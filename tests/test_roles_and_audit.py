import pytest

from tests.conftest import HB_WRITER, NB_SUPPORT, NB_WRITER
from tests.helpers import entry, post


@pytest.mark.parametrize(
    ("path", "body"),
    [
        ("/v1/entries", entry()),
        ("/v1/transfers", {}),
        ("/v1/imports", {"rows": [entry()]}),
        ("/v1/entries/1/reversal", {"reason": "x"}),
    ],
)
def test_support_cannot_write(client, conn, path, body):
    post(client, external_id="seed")
    assert client.post(path, json=body, headers=NB_SUPPORT).status_code == 403
    assert conn.execute("SELECT COUNT(*) FROM entries").fetchone()[0] == 1


def test_support_cannot_read_audit_log(client):
    assert client.get("/v1/audit", headers=NB_SUPPORT).status_code == 403


def test_support_sees_balance_and_entries_without_sensitive_fields(client):
    post(client, external_id="d", memo="client called about divorce settlement")
    assert client.get("/v1/clients/C-1/balance", headers=NB_SUPPORT).status_code == 200
    entries = client.get("/v1/clients/C-1/entries", headers=NB_SUPPORT).json()["entries"]
    assert entries[0]["amount"] == "100.00"
    assert "memo" not in entries[0] and "created_by" not in entries[0]


def test_writer_sees_full_entry(client):
    post(client, external_id="d", memo="note")
    e = client.get("/v1/clients/C-1/entries", headers=NB_WRITER).json()["entries"][0]
    assert (e["memo"], e["created_by"]) == ("note", "northbridge-advisor")


def test_audit_log_answers_who_did_what_when(client):
    entry_id = post(client, external_id="d").json()["entry"]["id"]
    client.post(f"/v1/entries/{entry_id}/reversal", json={"reason": "duplicate"}, headers=NB_WRITER)
    events = client.get("/v1/audit", headers=NB_WRITER).json()["events"]
    assert [(e["action"], e["actor"], e["entity_id"]) for e in events] == [
        ("entry.reversed", "northbridge-advisor", entry_id),
        ("entry.created", "northbridge-advisor", entry_id),
    ]
    assert events[0]["detail"]["reason"] == "duplicate" and events[0]["at"]


def test_audit_log_is_tenant_scoped(client):
    post(client, external_id="nb-only")
    assert client.get("/v1/audit", headers=HB_WRITER).json()["events"] == []
