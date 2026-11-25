# AI usage

**Tool:** Devin (Claude model) running inside T3 Code, used for the design discussion and to generate the code and tests.

## Key prompts
1. "Read this spec, grill me until we are on the same page, and plan the commits." This produced a 27-question design session (stack, money format, locking, idempotency, duplicates, corrections, roles, API, tests, commit plan and cut order) before any code was written.
2. "Go": implement the agreed plan commit by commit, with each feature's tests in the same commit.

## What I corrected or rejected
- Rejected floating-point money: amounts arrive as decimal strings and are stored as whole minor units, with decimals checked per currency (JPY has none).
- My first idea for concurrency was "lock the table". It was refined to SQLite `BEGIN IMMEDIATE` (the write lock is taken before the balance check). An in-process Python lock was rejected because it does not protect multiple server processes.
- Rejected SQLAlchemy (its SQLite driver manages transactions itself, which makes `BEGIN IMMEDIATE` awkward) and PostgreSQL (setup time inside one hour). Both are noted as the scale-up path.
- Rejected blocking look-alike duplicates, because two identical fees on one day can be real; they get a warning instead. Rejected cross-firm transfers.
- Checked that the concurrency tests are meaningful: weakening `BEGIN IMMEDIATE` to `BEGIN` makes both of them fail.

## Review
The design decisions are mine, made in the session above. The code is AI-generated against that design and was checked during the hour by the test suite and a manual curl smoke test of the running server. I did not review every line inside the hour; I am reviewing it line by line before the walkthrough.
