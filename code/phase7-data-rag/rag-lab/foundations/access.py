"""L60: a synthetic SQLite analogue, not PostgreSQL RLS or authentication."""

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass


@dataclass(frozen=True)
class HostActor:
    """The trusted host supplies this; never construct it from tool arguments."""

    tenant: str
    user: str


@dataclass(frozen=True)
class Document:
    tenant: str
    doc_id: str
    audience: str
    body: str


@dataclass(frozen=True)
class Membership:
    tenant: str
    user: str
    role: str


WORKED_DOCUMENTS = (
    Document("north", "KB-01", "member", "北站领取台在 21:30 停止发放。"),
    Document("north", "KB-02", "reviewer", "北站复核表在 22:00 汇总。"),
    Document("south", "KB-01", "member", "南站领取台在 20:30 停止发放。"),
)
WORKED_MEMBERSHIPS = (
    Membership("north", "lin", "reader"),
    Membership("north", "mei", "reviewer"),
    Membership("south", "lin", "reader"),
)


@contextmanager
def open_fixture(documents=WORKED_DOCUMENTS, memberships=WORKED_MEMBERSHIPS):
    """Seed a fresh in-memory database, then expose only the read phase."""
    db = sqlite3.connect(":memory:")
    try:
        db.executescript("""
            CREATE TABLE membership (
                tenant TEXT NOT NULL, user_key TEXT NOT NULL,
                role TEXT NOT NULL CHECK (role IN ('reader', 'reviewer')),
                PRIMARY KEY (tenant, user_key)
            );
            CREATE TABLE document (
                tenant TEXT NOT NULL, doc_id TEXT NOT NULL,
                audience TEXT NOT NULL CHECK (audience IN ('member', 'reviewer')),
                body TEXT NOT NULL, PRIMARY KEY (tenant, doc_id)
            );
        """)
        db.executemany("INSERT INTO membership VALUES (?, ?, ?)",
                       ((m.tenant, m.user, m.role) for m in memberships))
        db.executemany("INSERT INTO document VALUES (?, ?, ?, ?)",
                       ((d.tenant, d.doc_id, d.audience, d.body) for d in documents))
        db.commit()
        db.execute("PRAGMA query_only = ON")
        yield db
    finally:
        db.close()


def visible_documents(db, actor: HostActor, doc_id: str | None = None) -> tuple[Document, ...]:
    """Apply tenant, membership and audience checks before returning candidates."""
    rows = db.execute("""
        SELECT d.tenant, d.doc_id, d.audience, d.body
        FROM document AS d
        JOIN membership AS m ON m.tenant = d.tenant
        WHERE d.tenant = :tenant AND m.user_key = :user
          AND (d.audience = 'member' OR m.role = 'reviewer')
          AND (:doc_id IS NULL OR d.doc_id = :doc_id)
        ORDER BY d.doc_id
    """, {"tenant": actor.tenant, "user": actor.user, "doc_id": doc_id})
    return tuple(Document(*row) for row in rows)
