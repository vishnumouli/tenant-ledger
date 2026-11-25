import json
import sqlite3
from datetime import date, datetime, timezone

from pydantic import ValidationError

from app import money
from app.auth import Caller
from app.db import write_tx
from app.schemas import EntryIn

# Money in is positive, money out is negative, so a balance is just SUM(amount_minor).
SIGNS = {"deposit": 1, "withdrawal": -1, "fee": -1}


class LedgerError(Exception):
    status = 400

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class NotFound(LedgerError):
    status = 404


class Conflict(LedgerError):
    status = 409


class Rejected(LedgerError):
    status = 422


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _check_date(effective_date: date) -> None:
    if effective_date > datetime.now(timezone.utc).date():
        raise Rejected("effective_date cannot be in the future")


def _parse_amount(amount: str, currency: str) -> int:
    try:
        return money.to_minor(amount, currency)
    except money.MoneyError as exc:
        raise Rejected(str(exc)) from None


def audit(conn: sqlite3.Connection, caller: Caller, action: str, entity_id: int | None, detail: dict) -> None:
    conn.execute(
        "INSERT INTO audit_events (firm_id, actor, action, entity_id, detail, at) VALUES (?, ?, ?, ?, ?, ?)",
        (caller.firm_id, caller.actor, action, entity_id, json.dumps(detail, default=str), _now()),
    )


def current_balance(conn: sqlite3.Connection, firm_id: str, client_ref: str, currency: str) -> int:
    return conn.execute(
        "SELECT COALESCE(SUM(amount_minor), 0) FROM entries WHERE firm_id = ? AND client_ref = ? AND currency = ?",
        (firm_id, client_ref, currency),
    ).fetchone()[0]


def _ensure_funds(conn: sqlite3.Connection, firm_id: str, client_ref: str, currency: str, needed: int) -> None:
    """Must run inside write_tx: the write lock guarantees nobody spends the same money between check and insert."""
    balance = current_balance(conn, firm_id, client_ref, currency)
    if balance < needed:
        raise Rejected(
            f"insufficient funds for {client_ref}: balance {money.to_major(balance, currency)} {currency}, "
            f"needed {money.to_major(needed, currency)} {currency}"
        )


def _insert_entry(conn: sqlite3.Connection, caller: Caller, **fields) -> int:
    fields |= {"firm_id": caller.firm_id, "created_by": caller.actor, "recorded_at": _now()}
    columns = ", ".join(fields)
    placeholders = ", ".join("?" for _ in fields)
    cur = conn.execute(f"INSERT INTO entries ({columns}) VALUES ({placeholders})", tuple(fields.values()))
    return cur.lastrowid


def get_entry(conn: sqlite3.Connection, firm_id: str, entry_id: int) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM entries WHERE id = ? AND firm_id = ?", (entry_id, firm_id)).fetchone()
    if row is None:
        raise NotFound(f"entry {entry_id} not found")
    return row


