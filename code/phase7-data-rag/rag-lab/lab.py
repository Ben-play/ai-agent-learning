"""Deterministic, local RAG retrieval. Caller identity is supplied by the trusted test host."""

from collections.abc import Iterable, Iterator
from contextlib import closing, contextmanager
from dataclasses import dataclass
import json
from math import hypot, isfinite
import sqlite3

Key = tuple[str, int, str]
Vector = tuple[float, ...]
DIMENSIONS = 3  # One fixed vector space for the SQLite teaching store.


@dataclass(frozen=True)
class Chunk:
    doc_id: str
    version: int
    locator: str
    title: str
    text: str
    terms: tuple[str, ...]
    vector: Vector

    @property
    def key(self) -> Key:
        return self.doc_id, self.version, self.locator


@dataclass(frozen=True)
class Query:
    terms: tuple[str, ...]
    vector: Vector = (0.0, 0.0, 0.0)


@dataclass(frozen=True)
class Hit:
    chunk: Chunk
    score: float


def cosine(left: Vector, right: Vector) -> float:
    if len(left) != len(right) or not left or not all(isfinite(x) for x in (*left, *right)):
        raise ValueError("vectors must have the same nonzero dimension and finite values")
    left_norm, right_norm = hypot(*left), hypot(*right)
    if not isfinite(left_norm) or not isfinite(right_norm):
        raise ValueError("unrepresentable vector norm")
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return sum((x / left_norm) * (y / right_norm) for x, y in zip(left, right, strict=True))


def rank(chunks: Iterable[Chunk], query: Query, *, mode: str = "lexical", k: int = 3) -> tuple[Hit, ...]:
    """Rank an already authorized pool. Neither this function nor embeddings grant access."""
    if mode not in {"lexical", "vector", "hybrid"}:
        raise ValueError("unknown retrieval mode")
    if type(k) is not int or k < 0:
        raise ValueError("k must be a nonnegative integer")
    if k == 0:
        return ()
    pool = tuple(chunks)
    if len({chunk.key for chunk in pool}) != len(pool):
        raise ValueError("duplicate chunk keys in candidate pool")

    def ordered(scores):
        hits = [Hit(chunk, float(score)) for chunk, score in scores if score > 0]
        return tuple(sorted(hits, key=lambda hit: (-hit.score, hit.chunk.key)))

    if mode != "vector":
        terms = set(query.terms)
        lexical = ordered((chunk, len(terms.intersection(chunk.terms))) for chunk in pool)
        if mode == "lexical":
            return lexical[:k]
    dense = ordered((chunk, cosine(chunk.vector, query.vector)) for chunk in pool)
    if mode == "vector":
        return dense[:k]
    scores: dict[Key, float] = {}
    entries: dict[Key, Chunk] = {}
    # Full positive lists from the same authorized pool, then one final top k.
    for results in (lexical, dense):
        for position, hit in enumerate(results, start=1):
            key = hit.chunk.key
            entries[key] = hit.chunk
            scores[key] = scores.get(key, 0.0) + 1 / (60 + position)
    return ordered((entries[key], score) for key, score in scores.items())[:k]


SCHEMA = """
CREATE TABLE documents (
    tenant TEXT NOT NULL, doc_id TEXT NOT NULL, version INTEGER NOT NULL,
    PRIMARY KEY (tenant, doc_id), UNIQUE (tenant, doc_id, version)
);
CREATE TABLE chunks (
    tenant TEXT NOT NULL, doc_id TEXT NOT NULL, version INTEGER NOT NULL,
    locator TEXT NOT NULL, title TEXT NOT NULL, text TEXT NOT NULL,
    terms TEXT NOT NULL, vector TEXT NOT NULL,
    PRIMARY KEY (tenant, doc_id, version, locator),
    FOREIGN KEY (tenant, doc_id, version) REFERENCES documents(tenant, doc_id, version) ON DELETE CASCADE
);
CREATE TABLE grants (
    tenant TEXT NOT NULL, doc_id TEXT NOT NULL, user_id TEXT NOT NULL,
    PRIMARY KEY (tenant, doc_id, user_id),
    FOREIGN KEY (tenant, doc_id) REFERENCES documents(tenant, doc_id) ON DELETE CASCADE
);
"""
VISIBLE = """
SELECT c.doc_id, c.version, c.locator, c.title, c.text, c.terms, c.vector
FROM chunks AS c
JOIN grants AS g ON (g.tenant, g.doc_id) = (c.tenant, c.doc_id)
WHERE c.tenant = ? AND g.user_id = ?
"""


