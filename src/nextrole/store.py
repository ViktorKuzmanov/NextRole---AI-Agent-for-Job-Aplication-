"""SQLite store: one row per posting NextRole has looked at.

It is both the dedupe memory (a posting is classified once) and the record the
dashboard will read.
"""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .models import Application, ClassifiedJob

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id           TEXT PRIMARY KEY,
    source       TEXT NOT NULL,
    company      TEXT NOT NULL,
    title        TEXT NOT NULL,
    location     TEXT,
    url          TEXT NOT NULL,
    role         TEXT NOT NULL,
    fit_score    INTEGER NOT NULL,
    reason       TEXT,
    status       TEXT NOT NULL,       -- skipped | prepared | submitted | failed
    cover_letter TEXT,
    submitted    TEXT,                -- JSON of exactly what was sent
    created_at   TEXT NOT NULL
)
"""


class Store:
    def __init__(self, path: Path | str):
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.execute(SCHEMA)

    def seen_ids(self) -> set[str]:
        return {row["id"] for row in self.db.execute("SELECT id FROM jobs")}

    def _upsert(self, item: ClassifiedJob, status: str, cover_letter=None, submitted=None):
        job, c = item.job, item.classification
        self.db.execute(
            "INSERT OR REPLACE INTO jobs VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                job.id, job.source, job.company, job.title, job.location, job.url,
                c.role, c.fit_score, c.reason, status, cover_letter,
                json.dumps(submitted) if submitted else None,
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
            ),
        )

    def save(self, classified: list[ClassifiedJob], applications: list[Application]) -> None:
        applied = {a.job.id: a for a in applications}
        with self.db:
            for item in classified:
                app = applied.get(item.job.id)
                if app:
                    self._upsert(item, app.status, app.cover_letter, app.submitted)
                else:
                    self._upsert(item, "skipped")

    def rows(self, status: str | None = None) -> list[sqlite3.Row]:
        query = "SELECT * FROM jobs"
        args: tuple = ()
        if status:
            query += " WHERE status = ?"
            args = (status,)
        return self.db.execute(query + " ORDER BY created_at DESC, fit_score DESC", args).fetchall()
