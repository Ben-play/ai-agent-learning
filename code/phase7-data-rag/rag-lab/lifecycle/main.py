"""Offline reranking, evidence packing and two request caches over the shared SQLite lab."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import runpy
from statistics import median
from timeit import Timer

CORE = runpy.run_path(str(Path(__file__).resolve().parents[1] / "lab.py"))
Chunk, Query, Hit, Key, EvidenceStore, open_demo = (
    CORE[name] for name in ("Chunk", "Query", "Hit", "Key", "EvidenceStore", "open_demo")
)
NO_EVIDENCE = "没有可用证据，无法回答。"


def rerank(candidates: tuple[Hit, ...], authorized: tuple[Chunk, ...],
           cues: tuple[str, ...]) -> tuple[Hit, ...]:
    """Score only the given authorized candidates; preserve their order on ties."""
    allowed = {chunk.key: chunk for chunk in authorized}
    seen: set[Key] = set()
    scores = []
    cue_set = set(cues)
    for hit in candidates:
        chunk = hit.chunk
        if chunk.key in seen or allowed.get(chunk.key) != chunk:
            raise ValueError("candidate is duplicate, absent, or not current authorized content")
        seen.add(chunk.key)
        scores.append(Hit(chunk, len(cue_set.intersection(chunk.terms))))
    return tuple(sorted(scores, key=lambda hit: -hit.score))


def _render(chunks: tuple[Chunk, ...]) -> str:
    if not chunks:
        return ""
    lines = (f"[{c.doc_id} v{c.version} {c.locator}] {c.title}：{c.text}" for c in chunks)
    return "证据：\n" + "\n".join(lines) + "\n"


@dataclass(frozen=True)
class Packed:
    chunks: tuple[Chunk, ...]
    context: str

    @property
    def citations(self) -> tuple[Key, ...]:
        return tuple(chunk.key for chunk in self.chunks)

    @property
    def chars(self) -> int:
        return len(self.context)

    @property
    def utf8_bytes(self) -> int:
        return len(self.context.encode("utf-8"))


def pack(hits: tuple[Hit, ...], *, top_k: int, max_chars: int, max_bytes: int) -> Packed:
    """Greedily pack whole entries under both limits, skipping entries that do not fit."""
    for value in (top_k, max_chars, max_bytes):
        if type(value) is not int or value < 0:
            raise ValueError("packing limits must be nonnegative integers")
    packed = Packed((), "")
    for hit in hits:
        if len(packed.chunks) == top_k:
            break
        chunks = packed.chunks + (hit.chunk,)
        proposal = Packed(chunks, _render(chunks))
        if proposal.chars <= max_chars and proposal.utf8_bytes <= max_bytes:
            packed = proposal
    return packed


@dataclass(frozen=True)
class Plan:
    mode: str = "lexical"
    candidate_k: int = 3
    cues: tuple[str, ...] | None = None  # None selects the unmodified candidate order.
    top_k: int = 1
    max_chars: int = 64
    max_bytes: int = 120


@dataclass(frozen=True)
class Answer:
    text: str
    context: str
    citations: tuple[Key, ...]


@dataclass
class Stats:
    searches: int = 0
    retrieval_hits: int = 0
    compositions: int = 0
    answer_hits: int = 0


CacheKey = tuple[int, str, str, Query, Plan]
AnswerKey = tuple[CacheKey, frozenset[str]]


@dataclass(frozen=True)
class _CachedAnswer:
    answer: Answer
    dependencies: tuple[Chunk, ...]


class EvidenceCaches:
    """One host-owned store, one process, sequential access only; no TTL or LRU."""

    def __init__(self, db: EvidenceStore):
        self.db = db
        self._epoch = db.epoch
        self._retrieval: dict[CacheKey, tuple[Key, ...]] = {}
        self._answers: dict[AnswerKey, _CachedAnswer] = {}
        self.stats = Stats()

    def _key(self, tenant: str, user: str, query: Query, plan: Plan) -> CacheKey:
        epoch = self.db.epoch
        if epoch != self._epoch:
            self._retrieval.clear()
            self._answers.clear()
            self._epoch = epoch
        return epoch, tenant, user, query, plan

    def _current(self, tenant: str, user: str, keys: tuple[Key, ...]) -> tuple[Chunk, ...] | None:
        chunks = []
        for key in keys:
            chunk = self.db.source(tenant, user, key)
            if chunk is None:
                return None  # Do not silently drop one dependency and reuse the partial result.
            chunks.append(chunk)
        return tuple(chunks)

    def retrieve(self, tenant: str, user: str, query: Query, plan: Plan = Plan()) -> Packed:
        key = self._key(tenant, user, query, plan)
        if key in self._retrieval:
            chunks = self._current(tenant, user, self._retrieval[key])
            if chunks is not None:
                self.stats.retrieval_hits += 1
                return Packed(chunks, _render(chunks))
        self.stats.searches += 1
        hits = self.db.search(tenant, user, query, mode=plan.mode, k=plan.candidate_k)
        if plan.cues is not None:
            hits = rerank(hits, self.db.authorized(tenant, user), plan.cues)
        result = pack(hits, top_k=plan.top_k, max_chars=plan.max_chars, max_bytes=plan.max_bytes)
        self._retrieval[key] = result.citations
        return result

    def answer(self, tenant: str, user: str, query: Query, plan: Plan = Plan(), *,
               required_terms: tuple[str, ...] | None = None) -> Answer:
        """Quote the first packed chunk carrying every required fixture tag, or abstain.

        Defaults to all query terms. A task can specify its own terms when the query
        is only a coarse retrieval hint. This is not semantic entailment checking.
        """
        terms = frozenset(query.terms if required_terms is None else required_terms)
        key = (self._key(tenant, user, query, plan), terms)
        saved = self._answers.get(key)
        if saved is not None:
            current = self._current(tenant, user, tuple(c.key for c in saved.dependencies))
            if current == saved.dependencies:
                self.stats.answer_hits += 1
                return saved.answer

        result = self.retrieve(tenant, user, query, plan)
        self.stats.compositions += 1
        support = next((c for c in result.chunks if terms and terms.issubset(c.terms)), None)
        answer = (Answer(support.text, _render((support,)), (support.key,)) if support is not None
                  else Answer(NO_EVIDENCE, "", ()))
        self._answers[key] = _CachedAnswer(answer, result.chunks)
        return answer


def _report_timing() -> None:
    """Compare two local stages from one already authorized, frozen batch."""
    query = Query(("导出", "保留"), (1.0, 0.0, 0.0))
    with open_demo() as db:
        pool = db.authorized("support", "mei")
        candidates = db.search("support", "mei", query, mode="hybrid", k=2)
    cues = ("过期", "重新生成")
    limits = dict(top_k=1, max_chars=64, max_bytes=100)

    def baseline():
        return pack(candidates, **limits)

    def adjusted():
        return pack(rerank(candidates, pool, cues), **limits)

    trials = (("baseline", baseline, 0), ("rerank", adjusted, len(candidates)))
    rounds, iterations = 7, 1000
    timers = {name: Timer(fn) for name, fn, _ in trials}
    samples: dict[str, list[float]] = {name: [] for name in timers}
    picked = {name: fn().citations for name, fn, _ in trials}  # Untimed warm-up.
    for index in range(rounds):
        for name, _, _ in trials[::1 if index % 2 == 0 else -1]:
            samples[name].append(timers[name].timeit(number=iterations))

    print(f"Synthetic batch: {len(candidates)} candidates; {limits}; {rounds} x {iterations} per arm")
    for name, _, scores in trials:
        per_call = median(samples[name]) * 1_000_000 / iterations
        print(f"{name}: {scores} rerank scores + 1 pack call/request; "
              f"median {per_call:.2f} us/request; packed {picked[name]}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timing", action="store_true", help="report local L65 timing separately")
    if parser.parse_args().timing:
        _report_timing()
