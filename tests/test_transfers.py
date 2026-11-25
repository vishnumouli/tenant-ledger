import pytest

from tests.conftest import HB_WRITER, NB_WRITER
from tests.helpers import post


def transfer(client, headers=NB_WRITER, **fields):
    body = {"from_client": "C-1", "to_client": "C-2", "amount": "40.00", "currency": "USD",
            "effective_date": "2026-01-20", "external_id": "t-1", **fields}
    return client.post("/v1/transfers", json=body, headers=headers)


def amount(client, ref, headers=NB_WRITER):
    return client.get(f"/v1/clients/{ref}/balance", headers=headers).json()["balances"][0]["amount"]


def test_transfer_moves_money_with_two_linked_entries(client):
    post(client, client_ref="C-1", amount="100.00", external_id="d")
    r = transfer(client)
    assert r.status_code == 201
    legs = r.json()["entries"]
    assert [(e["client_ref"], e["type"], e["amount"]) for e in legs] == [
        ("C-1", "transfer_out", "-40.00"),
        ("C-2", "transfer_in", "40.00"),
    ]
    assert legs[0]["transfer_id"] == legs[1]["transfer_id"] == r.json()["transfer_id"]
    assert (amount(client, "C-1"), amount(client, "C-2")) == ("60.00", "40.00")


def test_transfer_without_funds_writes_neither_leg(client, conn):
    post(client, client_ref="C-1", amount="10.00", external_id="d")
    assert transfer(client).status_code == 422
    assert conn.execute("SELECT COUNT(*) FROM entries WHERE transfer_id IS NOT NULL").fetchone()[0] == 0


def test_transfer_retry_is_idempotent(client, conn):
    post(client, client_ref="C-1", amount="100.00", external_id="d")
    first = transfer(client)
    again = transfer(client)
    assert again.status_code == 200 and again.json()["status"] == "duplicate"
    assert again.json()["transfer_id"] == first.json()["transfer_id"]
    assert amount(client, "C-1") == "60.00"


def test_transfer_reusing_external_id_with_other_details_conflicts(client):
    post(client, client_ref="C-1", amount="100.00", external_id="d")
    transfer(client)
    assert transfer(client, amount="41.00").status_code == 409
    assert transfer(client, external_id="d").status_code == 409


def test_transfer_to_self_is_rejected(client):
    assert transfer(client, to_client="C-1").status_code == 422


def test_transfer_cannot_reach_into_another_firm(client):
    post(client, client_ref="C-1", amount="100.00", external_id="d")
    r = transfer(client, headers=HB_WRITER)
    assert r.status_code == 422
    assert amount(client, "C-1") == "100.00"


@pytest.mark.parametrize("fields", [{"amount": "0"}, {"currency": "XYZ"}, {"effective_date": "2999-01-01"}])
def test_bad_transfer_input_is_rejected(client, fields):
    post(client, client_ref="C-1", amount="100.00", external_id="d")
    assert transfer(client, **fields).status_code == 422
