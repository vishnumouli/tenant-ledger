import json

import pytest

from tests.helpers import post


def test_deposit_is_stored_as_signed_minor_units(client):
    r = post(client, amount="12.34")
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "created"
    assert body["entry"]["amount_minor"] == 1234
    assert body["entry"]["amount"] == "12.34"
    assert body["entry"]["created_by"] == "northbridge-advisor"


def test_withdrawal_and_fee_are_negative(client):
    post(client, amount="100.00", external_id="d")
    w = post(client, type="withdrawal", amount="30.00", external_id="w").json()["entry"]
    f = post(client, type="fee", amount="1.50", external_id="f").json()["entry"]
    assert (w["amount_minor"], f["amount_minor"]) == (-3000, -150)


def test_overdraft_is_rejected_and_nothing_is_written(client, conn):
    post(client, amount="50.00", external_id="d")
    r = post(client, type="withdrawal", amount="50.01", external_id="w")
    assert r.status_code == 422
    assert "insufficient funds" in r.json()["detail"]
    assert conn.execute("SELECT COUNT(*) FROM entries").fetchone()[0] == 1


def test_balances_are_per_currency(client):
    post(client, amount="100.00", currency="EUR", external_id="d")
    r = post(client, type="withdrawal", amount="1.00", currency="USD", external_id="w")
    assert r.status_code == 422


def test_retry_with_same_external_id_is_idempotent(client, conn):
    first = post(client, external_id="custodian-77")
    again = post(client, external_id="custodian-77")
    assert first.status_code == 201 and again.status_code == 200
    assert again.json()["status"] == "duplicate"
    assert again.json()["entry"]["id"] == first.json()["entry"]["id"]
    assert conn.execute("SELECT COUNT(*) FROM entries").fetchone()[0] == 1


def test_same_external_id_with_different_details_conflicts(client):
    post(client, amount="100.00", external_id="custodian-77")
    r = post(client, amount="999.00", external_id="custodian-77")
    assert r.status_code == 409


def test_lookalike_is_accepted_with_warning(client):
    post(client, type="deposit", amount="100.00", external_id="a")
    post(client, type="fee", amount="25.00", external_id="fee-1")
    r = post(client, type="fee", amount="25.00", external_id="fee-2")
    assert r.status_code == 201
    assert r.json()["warnings"][0].startswith("possible_duplicate")


@pytest.mark.parametrize(
    "fields",
    [
        {"effective_date": "2999-01-01"},
        {"amount": "-5.00"},
        {"amount": 12.5},
        {"currency": "XYZ"},
        {"amount": "1.001"},
        {"client_ref": "bad ref!"},
        {"type": "bonus"},
        {"external_id": ""},
        {"unexpected": "field"},
    ],
)
def test_bad_input_is_rejected(client, conn, fields):
    r = post(client, **fields)
    assert r.status_code == 422
    assert conn.execute("SELECT COUNT(*) FROM entries").fetchone()[0] == 0


def test_missing_field_is_rejected(client):
    r = client.post("/v1/entries", json={"client_ref": "C-1"}, headers={"X-API-Key": "nb-writer-key"})
    assert r.status_code == 422


def test_creation_is_audited_in_same_transaction(client, conn):
    entry_id = post(client, external_id="x").json()["entry"]["id"]
    row = conn.execute("SELECT * FROM audit_events WHERE entity_id = ?", (entry_id,)).fetchone()
    assert row["action"] == "entry.created" and row["actor"] == "northbridge-advisor"
    assert json.loads(row["detail"])["external_id"] == "x"


def test_rejected_write_leaves_no_audit_event(client, conn):
    post(client, type="withdrawal", amount="1.00", external_id="w")
    assert conn.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0] == 0
