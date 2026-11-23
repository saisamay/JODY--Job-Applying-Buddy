# JODY — Your AI Job Applying Buddy

JODY currently provides a private local workspace for manual job intake. Sign in, paste a vacancy, optionally keep its source URL and reload to see the saved record. Saving the same description and URL again is safe. The workspace shows the most recent 100 entries. No job-board accounts, model keys or paid services are needed.

## Run on Ubuntu 24.04

Install Git, curl, Python 3.12 with venv support, Node/npm (the tested Node version is in .nvmrc), and Docker Engine with the Compose plugin. Verify `docker info` works for your account. If you already use nvm, run `nvm install && nvm use` from the repository root. [Docker Engine for Ubuntu](https://docs.docker.com/engine/install/ubuntu/)

From the repository root, install dependencies and create the local environment once.

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r requirements-dev.lock
npm ci
python3 infra/init-env.py
```

The last command creates a mode-0600 .env from .env.example with separate migration/runtime database passwords, a private owner access key and a 256-bit encryption key. On a phase 1A checkout, run `python3 infra/init-env.py --upgrade` once to append missing keys while retaining existing values. Keep the generated values local. To use your own settings, edit .env as a shell-compatible file. Changing the database password in .env after volume initialization also requires updating the database role password.

```bash
./infra/run-local.sh
```

Open [the local workspace](http://127.0.0.1:3000) and enter the value of JODY_OWNER_KEY from your local .env. The runner starts PostgreSQL 16 with pgvector and Redis, applies Alembic migrations, checks broker connectivity and launches FastAPI and Next.js on loopback. The web server calls FastAPI server-side using API_BASE_URL. The browser receives an HTTP-only, same-site session cookie. The API stores a hash of the expiring token. Source URLs are retained as text and opened only at the owner's request.

Use Ctrl-C to stop the web and API processes. Stop the data services with `docker compose --env-file .env -f infra/compose.yaml stop`. Their named volumes preserve saved jobs. To use the compiled frontend, run `npm run build` followed by `JODY_WEB_MODE=start ./infra/run-local.sh`.

### Existing local services

If Docker is unavailable, supply DATABASE_URL (SQLAlchemy postgresql+psycopg URL) and REDIS_URL in .env for a dedicated local database and broker. The migration account must be able to provision the restricted application role, create tables and install the vector extension, or an administrator can install vector in that database first. Set `JODY_USE_EXISTING_SERVICES=1` when invoking the runner. The integration tests additionally need a role that can create disposable test databases with vector. Use a local development role. The standard Compose configuration supplies these permissions.

### Check the running stack

| Endpoint or command | Expected result |
|---|---|
| GET http://127.0.0.1:8000/health/live | 200 while the API process runs |
| GET http://127.0.0.1:8000/health/ready | 200 with postgres and redis true after migration, or 503 with dependency status |
| http://127.0.0.1:8000/docs | Interactive FastAPI contract |
| GET /api/v1/jobs | 401 without a session, owner-scoped list with a session |

Readiness checks connectivity, the expected migration and the vector extension. Each request has an X-Request-ID and a JSON log entry with route, status and duration. If readiness fails, check the selected database/ports, migrations and Redis. Defaults use host ports 55432 and 56379 to coexist with common system installations. Keep both application ports 3000 and 8000 free. The worker supports a connectivity check and one inert probe task per invocation. The private operator can pause all task dispatch from the dashboard.

## Development and verification

```bash
source .venv/bin/activate
set -a; source .env; set +a
export PYTHONPATH="$PWD/apps/api"
ruff check apps/api apps/worker tests infra
ruff format --check apps/api apps/worker tests infra
mypy
pytest
npm run contracts
git diff --exit-code -- packages/shared/api.d.ts
npm run lint
npm run typecheck
npm run format:check
npm run build
```

Run the production build with the development web server stopped. Run the browser smoke against a disposable local stack. It signs in with the configured owner key and adds one synthetic entry. Use `npx playwright install chromium` once and then `npm run test:browser`, or set CHROME_BIN to an installed Chrome executable. Python integration tests create a uniquely named database, run migrations, exercise the real dependencies, then remove only that database. CI runs these checks with disposable Compose volumes on an Ubuntu runner. Format changed sources with `ruff format` and `npx prettier --write`.

| Location | Responsibility |
|---|---|
| apps/web | Next.js App Router, accessible forms, Tailwind styles and typed server-side API client |
| apps/api | FastAPI, Pydantic contracts, SQLAlchemy Core and Alembic migrations |
| apps/worker | Broker connectivity and one-shot local probe consumer |
| packages/shared | TypeScript definitions generated from FastAPI OpenAPI |
| infra | Local services, environment initialization and application runner |
| tests | API, database, broker and browser regression tests |
| docs | Product contract, architecture and phase handoff |

[Build contract](docs/BUILD_CONTRACT.md) · [Progress](docs/PROGRESS.md) · [Next step](docs/NEXT_STEP.md)

## Secure data foundation

Alembic revision `0002_secure_data` upgrades the existing tables, preserves IDs and session digests, and backfills profiles, settings and source references. Back up the database before migration. Downgrading discards phase 1B domain records. Use a backup for a data-preserving rollback. Legacy identities receive a reserved `@private.invalid` address until configured. Tests seed only the disposable database using tests/fixtures.

The migration login owns DDL. The startup script provisions a separate PostgreSQL login without superuser, role creation or row-security bypass and removes migration credentials from the API process. Backend code derives identity from a live session and sets it only for the current transaction. The runtime checks that tenant row policies apply at startup. Applications sharing the database must never expose this trusted backend login to clients.

Integration credentials use AES-256-GCM with a fresh nonce and user/provider-bound authenticated data. The API provides store/remove operations and returns only provider metadata. Keep JODY_ENCRYPTION_KEY in a private secret store and back it up separately from the database. Replacing the key requires an offline re-encryption and idempotency-receipt migration. Removing a stored credential does not revoke a token at the provider.

All routes below require a live bearer session. Mutations in this table require a UUID `Idempotency-Key` header. Repeating an identical command returns the original receipt. A different command using the same key returns 409. The manual intake endpoint retains its existing content-based deduplication.

| Route | Effect |
|---|---|
| GET /api/v1/profile | Read candidate profile, settings and stored provider names. |
| PATCH /api/v1/profile/settings | Validate and update the supplied preferences. Outbound delivery, scam Trash and rejection archive default to false. |
| GET or POST /api/v1/system/kill-switch | Read the global gate or set an explicit paused boolean. Only the private operator may change it. Starts paused. |
| PUT or DELETE /api/v1/integrations/{provider} | Store an encrypted credential or remove it. All provider workflows remain disconnected. |
| POST /api/v1/tasks/probe and GET /api/v1/tasks/{id} | Record one inert probe and inspect its persisted status. |
| GET /api/v1/audit | Read the latest 100 tenant events. The runtime role can append but cannot alter audit history. |

With the virtual environment and .env loaded and PYTHONPATH set as above, run `python apps/worker/run_once.py` to publish/consume one eligible probe. Pending PostgreSQL rows survive queue loss and are eligible for republication after ten seconds. Worker execution and the administrator's pause serialize on the singleton gate row. While paused, manual preparation and reads remain available. Resuming the worker never enables a delivery channel.
