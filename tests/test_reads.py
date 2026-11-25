from tests.conftest import HB_WRITER, NB_WRITER
from tests.helpers import post


def balance(client, ref="C-1", headers=NB_WRITER, **params):
    return client.get(f"/v1/clients/{ref}/balance", params=params, headers=headers)


def test_balance_as_of_excludes_later_entries(client):
    post(client, amount="100.00", effective_date="2026-03-31", external_id="q1")
    post(client, amount="50.00", effective_date="2026-04-01", external_id="q2")
    post(client, type="withdrawal", amount="20.00", effective_date="2026-06-30", external_id="w")

    q1 = balance(client, as_of="2026-03-31").json()["balances"]
    now = balance(client).json()["balances"]
    assert q1 == [{"currency": "USD", "amount": "100.00", "amount_minor": 10000}]
    assert now == [{"currency": "USD", "amount": "130.00", "amount_minor": 13000}]


def test_balance_is_reported_per_currency_never_mixed(client):
    post(client, amount="10.00", currency="USD", external_id="u")
    post(client, amount="1000", currency="JPY", external_id="j")
    got = {b["currency"]: b["amount"] for b in balance(client).json()["balances"]}
    assert got == {"JPY": "1000", "USD": "10.00"}


def test_entries_filtered_by_date_range(client):
    post(client, effective_date="2026-01-10", external_id="a")
    post(client, effective_date="2026-02-10", external_id="b")
    post(client, effective_date="2026-03-10", external_id="c")
    r = client.get("/v1/clients/C-1/entries", params={"from": "2026-02-01", "to": "2026-02-28"}, headers=NB_WRITER)
    assert [e["external_id"] for e in r.json()["entries"]] == ["b"]


def test_unknown_client_is_404(client):
    assert balance(client, ref="nobody").status_code == 404


def test_other_firm_cannot_see_client(client):
    post(client, client_ref="NB-SECRET", external_id="x")
    assert balance(client, ref="NB-SECRET", headers=HB_WRITER).status_code == 404
    assert client.get("/v1/clients/NB-SECRET/entries", headers=HB_WRITER).status_code == 404


def test_same_client_ref_in_two_firms_stays_separate(client):
    post(client, client_ref="C-1", amount="100.00", external_id="same-id")
    post(client, headers=HB_WRITER, client_ref="C-1", amount="5.00", external_id="same-id")
    assert balance(client).json()["balances"][0]["amount"] == "100.00"
    assert balance(client, headers=HB_WRITER).json()["balances"][0]["amount"] == "5.00"


def test_other_firm_cannot_spend_client_money(client):
    post(client, client_ref="C-1", amount="100.00", external_id="d")
    r = post(client, headers=HB_WRITER, client_ref="C-1", type="withdrawal", amount="1.00", external_id="w")
    assert r.status_code == 422
