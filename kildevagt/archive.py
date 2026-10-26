"""Archive: raw bytes saved as-is, plus url, fetched_at and SHA-256 in SQLite.

Files are stored under their hash, so identical content is kept once.
Change detection compares the *content hash* of a URL with its previous one.
"""
import hashlib
import mimetypes
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .models import RawResponse

SCHEMA = """
CREATE TABLE IF NOT EXISTS fetches (
    id INTEGER PRIMARY KEY,
    run_id INTEGER, source_id TEXT, url TEXT, kind TEXT,
    fetched_at TEXT, sha256 TEXT, content_hash TEXT, path TEXT,
    change TEXT, title TEXT, doc_date TEXT, agenda_items INTEGER
);
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY, started_at TEXT, finished_at TEXT,
    requests INTEGER, note TEXT
);
CREATE TABLE IF NOT EXISTS run_sources (
    run_id INTEGER, source_id TEXT, items_found INTEGER,
    new INTEGER, changed INTEGER, unchanged INTEGER, errors TEXT,
    docs_checked INTEGER, docs_bad INTEGER, health TEXT, health_reasons TEXT
);
CREATE INDEX IF NOT EXISTS fetches_url ON fetches (source_id, url);
"""


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def classify_change(previous_hash: str | None, new_hash: str) -> str:
    """new / changed / unchanged, by comparing content hashes."""
    if previous_hash is None:
        return "new"
    return "unchanged" if previous_hash == new_hash else "changed"


class Archive:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.root / "kildevagt.db")
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)
        try:
            self.db.execute("ALTER TABLE fetches ADD COLUMN agenda_items INTEGER")
        except sqlite3.OperationalError:
            pass
        for column in ("docs_checked INTEGER", "docs_bad INTEGER", "health TEXT", "health_reasons TEXT"):
            try:  # databases made before milestone 5 lack the health columns
                self.db.execute(f"ALTER TABLE run_sources ADD COLUMN {column}")
            except sqlite3.OperationalError:
                pass

    def start_run(self) -> int:
        cur = self.db.execute("INSERT INTO runs (started_at) VALUES (?)", (_now(),))
        self.db.commit()
        return cur.lastrowid

    def finish_run(self, run_id: int, requests: int):
        self.db.execute("UPDATE runs SET finished_at=?, requests=? WHERE id=?",
                        (_now(), requests, run_id))
        self.db.commit()

    def record_source(self, run_id, source_id, items_found, counts: dict, errors: list[str],
                      docs_checked=0, docs_bad=0, health="", reasons=()):
        self.db.execute(
            "INSERT INTO run_sources (run_id, source_id, items_found, new, changed, unchanged, errors,"
            " docs_checked, docs_bad, health, health_reasons) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (run_id, source_id, items_found, counts.get("new", 0), counts.get("changed", 0),
             counts.get("unchanged", 0), "\n".join(errors), docs_checked, docs_bad, health,
             "\n".join(reasons)))
        self.db.commit()

    def previous_item_counts(self, source_id: str, limit: int = 5) -> list[int]:
        """Item counts of recent runs that were not red, newest first."""
        rows = self.db.execute(
            "SELECT items_found FROM run_sources WHERE source_id=? AND items_found > 0 "
            "AND COALESCE(health, '') != 'RED' ORDER BY run_id DESC LIMIT ?", (source_id, limit))
        return [r["items_found"] for r in rows]

    def best_item_count(self, source_id: str, url: str) -> int:
        """Most agenda items this page ever had in a readable fetch (0 if never seen)."""
        row = self.db.execute(
            "SELECT MAX(agenda_items) FROM fetches WHERE source_id=? AND url=? AND kind='meeting' "
            "AND content_hash NOT LIKE 'bad:%'", (source_id, url)).fetchone()
        return row[0] or 0

    def latest_fetch(self, source_id: str, url: str):
        return self.db.execute(
            "SELECT * FROM fetches WHERE source_id=? AND url=? AND kind='meeting' ORDER BY id DESC LIMIT 1",
            (source_id, url)).fetchone()

    def last_hash(self, source_id: str, url: str) -> str | None:
        row = self.db.execute(
            "SELECT content_hash FROM fetches WHERE source_id=? AND url=? AND content_hash NOT LIKE 'bad:%' "
            "ORDER BY id DESC LIMIT 1",
            (source_id, url)).fetchone()
        return row["content_hash"] if row else None

    def fetched_recently(self, source_id: str, url: str, hours: float) -> bool:
        row = self.db.execute(
            "SELECT fetched_at FROM fetches WHERE source_id=? AND url=? ORDER BY id DESC LIMIT 1",
            (source_id, url)).fetchone()
        if not row:
            return False
        age = datetime.now(timezone.utc) - datetime.fromisoformat(row["fetched_at"])
        return age < timedelta(hours=hours)

    def store(self, run_id: int, source_id: str, raw: RawResponse, kind: str,
              content_hash: str | None = None, title: str = "", doc_date=None,
              agenda_items: int | None = None) -> str:
        """Save raw bytes untouched, record the fetch, return new/changed/unchanged."""
        digest = sha256(raw.content)
        content_hash = content_hash or digest
        extension = mimetypes.guess_extension(raw.content_type.split(";")[0].strip()) or ".bin"
        path = self.root / source_id / digest[:2] / f"{digest}{extension}"
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw.content)
        if content_hash.startswith("bad:"):  # page could not be read properly: never a baseline
            change = "unreadable"
        else:
            change = classify_change(self.last_hash(source_id, raw.url), content_hash)
        self.db.execute(
            "INSERT INTO fetches (run_id, source_id, url, kind, fetched_at, sha256, content_hash,"
            " path, change, title, doc_date, agenda_items) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (run_id, source_id, raw.url, kind, raw.fetched_at.isoformat(), digest, content_hash,
             str(path.relative_to(self.root)), change, title,
             doc_date.isoformat() if doc_date else None, agenda_items))
        self.db.commit()
        return change


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
