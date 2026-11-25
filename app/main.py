import sqlite3
from contextlib import asynccontextmanager
from datetime import date, datetime, timezone

from fastapi import Depends, FastAPI, Query, Request, Response
from fastapi.responses import JSONResponse

from app import db, ledger
from app.auth import Caller, get_caller, require_writer
from app.db import get_conn
from app.schemas import EntryIn, ImportIn, ReversalIn, TransferIn

MONTH = r"^\d{4}-(0[1-9]|1[0-2])$"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    conn = db.connect()
    db.init_db(conn)
    conn.close()
    yield


app = FastAPI(title="Tenant Ledger", lifespan=lifespan)


@app.exception_handler(ledger.LedgerError)
async def ledger_error(_request: Request, exc: ledger.LedgerError):
    return JSONResponse(status_code=exc.status, content={"detail": exc.message})


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/v1/me")
def me(caller: Caller = Depends(get_caller)):
    return {"firm_id": caller.firm_id, "role": caller.role}


@app.post("/v1/entries", status_code=201)
def create_entry(
    body: EntryIn,
    response: Response,
    caller: Caller = Depends(require_writer),
    conn: sqlite3.Connection = Depends(get_conn),
):
    entry, status, warnings = ledger.post_entry(conn, caller, body)
    if status == "duplicate":
        response.status_code = 200
    return {"status": status, "entry": ledger.entry_view(entry, caller), "warnings": warnings}


@app.post("/v1/transfers", status_code=201)
def create_transfer(
    body: TransferIn,
    response: Response,
    caller: Caller = Depends(require_writer),
    conn: sqlite3.Connection = Depends(get_conn),
):
    legs, status = ledger.post_transfer(conn, caller, body)
    if status == "duplicate":
        response.status_code = 200
    return {
        "status": status,
        "transfer_id": legs[0]["transfer_id"],
        "entries": [ledger.entry_view(leg, caller) for leg in legs],
    }


@app.post("/v1/entries/{entry_id}/reversal", status_code=201)
def create_reversal(
    entry_id: int,
    body: ReversalIn,
    caller: Caller = Depends(require_writer),
    conn: sqlite3.Connection = Depends(get_conn),
):
    reversals = ledger.reverse_entry(conn, caller, entry_id, body.reason)
    return {"reversals": [ledger.entry_view(r, caller) for r in reversals]}


@app.post("/v1/imports")
def create_import(
    body: ImportIn,
    caller: Caller = Depends(require_writer),
    conn: sqlite3.Connection = Depends(get_conn),
):
    return ledger.import_rows(conn, caller, body.rows)


@app.get("/v1/clients/{client_ref}/balance")
def client_balance(
    client_ref: str,
    as_of: date | None = None,
    caller: Caller = Depends(get_caller),
    conn: sqlite3.Connection = Depends(get_conn),
):
    as_of = as_of or datetime.now(timezone.utc).date()
    return {
        "client_ref": client_ref,
        "as_of": as_of,
        "balances": ledger.balance_as_of(conn, caller.firm_id, client_ref, as_of),
    }


@app.get("/v1/clients/{client_ref}/entries")
def client_entries(
    client_ref: str,
    date_from: date | None = Query(default=None, alias="from"),
    date_to: date | None = Query(default=None, alias="to"),
    caller: Caller = Depends(get_caller),
    conn: sqlite3.Connection = Depends(get_conn),
):
    rows = ledger.list_entries(conn, caller.firm_id, client_ref, date_from, date_to)
    return {"client_ref": client_ref, "entries": [ledger.entry_view(r, caller) for r in rows]}


@app.get("/v1/clients/{client_ref}/summary")
def client_summary(
    client_ref: str,
    month_from: str = Query(alias="from", pattern=MONTH),
    month_to: str = Query(alias="to", pattern=MONTH),
    caller: Caller = Depends(get_caller),
    conn: sqlite3.Connection = Depends(get_conn),
):
    months = ledger.monthly_summary(conn, caller.firm_id, client_ref, month_from, month_to)
    return {"client_ref": client_ref, "months": months}


@app.get("/v1/audit")
def audit_log(
    limit: int = Query(default=100, ge=1, le=500),
    caller: Caller = Depends(require_writer),
    conn: sqlite3.Connection = Depends(get_conn),
):
    return {"events": ledger.list_audit(conn, caller.firm_id, limit)}
