import sqlite3

import pytest

INSERT = (
    "INSERT INTO entries (firm_id, client_ref, type, amount_minor, currency, effective_date, "
    "recorded_at, created_by) VALUES ('northbridge', 'C1', 'deposit', 100, 'USD', '2026-01-01', 'now', 't')"
)


def test_seed_creates_two_firms(conn):
    assert conn.execute("SELECT COUNT(*) FROM firms").fetchone()[0] == 2


@pytest.mark.parametrize(
    "statement",
    ["UPDATE entries SET amount_minor = 999", "DELETE FROM entries"],
)
def test_entries_cannot_be_rewritten(conn, statement):
    conn.execute(INSERT)
    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        conn.execute(statement)
    assert conn.execute("SELECT amount_minor FROM entries").fetchone()[0] == 100


@pytest.mark.parametrize("statement", ["UPDATE audit_events SET actor = 'x'", "DELETE FROM audit_events"])
def test_audit_cannot_be_rewritten(conn, statement):
    conn.execute(
        "INSERT INTO audit_events (firm_id, actor, action, detail, at) VALUES ('northbridge', 'a', 'x', '{}', 'now')"
    )
    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        conn.execute(statement)


def test_zero_amount_rejected_by_schema(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(INSERT.replace(" 100,", " 0,"))
