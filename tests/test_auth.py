import pytest

from tests.conftest import HB_WRITER, NB_SUPPORT


@pytest.mark.parametrize("headers", [{}, {"X-API-Key": "not-a-real-key"}])
def test_missing_or_unknown_key_is_rejected(client, headers):
    assert client.get("/v1/me", headers=headers).status_code == 401


def test_key_resolves_firm_and_role(client):
    assert client.get("/v1/me", headers=HB_WRITER).json() == {"firm_id": "harbor", "role": "writer"}
    assert client.get("/v1/me", headers=NB_SUPPORT).json() == {"firm_id": "northbridge", "role": "support"}