class EvidenceStore:
    """One host-owned SQLite connection; caller IDs are not an authentication mechanism.

    The default corpus is independent of L61; its citation bridge supplies its
    own trusted fixture rows. A key is local to the tenant selected by the host.
    """

    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn
        self._epoch = 0

    @property
    def epoch(self) -> int:
        return self._epoch

    @staticmethod
    def _chunk(row) -> Chunk:
        doc_id, version, locator, title, text, terms, vector = row
        return Chunk(doc_id, version, locator, title, text, tuple(json.loads(terms)), tuple(json.loads(vector)))

    def authorized(self, tenant: str, user: str) -> tuple[Chunk, ...]:
        rows = self._conn.execute(VISIBLE + " ORDER BY c.doc_id, c.version, c.locator", (tenant, user))
        return tuple(map(self._chunk, rows))

    def source(self, tenant: str, user: str, key: Key) -> Chunk | None:
        row = self._conn.execute(VISIBLE + " AND (c.doc_id, c.version, c.locator) = (?, ?, ?)",
                                 (tenant, user, *key)).fetchone()
        return self._chunk(row) if row is not None else None

    def search(self, tenant: str, user: str, query: Query, *, mode: str = "lexical", k: int = 3) -> tuple[Hit, ...]:
        return rank(self.authorized(tenant, user), query, mode=mode, k=k)

    def revoke(self, tenant: str, user: str, doc_id: str) -> None:
        with self._conn:
            removed = self._conn.execute("DELETE FROM grants WHERE tenant=? AND user_id=? AND doc_id=?",
                                         (tenant, user, doc_id)).rowcount
        if removed:
            self._epoch += 1

    def _insert_chunks(self, tenant: str, chunks: Iterable[Chunk]) -> None:
        rows = []
        for chunk in chunks:
            if len(chunk.vector) != DIMENSIONS:
                raise ValueError(f"stored vectors must have {DIMENSIONS} dimensions")
            # Validate finite elements and norm before committing a published version.
            cosine(chunk.vector, (0.0,) * DIMENSIONS)
            rows.append((tenant, *chunk.key, chunk.title, chunk.text,
                         json.dumps(chunk.terms), json.dumps(chunk.vector, allow_nan=False)))
        self._conn.executemany("INSERT INTO chunks VALUES (?, ?, ?, ?, ?, ?, ?, ?)", rows)

    def replace_document(self, tenant: str, doc_id: str, version: int, chunks: Iterable[Chunk]) -> None:
        incoming = tuple(chunks)
        if (type(version) is not int or version < 1 or not incoming
                or any(c.doc_id != doc_id or type(c.version) is not int or c.version != version for c in incoming)
                or len({c.key for c in incoming}) != len(incoming)):
            raise ValueError("replacement requires unique chunks of the requested document version")
        with self._conn:
            current = self._conn.execute("SELECT version FROM documents WHERE tenant=? AND doc_id=?",
                                         (tenant, doc_id)).fetchone()
            if current is None or version <= current[0]:
                raise ValueError("replacement must advance an existing version")
            self._conn.execute("DELETE FROM chunks WHERE tenant=? AND doc_id=?", (tenant, doc_id))
            self._conn.execute("UPDATE documents SET version=? WHERE tenant=? AND doc_id=?", (version, tenant, doc_id))
            self._insert_chunks(tenant, incoming)
        self._epoch += 1

    def delete_document(self, tenant: str, doc_id: str) -> None:
        with self._conn:
            removed = self._conn.execute("DELETE FROM documents WHERE tenant=? AND doc_id=?",
                                         (tenant, doc_id)).rowcount
        if removed:
            self._epoch += 1


DEMO = (
    ("support", Chunk("EXPORT-POLICY", 1, "§1", "导出保留期", "导出文件生成后保留 7 天。",
                      ("导出", "保留", "有效期"), (1.0, 0.0, 0.0)), ("mei", "lin")),
    ("support", Chunk("EXPORT-OPS", 1, "§2", "导出过期处理", "导出文件过期后，需重新发起导出。",
                      ("导出", "过期", "重新生成"), (0.45, 0.89, 0.0)), ("mei",)),
    ("support", Chunk("SYNC-POLICY", 1, "§1", "同步时间", "同步任务每天 02:00 运行。",
                      ("同步", "02:00"), (0.0, 0.0, 1.0)), ("mei", "lin")),
    ("support", Chunk("EXPORT-INTERNAL", 1, "§1", "内部留存", "内部导出记录单独归档。",
                      ("导出", "保留", "过期", "有效期"), (1.0, 0.0, 0.0)), ("auditor",)),
    ("operations", Chunk("EXPORT-POLICY", 1, "§1", "运维导出保留期", "运维导出文件保留 30 天。",
                         ("导出", "保留"), (1.0, 0.0, 0.0)), ("mei",)),
)


@contextmanager
def open_demo(*, rows: Iterable[tuple[str, Chunk, tuple[str, ...]]] | None = None) -> Iterator[EvidenceStore]:
    """Seed a fresh lab. Optional rows come from a trusted course fixture, not a request."""
    documents: dict[tuple[str, str], tuple[int, frozenset[str]]] = {}
    chunks: dict[tuple[str, str], list[Chunk]] = {}
    for tenant, chunk, users in DEMO if rows is None else rows:
        if type(chunk.version) is not int or chunk.version < 1:
            raise ValueError("fixture version must be a positive integer")
        key = tenant, chunk.doc_id
        meta = chunk.version, frozenset(users)
        if documents.setdefault(key, meta) != meta:
            raise ValueError("fixture chunks of one document must share a version and grants")
        chunks.setdefault(key, []).append(chunk)
    with closing(sqlite3.connect(":memory:")) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(SCHEMA)
        store = EvidenceStore(conn)
        with conn:
            for (tenant, doc_id), (version, users) in documents.items():
                conn.execute("INSERT INTO documents VALUES (?, ?, ?)", (tenant, doc_id, version))
                store._insert_chunks(tenant, chunks[(tenant, doc_id)])
                conn.executemany("INSERT INTO grants VALUES (?, ?, ?)", ((tenant, doc_id, user) for user in users))
        yield store
