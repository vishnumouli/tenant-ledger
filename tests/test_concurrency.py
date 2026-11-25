import threading
from concurrent.futures import ThreadPoolExecutor

from app import db, ledger
from app.auth import Caller
from app.schemas import EntryIn

CALLER = Caller(firm_id="northbridge", role="writer", actor="test")
THREADS = 10


def make(type, amount, external_id):
    return EntryIn(client_ref="C-1", type=type, amount=amount, currency="USD",
                   effective_date="2026-01-15", external_id=external_id)


def run_in_parallel(fn):
    """Each thread gets its own connection; the barrier releases them all at the same instant."""
    barrier = threading.Barrier(THREADS)

    def worker(i):
        conn = db.connect()
        try:
            barrier.wait()
            return fn(conn, i)
        finally:
            conn.close()

    with ThreadPoolExecutor(THREADS) as pool:
        return list(pool.map(worker, range(THREADS)))


def test_parallel_withdrawals_never_overdraw(conn):
    ledger.post_entry(conn, CALLER, make("deposit", "100.00", "dep"))

    def withdraw(c, i):
        try:
            ledger.post_entry(c, CALLER, make("withdrawal", "30.00", f"w-{i}"))
            return "ok"
        except ledger.Rejected:
            return "rejected"

    results = run_in_parallel(withdraw)
    assert results.count("ok") == 3
    assert results.count("rejected") == THREADS - 3
    assert ledger.current_balance(conn, "northbridge", "C-1", "USD") == 1000


def test_parallel_resends_create_exactly_one_entry(conn):
    results = run_in_parallel(lambda c, i: ledger.post_entry(c, CALLER, make("deposit", "100.00", "same"))[1])
    assert results.count("created") == 1
    assert results.count("duplicate") == THREADS - 1
    assert conn.execute("SELECT COUNT(*) FROM entries").fetchone()[0] == 1
