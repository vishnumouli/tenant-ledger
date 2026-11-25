from tests.conftest import HB_WRITER, NB_WRITER
from tests.helpers import post
from tests.test_transfers import transfer


def reverse(client, entry_id, headers=NB_WRITER, reason="keyed wrong amount"):
    return client.post(f"/v1/entries/{entry_id}/reversal", json={"reason": reason}, headers=headers)


def amount(client, ref="C-1", **params):
    r = client.get(f"/v1/clients/{ref}/balance", params=params, headers=NB_WRITER)
    return r.json()["balances"][0]["amount"]


def test_reversal_appends_opposite_entry_and_keeps_original(client, conn):
    wrong = post(client, amount="100.00", external_id="d").json()["entry"]
    r = reverse(client, wrong["id"])
    assert r.status_code == 201
    rev = r.json()["reversals"][0]
    assert (rev["type"], rev["amount"], rev["reverses_entry_id"], rev["memo"]) == (
        "reversal", "-100.00", wrong["id"], "keyed wrong amount")
    assert amount(client) == "0.00"
    original = conn.execute("SELECT amount_minor FROM entries WHERE id = ?", (wrong["id"],)).fetchone()
    assert original["amount_minor"] == 10000


def test_reversal_corrects_past_balances(client):
    post(client, amount="100.00", effective_date="2026-03-31", external_id="good")
    wrong = post(client, amount="900.00", effective_date="2026-03-15", external_id="typo").json()["entry"]
    assert amount(client, as_of="2026-03-31") == "1000.00"
    reverse(client, wrong["id"])
    assert amount(client, as_of="2026-03-31") == "100.00"


def test_entry_can_only_be_reversed_once(client):
    entry_id = post(client, external_id="d").json()["entry"]["id"]
    reverse(client, entry_id)
    assert reverse(client, entry_id).status_code == 409
    assert amount(client) == "0.00"


def test_reversal_cannot_be_reversed(client):
    entry_id = post(client, external_id="d").json()["entry"]["id"]
    rev_id = reverse(client, entry_id).json()["reversals"][0]["id"]
    assert reverse(client, rev_id).status_code == 409


def test_reversing_one_leg_reverses_whole_transfer(client):
    post(client, client_ref="C-1", amount="100.00", external_id="d")
    in_leg = transfer(client).json()["entries"][1]
    r = reverse(client, in_leg["id"])
    assert len(r.json()["reversals"]) == 2
    assert (amount(client, "C-1"), amount(client, "C-2")) == ("100.00", "0.00")


def test_reversing_a_spent_deposit_is_refused(client):
    dep = post(client, amount="100.00", external_id="d").json()["entry"]
    post(client, type="withdrawal", amount="80.00", external_id="w")
    r = reverse(client, dep["id"])
    assert r.status_code == 422 and "insufficient funds" in r.json()["detail"]


def test_reversing_a_withdrawal_restores_funds(client):
    post(client, amount="100.00", external_id="d")
    w = post(client, type="withdrawal", amount="80.00", external_id="w").json()["entry"]
    assert reverse(client, w["id"]).status_code == 201
    assert amount(client) == "100.00"


def test_other_firm_cannot_reverse(client):
    entry_id = post(client, external_id="d").json()["entry"]["id"]
    assert reverse(client, entry_id, headers=HB_WRITER).status_code == 404
    assert reverse(client, 99999).status_code == 404


def test_reason_is_required(client):
    entry_id = post(client, external_id="d").json()["entry"]["id"]
    assert reverse(client, entry_id, reason="").status_code == 422


def test_reversal_is_audited(client, conn):
    entry_id = post(client, external_id="d").json()["entry"]["id"]
    reverse(client, entry_id)
    row = conn.execute("SELECT * FROM audit_events WHERE action = 'entry.reversed'").fetchone()
    assert row["entity_id"] == entry_id and "keyed wrong amount" in row["detail"]
