from fastapi import FastAPI

app = FastAPI(title="Tenant Ledger")


@app.get("/health")
def health():
    return {"status": "ok"}
