from tests.conftest import NB_WRITER


def entry(client_ref="C-1", type="deposit", amount="100.00", currency="USD",
          effective_date="2026-01-15", external_id="ext-1", **extra):
    return {"client_ref": client_ref, "type": type, "amount": amount, "currency": currency,
            "effective_date": effective_date, "external_id": external_id, **extra}


def post(client, headers=NB_WRITER, **fields):
    return client.post("/v1/entries", json=entry(**fields), headers=headers)
