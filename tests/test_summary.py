from tests.conftest import HB_WRITER, NB_SUPPORT, NB_WRITER
from tests.helpers import post
from tests.test_transfers import transfer


def summary(client, headers=NB_WRITER, **params):
    params = {"from": "2026-01", "to": "2026-02"} | params
    return client.get("/v1/clients/C-1/summary", params=params, headers=headers)


def test_monthly_inflows_outflows_fees_and_net(client):
    post(client, amount="1000.00", effective_date="2026-01-05", external_id="d1")
    post(client, type="withdrawal", amount="200.00", effective_date="2026-01-10", external_id="w1")
    post(client, type="fee", amount="10.00", effective_date="2026-01-31", external_id="f1")
    transfer(client, amount="50.00", effective_date="2026-02-01", external_id="t1")
    post(client, amount="5.00", effective_date="2026-03-01", external_id="outside-range")

    months = summary(client).json()["months"]
    assert months == [
        {"month": "2026-01", "currency": "USD", "inflows": "1000.00", "outflows": "200.00", "fees": "10.00", "net": "790.00"},
        {"month": "2026-02", "currency": "USD", "inflows": "0.00", "outflows": "50.00", "fees": "0.00", "net": "-50.00"},
    ]


def test_reversed_fee_reduces_fees_not_inflows(client):
    post(client, amount="100.00", effective_date="2026-01-05", external_id="d")
    fee = post(client, type="fee", amount="10.00", effective_date="2026-01-06", external_id="f").json()["entry"]
    client.post(f"/v1/entries/{fee['id']}/reversal", json={"reason": "fee waived"}, headers=NB_WRITER)
    jan = summary(client).json()["months"][0]
    assert (jan["inflows"], jan["fees"], jan["net"]) == ("100.00", "0.00", "100.00")


def test_currencies_are_summarised_separately(client):
    post(client, amount="10.00", currency="USD", effective_date="2026-01-05", external_id="u")
    post(client, amount="300", currency="JPY", effective_date="2026-01-05", external_id="j")
    assert [(m["currency"], m["net"]) for m in summary(client).json()["months"]] == [("JPY", "300"), ("USD", "10.00")]


def test_support_can_read_summary_other_firm_cannot(client):
    post(client, effective_date="2026-01-05", external_id="d")
    assert summary(client, headers=NB_SUPPORT).status_code == 200
    assert summary(client, headers=HB_WRITER).status_code == 404


def test_bad_month_is_rejected(client):
    post(client, effective_date="2026-01-05", external_id="d")
    assert summary(client, **{"from": "2026-13"}).status_code == 422