def post_entry(conn: sqlite3.Connection, caller: Caller, e: EntryIn) -> tuple[sqlite3.Row, str, list[str]]:
    """Record a deposit, withdrawal or fee. Returns (entry, "created" | "duplicate", warnings)."""
    minor = _parse_amount(e.amount, e.currency)
    _check_date(e.effective_date)
    signed = SIGNS[e.type] * minor
    day = e.effective_date.isoformat()
    warnings: list[str] = []

    with write_tx(conn):
        existing = conn.execute(
            "SELECT * FROM entries WHERE firm_id = ? AND external_id = ?", (caller.firm_id, e.external_id)
        ).fetchone()
        if existing is not None:
            same = (existing["client_ref"], existing["type"], existing["amount_minor"],
                    existing["currency"], existing["effective_date"]) == (e.client_ref, e.type, signed, e.currency, day)
            if not same:
                raise Conflict(f"external_id {e.external_id!r} was already used with different details")
            return existing, "duplicate", warnings

        if signed < 0:
            _ensure_funds(conn, caller.firm_id, e.client_ref, e.currency, -signed)

        lookalike = conn.execute(
            "SELECT id FROM entries WHERE firm_id = ? AND client_ref = ? AND type = ? AND amount_minor = ? "
            "AND currency = ? AND effective_date = ? LIMIT 1",
            (caller.firm_id, e.client_ref, e.type, signed, e.currency, day),
        ).fetchone()
        if lookalike is not None:
            warnings.append(
                f"possible_duplicate: entry {lookalike['id']} has the same client, type, amount, currency and date"
            )

        entry_id = _insert_entry(
            conn, caller, client_ref=e.client_ref, type=e.type, amount_minor=signed, currency=e.currency,
            effective_date=day, external_id=e.external_id, memo=e.memo,
        )
        audit(conn, caller, "entry.created", entry_id, e.model_dump(mode="json"))

    return get_entry(conn, caller.firm_id, entry_id), "created", warnings


def import_rows(conn: sqlite3.Connection, caller: Caller, rows: list) -> dict:
    """Each row commits on its own, in order: good rows land, bad rows are reported, re-sent rows are no-ops."""
    results = []
    for index, raw in enumerate(rows):
        try:
            entry, status, warnings = post_entry(conn, caller, EntryIn.model_validate(raw))
            results.append({"row": index, "status": status, "entry_id": entry["id"], "warnings": warnings})
        except ValidationError as exc:
            errors = [f"{'.'.join(map(str, err['loc'])) or 'row'}: {err['msg']}" for err in exc.errors()]
            results.append({"row": index, "status": "rejected", "errors": errors})
        except LedgerError as exc:
            results.append({"row": index, "status": "rejected", "errors": [exc.message]})

    counts = {s: sum(r["status"] == s for r in results) for s in ("created", "duplicate", "rejected")}
    with write_tx(conn):
        audit(conn, caller, "import.completed", None, {"rows": len(rows), **counts})
    return {"summary": counts, "results": results}


def _require_client(conn: sqlite3.Connection, firm_id: str, client_ref: str) -> None:
    # Unknown and other-firm clients look identical (404), so existence never leaks across tenants.
    found = conn.execute(
        "SELECT 1 FROM entries WHERE firm_id = ? AND client_ref = ? LIMIT 1", (firm_id, client_ref)
    ).fetchone()
    if found is None:
        raise NotFound(f"client {client_ref} not found")


def balance_as_of(conn: sqlite3.Connection, firm_id: str, client_ref: str, as_of: date) -> list[dict]:
    _require_client(conn, firm_id, client_ref)
    rows = conn.execute(
        "SELECT currency, SUM(amount_minor) AS total FROM entries "
        "WHERE firm_id = ? AND client_ref = ? AND effective_date <= ? GROUP BY currency ORDER BY currency",
        (firm_id, client_ref, as_of.isoformat()),
    ).fetchall()
    return [
        {"currency": r["currency"], "amount": money.to_major(r["total"], r["currency"]), "amount_minor": r["total"]}
        for r in rows
    ]


def list_entries(
    conn: sqlite3.Connection, firm_id: str, client_ref: str, date_from: date | None, date_to: date | None
) -> list[sqlite3.Row]:
    _require_client(conn, firm_id, client_ref)
    return conn.execute(
        "SELECT * FROM entries WHERE firm_id = ? AND client_ref = ? "
        "AND effective_date >= ? AND effective_date <= ? ORDER BY effective_date, id",
        (firm_id, client_ref, (date_from or date.min).isoformat(), (date_to or date.max).isoformat()),
    ).fetchall()


def entry_view(row: sqlite3.Row, caller: Caller) -> dict:
    data = dict(row)
    data["amount"] = money.to_major(row["amount_minor"], row["currency"])
    del data["firm_id"]
    return data
