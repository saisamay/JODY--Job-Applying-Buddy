# JODY — Your AI Job Applying Buddy

The public JODY landing page lets visitors explore sample jobs and an interactive product preview. The private workspace displays the owner’s saved jobs, trust evaluations, applications, resumes, evidence sources, approvals and activity. Local manual intake, PDF management, qualification comparisons, settings and the global pause control use the authenticated API. Public search results and sample evaluations carry fixture labels.

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

Open the [landing page](http://127.0.0.1:3000/) or [sign in](http://127.0.0.1:3000/signin) with JODY_OWNER_KEY from your local .env to open the [private workspace](http://127.0.0.1:3000/workspace). The runner starts PostgreSQL 16 with pgvector and Redis, applies Alembic migrations, checks broker connectivity and launches FastAPI and Next.js on loopback. The web server calls FastAPI server-side using API_BASE_URL. The browser receives an HTTP-only, same-site session cookie. The API stores a hash of the expiring token. Source URLs are retained as text and opened only at the owner's request.

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

Run the production build with the development web server stopped. Run the browser smoke against a disposable local stack. It exercises public search, signs in with the configured owner key, visits all twelve workspace views at five widths, checks accessibility, toggles pause, saves a synthetic job, compares it, manages a temporary PDF and edits a temporary blocklist entry. For visual captures, point WEB_BASE_URL at a synthetic QA stack and set both JODY_SYNTHETIC_WORKSPACE=1 and JODY_UI_CAPTURE_DIR to an output directory. [Screenshot gallery](docs/screenshots/ui/README.md) Use `npx playwright install chromium` once and then `npm run test:browser`, or set CHROME_BIN to an installed Chrome executable. Python integration tests create a uniquely named database, run migrations, exercise the real dependencies, then remove only that database. CI runs these checks with disposable Compose volumes on an Ubuntu runner. Format changed sources with `ruff format` and `npx prettier --write`.

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

## Candidate profile and onboarding

Use the server-side `candidateApi` in apps/web/lib/api.ts and its generated OpenAPI types in packages/shared/api.d.ts. All candidate routes use the existing private session. Read `GET /api/v1/candidate` for the current revision, editable fields, provenance, pending suggestions, resume metadata, current permissions and eight ordered onboarding steps. Existing clients can continue to use `GET /api/v1/profile`.

| Operation under /api/v1/candidate | Use |
|---|---|
| PATCH the base path | Send revision and fields. Omitted fields stay unchanged. Explicit null clears an optional field. Saving a field marks it user-provided and invalidates its previous verification. |
| PATCH /suggestions | Save or dismiss a proposed field with origin user_provided or inferred. To accept, submit the chosen value through the profile edit. Suggestions alone never supply application answers. |
| POST /review | Review the entire current value of one field and record its supporting evidence reference. This records the owner's verification at that revision. |
| POST /onboarding | Submit revision, step and status. Basic identity, permissions review and final confirmation require explicit completion. The other five sections can be skipped and revisited. Relevant edits reopen the affected step and final confirmation. |
| POST /resumes | Send a raw application/pdf body with a revision query parameter. Pass the percent-encoded label and optional role in X-Resume-Label and X-Resume-Role headers. Stores up to 20 PDFs per owner, each at most 5 MiB. |
| GET, PATCH or DELETE /resumes/{id} | Download as an attachment, edit the role/label, or remove an upload. DELETE takes revision in the query. Uploads are private source documents. The system checks size and PDF boundary markers and does not extract or certify their claims. |
| POST /application-preview | Pass required field names, optional resume_id and include_portfolio. The response contains answers and clarification requests. Qualification fields require owner review. Unknown or missing answers stay unanswered. The special field resume prompts for a selection if none was supplied. |

Use a UUID Idempotency-Key on mutations. Keep the same key for a retry of the same command. Reload after a 409 revision conflict. The preview is read-only. The existing PATCH /api/v1/profile/settings endpoint handles permission changes. Re-read the candidate after changing permissions. Onboarding confirmation and account-level permissions never authorize sending an email or submitting an application. Those operations still require separate approval for the exact destination and content.

Name, email and public profile links keep their original database columns. Additional personal fields, pending suggestions, evidence notes and resume bytes use authenticated encryption with user-bound context. Resume lookup, download and mutation also enforce database row-level security. Audits and command receipts contain revision/ID metadata. The migration neither seeds real personal information nor imports unverifiable claims from opaque legacy vault data.

For the private Vercel and Render preview, see the [deployment runbook and environment checklist](docs/PRIVATE_PREVIEW.md).
