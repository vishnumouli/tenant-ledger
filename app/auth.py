import sqlite3
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException

from app.db import get_conn, hash_key


@dataclass(frozen=True)
class Caller:
    firm_id: str
    role: str
    actor: str


def get_caller(
    x_api_key: str | None = Header(default=None),
    conn: sqlite3.Connection = Depends(get_conn),
) -> Caller:
    # The firm always comes from the key, never from the URL or body.
    row = None
    if x_api_key:
        row = conn.execute(
            "SELECT firm_id, role, label FROM api_keys WHERE key_hash = ?", (hash_key(x_api_key),)
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=401, detail="missing or invalid API key")
    return Caller(firm_id=row["firm_id"], role=row["role"], actor=row["label"])


def require_writer(caller: Caller = Depends(get_caller)) -> Caller:
    if caller.role != "writer":
        raise HTTPException(status_code=403, detail="this key is read-only")
    return caller
