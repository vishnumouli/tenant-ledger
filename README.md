# Tenant Ledger
Multi-tenant money-movement ledger API (FastAPI + SQLite). Requires [uv](https://docs.astral.sh/uv/), which installs Python 3.12 itself.
Run: `uv run uvicorn app.main:app`, then open http://127.0.0.1:8000/docs. Send header `X-API-Key`: `nb-writer-key`, `nb-support-key`, `hb-writer-key` or `hb-support-key`.
Test: `uv run pytest`
