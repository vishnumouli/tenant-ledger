import hashlib
import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager

SCHEMA = """
CREATE TABLE IF NOT EXISTS firms (
    id   TEXT PRIMARY KEY,
    name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS api_keys (
    key_hash TEXT PRIMARY KEY,
    firm_id  TEXT NOT NULL REFERENCES firms(id),
    role     TEXT NOT NULL CHECK (role IN ('writer', 'support')),
    label    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS entries (
    id                INTEGER PRIMARY KEY,
    firm_id           TEXT NOT NULL REFERENCES firms(id),
    client_ref        TEXT NOT NULL,
    type              TEXT NOT NULL CHECK (type IN
                        ('deposit', 'withdrawal', 'fee', 'transfer_in', 'transfer_out', 'reversal')),
    amount_minor      INTEGER NOT NULL CHECK (amount_minor <> 0),
    currency          TEXT NOT NULL,
    effective_date    TEXT NOT NULL,
    recorded_at       TEXT NOT NULL,
    created_by        TEXT NOT NULL,
    external_id       TEXT,
    reverses_entry_id INTEGER UNIQUE REFERENCES entries(id),
    transfer_id       TEXT,
    memo              TEXT,
    UNIQUE (firm_id, external_id)
);
CREATE INDEX IF NOT EXISTS ix_entries_client_date
    ON entries (firm_id, client_ref, effective_date);
CREATE INDEX IF NOT EXISTS ix_entries_transfer ON entries (firm_id, transfer_id);

CREATE TABLE IF NOT EXISTS audit_events (
    id        INTEGER PRIMARY KEY,
    firm_id   TEXT NOT NULL REFERENCES firms(id),
    actor     TEXT NOT NULL,
    action    TEXT NOT NULL,
    entity_id INTEGER,
    detail    TEXT NOT NULL,
    at        TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_audit_firm ON audit_events (firm_id, id);

CREATE TRIGGER IF NOT EXISTS entries_no_update BEFORE UPDATE ON entries
BEGIN SELECT RAISE(ABORT, 'entries are append-only'); END;
CREATE TRIGGER IF NOT EXISTS entries_no_delete BEFORE DELETE ON entries
BEGIN SELECT RAISE(ABORT, 'entries are append-only'); END;
CREATE TRIGGER IF NOT EXISTS audit_no_update BEFORE UPDATE ON audit_events
BEGIN SELECT RAISE(ABORT, 'audit_events are append-only'); END;
CREATE TRIGGER IF NOT EXISTS audit_no_delete BEFORE DELETE ON audit_events
BEGIN SELECT RAISE(ABORT, 'audit_events are append-only'); END;
"""

DEMO_FIRMS = [("northbridge", "Northbridge Advisory"), ("harbor", "Harbor Wealth")]
DEMO_KEYS = [
    ("nb-writer-key", "northbridge", "writer", "northbridge-advisor"),
    ("nb-support-key", "northbridge", "support", "northbridge-support"),
    ("hb-writer-key", "harbor", "writer", "harbor-advisor"),
    ("hb-support-key", "harbor", "support", "harbor-support"),
]


def hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def db_path() -> str:
    return os.environ.get("LEDGER_DB", "ledger.db")


def connect(path: str | None = None) -> sqlite3.Connection:
    # isolation_level=None: we issue BEGIN/COMMIT ourselves. timeout=5: wait up to 5s for the write lock.
    conn = sqlite3.connect(path or db_path(), isolation_level=None, timeout=5, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA journal_mode = WAL")
    conn.executescript(SCHEMA)
    with write_tx(conn):
        conn.executemany("INSERT OR IGNORE INTO firms (id, name) VALUES (?, ?)", DEMO_FIRMS)
        conn.executemany(
            "INSERT OR IGNORE INTO api_keys (key_hash, firm_id, role, label) VALUES (?, ?, ?, ?)",
            [(hash_key(k), firm, role, label) for k, firm, role, label in DEMO_KEYS],
        )


@contextmanager
def write_tx(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """BEGIN IMMEDIATE takes the database write lock up front, so check-then-insert is atomic."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    conn.execute("COMMIT")


def get_conn() -> Iterator[sqlite3.Connection]:
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()
