# JODY progress

## Phase 0 · Planning checkpoint · 2026-11-23

| Item | Observed state |
|---|---|
| Starting point | Empty checkout and unborn main. The authorized public GitHub origin initially advertised no refs. No source, existing test command, CI workflow, environment template or deployment manifest was present. |
| Source | Recovered the formerly titled AutoApply AI PDF from the owner's local Downloads, verified the title and all eight printed pages and copied it locally to docs/JODY_PRD.pdf. SHA-256 and the truncated DDL boundary are in the build contract. Only the seven planning documents are intended for this public Git commit. |
| Planning output | Contract, 55-row requirements matrix, component and route design, private MVP and production roadmap, cost plan and two handoff ledgers. All application work is outstanding. |
| Local tooling | Git, Node/npm, Docker CLI, PostgreSQL client and PDF extraction tools found. Tectonic, Redis server and Vercel/Render CLIs were absent from PATH. Runtime services and Docker daemon have not been qualified. |
| GitHub | Public repo metadata readable, local HTTPS Git credentials and gh login unavailable. Existing SSH agent successfully authenticated to GitHub on port 443. Authorized target is saisamay/JODY--Job-Applying-Buddy, branch main. |
| Design and portfolio | Figma screenshot returned for node 131:1408. Architecture records observed layout cues. The portfolio URL resolved, but the web reader returned no extractable text. No candidate fact was imported or verified. |
| Integrations | GitHub, Figma, Gmail and Render connector tools are exposed to the development session. No personal mailbox data was accessed. Render reported no selected workspace. No Vercel connector or project link was found. Telegram, resume Git, portal access and runtime credentials are unconfigured in the repository. |
| Deployment evidence | Initial public GitHub checks found zero workflows and deployments. No application or provider target is defined in this checkout. External account-level links are unverified. No infrastructure was provisioned. |
| Application tests | No application exists at this checkpoint. Zero runtime features have been verified. |

## Verification record

A local Python validation against the original PDF and Markdown passed. It found seven documents, 16 resolving local links, 55 unique IDs with six populated fields each, valid priority/status values and no undefined requirement references. PDF text extraction matched eight numbered footers and the source SHA-256. Parsing page 7 and comparing method/path pairs against the architecture matched all 18. The screenshot and rendered page 6 were also visually inspected.

For a repeat check, use `sha256sum docs/JODY_PRD.pdf`, `pdfinfo docs/JODY_PRD.pdf`, and `pdftotext -f 7 -l 7 -layout docs/JODY_PRD.pdf -` to compare the source ledger. Run `git diff --cached --check` and inspect staged paths and secret signatures before committing. The phase report supplies the SHA and post-push observations.

Use `git log -1 --format='%H %s' -- docs/PROGRESS.md` to identify the commit containing this checkpoint. The current commit cannot embed its own SHA. For each later phase append the prior verified SHA, current requirements and test commands/results, any real-provider validation, push/deploy evidence or blockers, and the next action. Keep phase 0's baseline as historical evidence.

## Outstanding gates

The next development slice uses fixtures and can run locally after the owner starts implementation. Real candidate evidence, resume template, provider entitlements, retention choices and hosting budget belong to later gates. Hosting requires an identified Vercel project and confirmed Render workspace/service mapping with deployment read/trigger access. Any billable addition needs a separately approved estimate. [Next action](NEXT_STEP.md)

## Phase 1A · Local foundation and manual intake · 2026-11-23

**Starting revision** was aea642122d4b0ccb90b4fa4de322c8999283b647 on main. The owner selected FastAPI, SQLAlchemy and Alembic for the backend. This supersedes the provisional Node backend choice in phase 0.

| Area | Delivered and observed locally |
|---|---|
| Workspace | Next.js App Router, TypeScript, Tailwind, labeled sign-in and intake forms, keyboard focus, accessible feedback and saved jobs list. Next server actions call FastAPI using types generated from its OpenAPI document. |
| API and persistence | Closed owner login with expiring hashed sessions, scoped reads and atomic manual intake. Owner, job, observation and event writes use a PostgreSQL migration. Concurrent identical requests produce one job, observation and event. |
| Infrastructure | PostgreSQL 16 with vector, Redis-compatible broker, Alembic, structured request logs, sanitized errors, live and ready probes. A worker command checks the broker. No job automation or external providers were enabled. |
| Developer workflow | Local-only environment template and initializer, dependency locks, lint/format/type settings, Ubuntu startup script and runbook, GitHub Actions workflow with Compose and browser smoke. |
| Database tests | Real pgvector distance query, migration upgrade/check/downgrade/upgrade, dependency-failure readiness, invalid inputs, session revocation on sign-out, concurrent intake, cross-owner denial and fresh API lifespan persistence. Nine pytest tests passed. |
| Browser tests | Headless Chrome passed owner login, save, reload, duplicate retry and sign-out through the actual frontend and API. Passed once against the optimized build and again against the development server after restarting both processes with the same database. |
| Other gates | Ruff lint/format, strict mypy, ESLint, Prettier, TypeScript, OpenAPI type generation and optimized Next build. Exact commands are in the runbook and CI workflow. |

**Local environment difference.** Docker Compose configuration validation passed. The local account lacks permission to open the Docker socket. Equivalent user-owned PostgreSQL 16, pgvector and Redis 7 processes supplied the live services on loopback ports 55432 and 56379. The local stack uses synthetic data and a generated private .env. GitHub Actions independently started the Compose containers on Ubuntu and passed the full suite against them.

**Release boundary.** No Vercel project or Render service binding is in the checkout. No paid resource or hosted application is part of this phase. The authenticated intake slice contributes to the broader matrix rows. Future work includes database row-level security for hosted tenants, pipeline features, outbox and a real task consumer. The next slice is [the durable local outbox](NEXT_STEP.md). [Ubuntu runbook](../README.md)

**Published checkpoint.** Verified GitHub main contained implementation commit f5998b39fdf91d05b4b01b814286f5d7b25c8281. The Foundation run passed dependency installation, Compose startup, backend tests, contract regeneration, frontend checks, build and real browser round trip. GitHub reported zero deployments for that SHA. Additional local smoke verified keyboard sign-in, skip navigation and no horizontal overflow at a 375px viewport. [Passing CI run](https://github.com/saisamay/JODY--Job-Applying-Buddy/actions/runs/45109350483)
