from tests.conftest import NB_WRITER
from tests.helpers import entry

FILE = [
    entry(external_id="r0", amount="100.00"),
    entry(external_id="r1", amount="-5.00"),
    entry(external_id="r2", currency="XYZ"),
    entry(external_id="r3", effective_date="2999-01-01"),
    {"client_ref": "C-1", "type": "deposit"},
    entry(external_id="r5", type="withdrawal", amount="40.00"),
    entry(external_id="r6", type="withdrawal", amount="500.00"),
    "not even an object",
]


def run_import(client, rows):
    return client.post("/v1/imports", json={"rows": rows}, headers=NB_WRITER)


def balance(client):
    return client.get("/v1/clients/C-1/balance", headers=NB_WRITER).json()["balances"][0]["amount"]


def test_bad_rows_do_not_block_good_rows(client):
    r = run_import(client, FILE)
    assert r.status_code == 200
    statuses = [row["status"] for row in r.json()["results"]]
    assert statuses == ["created", "rejected", "rejected", "rejected", "rejected", "created", "rejected", "rejected"]
    assert r.json()["summary"] == {"created": 2, "duplicate": 0, "rejected": 6}
    assert all(row["errors"] for row in r.json()["results"] if row["status"] == "rejected")
    assert balance(client) == "60.00"


def test_rows_apply_in_order_so_later_rows_can_spend_earlier_deposits(client):
    r = run_import(client, [entry(external_id="d", amount="10.00"), entry(external_id="w", type="withdrawal", amount="10.00")])
    assert r.json()["summary"]["created"] == 2


def test_resending_the_whole_file_changes_nothing(client, conn):
    run_import(client, FILE)
    again = run_import(client, FILE)
    assert again.json()["summary"] == {"created": 0, "duplicate": 2, "rejected": 6}
    assert balance(client) == "60.00"
    assert conn.execute("SELECT COUNT(*) FROM entries").fetchone()[0] == 2


def test_import_is_audited(client, conn):
    run_import(client, FILE)
    actions = [r[0] for r in conn.execute("SELECT action FROM audit_events ORDER BY id")]
    assert actions == ["entry.created", "entry.created", "import.completed"]


def test_empty_and_oversized_files_are_rejected(client):
    assert run_import(client, []).status_code == 422
    assert run_import(client, [entry()] * 1001).status_code == 422
