from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI

from app import db
from app.auth import Caller, get_caller


@asynccontextmanager
async def lifespan(_app: FastAPI):
    conn = db.connect()
    db.init_db(conn)
    conn.close()
    yield


app = FastAPI(title="Tenant Ledger", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/v1/me")
def me(caller: Caller = Depends(get_caller)):
    return {"firm_id": caller.firm_id, "role": caller.role}
