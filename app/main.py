import sqlite3
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request, Response
from fastapi.responses import JSONResponse

from app import db, ledger
from app.auth import Caller, get_caller, require_writer
from app.db import get_conn
from app.schemas import EntryIn


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
