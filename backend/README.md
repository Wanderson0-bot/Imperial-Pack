# Imperial Pack FastAPI backend

The repository root remains the Vite frontend. This backend uses FastAPI, SQLAlchemy 2 and PostgreSQL through the standard `DATABASE_URL` setting. It is an internal single-company application for Imperial Pack: there are no organizations, memberships, tenant IDs, or organization-based RLS policies. `customers.establishment` remains the customer's business name, not a tenant boundary. The backend does not substitute SQLite or an in-memory database when configuration is absent: database-backed endpoints return 503 until configured.

## Local setup

1. Create a PostgreSQL database and copy `.env.example` to `backend/.env`.
2. Set a cryptographically random `SECRET_KEY` and the database credentials.
3. Install `python -m pip install -r requirements.txt`.
4. Inspect the current database revision with `alembic -c alembic.ini current` and the available revisions with `alembic -c alembic.ini history`. After a logical backup and schema review, apply the reviewed single-company revision with `alembic -c alembic.ini upgrade 0007_single_company_indexes`. This revision path creates the missing finance tables and their integrity controls; it does not add organizations or RLS.
5. To create the first administrator through the login screen, set `INITIAL_ADMIN_EMAIL` to the one authorized address before starting the API. Registration is available only while the users table is empty and only for that address. Alternatively, bootstrap two administrators with `python -m app.auth.bootstrap admin1@example.com admin2@example.com`; passwords are prompted and hashed. Choose one bootstrap path.
6. Start with `uvicorn app.main:app --reload` from this directory.

Google OAuth is enabled only when client ID, secret, redirect URI, and the explicit authorized-email allowlist are configured. OAuth never creates an account automatically.

For an HTTPS frontend and API on different sites, set `COOKIE_SAMESITE=none` and `COOKIE_SECURE=true`; keep `FRONTEND_ORIGINS` limited to the exact trusted frontend origins. Same-site/local development can use `COOKIE_SAMESITE=lax` and `COOKIE_SECURE=false`. `/health` reports `database_connected` after executing `SELECT 1`. Alembic requires `DATABASE_URL` and does not fall back to localhost.

Production settings require a `SECRET_KEY` of at least 32 UTF-8 bytes and secure cookies. The API is not production-ready until deployment secrets, PostgreSQL, HTTPS, backup policy, and the authorized email allowlist are configured and reviewed.

## PostgreSQL integrity tests

The default backend suite uses isolated SQLite databases for fast regression checks. PostgreSQL locking and concurrent idempotency checks are in `tests/test_postgres_integrity.py`; run them with `TEST_POSTGRES_URL` pointing to a dedicated disposable test database:

```powershell
$env:TEST_POSTGRES_URL = "postgresql+psycopg://..."
python -m pytest -q tests/test_postgres_integrity.py
```

The test fixture creates and drops a uniquely named `ip_integrity_*` schema and requires permission to create/drop schemas. Point `TEST_POSTGRES_URL` only at a dedicated disposable PostgreSQL test database; never use the production database. Without this variable, PostgreSQL integration cases are skipped and SQLite results do not certify PostgreSQL concurrency.

## Operational alerts and opportunities

`GET /api/alerts` and `GET /api/opportunities` refresh persistent records from inventory balances, pending financial titles, non-cancelled customer orders, and active partner history. Source visibility follows the existing `inventory:read`, `finance:read`, `customers:read`, and `partners:read` permissions. Status changes require a matching write permission or the dedicated `alerts:manage` / `opportunities:manage` permission and are audited.

Rules use recorded facts only. Zero stock is high priority; positive stock below the configured minimum is medium. Financial titles overdue by calendar date are high priority; titles due within seven days are medium. Customer and partner replenishment windows use their observed mean purchase intervals and open three days before the expected date. A frequency change requires at least four orders and a latest interval at least 50% shorter or longer than the preceding intervals' mean. A partner product-quantity pattern change requires at least three recorded purchases and a latest quantity at least 50% above or below the previous purchases' mean. Product demand opportunities compare quantities in the last 30 days with the prior 30 days and require an increase. Replenishment is omitted when customer history is `insufficient_data`.

Priority is categorical and rule-based: overdue purchase patterns become high only at 1.5 times the observed interval; frequency drops become high at twice the prior interval mean; partner quantity changes become high when the latest quantity is at least twice or at most half of its previous mean. Event keys are unique per rule and entity. Repeated reads update an active record instead of inserting duplicates; a cleared event is closed and can be reopened if it recurs.
