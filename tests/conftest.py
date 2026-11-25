import pytest
from fastapi.testclient import TestClient

from app import db

NB_WRITER = {"X-API-Key": "nb-writer-key"}
NB_SUPPORT = {"X-API-Key": "nb-support-key"}
HB_WRITER = {"X-API-Key": "hb-writer-key"}


@pytest.fixture
def db_file(tmp_path, monkeypatch):
    path = tmp_path / "ledger.db"
    monkeypatch.setenv("LEDGER_DB", str(path))
    conn = db.connect()
    db.init_db(conn)
    conn.close()
    return path


@pytest.fixture
def conn(db_file):
    c = db.connect()
    yield c
    c.close()


@pytest.fixture
def client(db_file):
    from app.main import app

    with TestClient(app) as c:
        yield c
