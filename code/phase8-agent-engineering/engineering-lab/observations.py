"""Independent readback for the lab's temporary Phase 5 SQLite files."""

from contextlib import closing
import json
from pathlib import Path
import sqlite3


def saved_drafts(path):
    """Read committed rows across all subjects; never return a scoped subset."""
    uri = Path(path).resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as db:
        return tuple((op_id, tenant, actor, job, json.loads(payload))
                     for op_id, tenant, actor, job, payload in db.execute(
                         "SELECT op_id, tenant, actor, job, payload FROM saved_drafts ORDER BY op_id"))
