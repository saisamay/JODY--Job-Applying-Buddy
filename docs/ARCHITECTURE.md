# JODY architecture

**Release boundary.** One authenticated owner can bring a job description, evaluate its risk, match reviewed experience, compile an application packet, review the exact revision and record the outcome. This vertical slice works on a laptop. Mobile alerts, live mail, optional permitted adapters and continuous hosting have independent acceptance gates. [Requirements matrix](REQUIREMENTS_MATRIX.md)

## Components and trust boundaries

```text
Owner browser → Next.js dashboard → same-origin API proxy → Python FastAPI /api/v1
Paired Telegram callback → authenticated webhook adapter → command handlers
Command handlers → PostgreSQL 16 + pgvector (domain records, approvals, outbox)
Outbox relay → Redis queue → Python workers → evidence / scoring / preparation
                                          ↘ isolated Tectonic → private artifact store
Approved action → dispatch worker → policy recheck → provider → receipt / reconciliation
Inbound provider event → verified adapter → normalize + correlate → timeline / alert
```

The owner selected FastAPI, SQLAlchemy and Alembic for phase 1. Use a Python API and separate future Python worker and scheduler entry points. Share typed contracts by generating TypeScript from FastAPI OpenAPI. Local Compose provides Postgres and Redis with persistent volumes. API and web processes run on loopback on the host. A private local directory holds artifacts by content hash. Production uses Vercel for web, Render for API and continuously running workers, private DB/queue connections and private durable object storage. Never persist artifacts on ephemeral service disks. Previews use synthetic tenants, fake providers and separate credentials. Production integrations live only behind the API and workers.

## Frontend

The supplied Figma node renders a charcoal hero, orange pill action, spacious light panels and a compact dashboard preview with a left rail. Use the dark header for owner and pause state, warm light panels for job evidence and one orange primary action for the current review. Reserve explicit text and icons for risk and blocked states. The screenshot establishes hierarchy and palette. Do not reuse furniture assets, mock counters or portfolio marketing copy. [Figma reference](https://www.figma.com/design/q4eJYb38nZQwHvXmNFeXrx/Panto---Furniture-Landing-Page-Design--Community-?node-id=131-1408)

| Screen | Main interaction |
|---|---|
| Pipeline | Filter by stage, trust or source. Add a URL or paste text. Show stage counts from records, attention queue, last sync and pause control. Mobile uses a grouped list. Poll incrementally after a cursor, with manual refresh and stale/offline indication. |
| Job review | Show requisition, duplicate sightings, risk evidence and missing checks. Approve preparation, skip or block with reason. Show matched facts, unsupported requirements and the original description. |
| Application packet | Side-by-side resume diff and extracted PDF preview, ATS components, letter, contact and form answers. A distinct action approves one version for one destination. Unknown answers, missing evidence and stale approvals have visible recovery actions. |
| Inbox and outreach | Linked thread timeline, proposed classifications, draft connection/rapport/follow-up and manual outcome controls. Show previous labels, recovery window and restore result. |
| Sources, evidence and settings | Review GitHub/portfolio evidence, select repositories, toggle allowed sources, edit blocklist and thresholds, pair/revoke integrations and inspect health. Portfolio content enters as unverified input. [Owner portfolio](https://saisamay.me/) |
| Audit and operations | Filter decisions, dispatches, provider receipts, mail changes and uncertain outcomes. Display actor, destination summary, revision and timestamps. Keep pause accessible on all private screens. |

Provide keyboard paths and visible focus for every action, labeled controls, status text independent of color, a readable PDF text alternative and version-conflict prompts. The browser receives authorized views and short-lived artifact access. Keep tokens, raw mail and vault data out of analytics and client persistence.

## Job lifecycle and gates

1. Ingest a permitted item. Store the normalized fields and source observation. Prefer verified ATS requisition ID or canonical employer application URL. Fallback uses normalized employer, role and location, with ambiguous matches queued for review. Preserve multiple openings and source deletions independently.
2. Check legitimacy before tailoring. Proposed initial rubric uses official vacancy link and employer identity, recruiter/domain corroboration, domain history and suspicious asks. Record per-check outcomes, source, freshness and missing data. A payment request or conflicting identity routes to review independent of numerical score. Owner confirmation is required to blocklist an entity. Tune weights and a borderline range on labeled fixtures before enabling auto-advance. A high score permits preparation only.
3. Index consented repo snapshots by owner, repo ID, path and commit. Normalize reviewable facts into claims. Evidence of a project's dependencies does not prove the owner's role. Owner reviews attribution, scope, dates and quantitative claims. Retrieval uses lexical ranking first and optional vector reranking. Retrieval selects candidate facts. A deterministic template can draft locally from approved claim IDs.
4. Freeze a manifest containing the job revision, template commit, claim IDs, field values and supporting excerpts. Render escaped text into approved templates. Compile with pinned compiler and cached bundles in an unprivileged isolated process with no network, shell escape or host mounts, bounded CPU, time, files and memory. Check PDF text extraction, fonts/layout and mandatory fields. Every material sentence or numerical assertion must have support. Free-text revisions require owner review.
5. Proposed ATS rubric scores four documented dimensions on a 0–100 scale with an initial equal weighting. Version the rubric, terms, extracted text and explanation. Treat the result as an internal compatibility estimate. Default threshold is 82, maximum two refinements, stop early on no improvement. Source/parse errors block approval. A below-target exception requires a recorded owner rationale; unsupported facts can never be overridden.
6. Generate immutable action intent covering sender, recipient or portal, exact text, answers and attachment hashes. Preparation, ATS exception, inbox mutation and dispatch are distinct permissions. A review screen or bound one-time callback records the authorized action and expiry. Revalidate the approval, revocation, caps, pause, blocklist, evidence freshness and packet at dispatch. An uncertain result enters reconciliation. Only a receipt or explicit owner-reported manual submission advances to applied.

Retain the source stage vocabulary for Kanban. Store job disposition, application attempts, contact sequence and email events separately. Changes to one dimension cannot erase another. Map an interview email to interview only after reliable correlation. Never downgrade an offer or reopen a blocked job because an older acknowledgment arrived.

## Relational design

Every tenant-owned table carries a non-null ownership key. Migration 0002 renames phase 1A owner_id and owners to user_id and users in place. The users row is the ownership root. Use UUIDs, UTC timestamptz, foreign keys, score checks (0–100), constrained statuses, unique (user_id, id) parents and composite tenant-aware foreign keys. Put owner scope in indexes, vector queries, queue keys, artifact namespaces and caches. Use row-level security with transaction-local identity, a runtime role without bypass privileges, and a separate migration role. Workers load scope from the persisted task. Public signup later adds identities and policies without changing the ownership key.

| Tables | Contents and invariants |
|---|---|
| users, identities, profile_versions, settings | Unique email and provider subject, name, GitHub/LinkedIn/portfolio references, active flag, timestamps, private vault, versioned settings, resume repo/branch/template. Unique verified Telegram chat mapping. Keep secret material out of profile projections. |
| integration_accounts, secret_envelopes, sync_cursors | Provider, scopes, revocation, health, quota window, encrypted credential plus nonce/tag/key version, last durable cursor. Unique provider account per owner. Keys supplied outside the DB. |
| sources, source_observations, jobs, job_events, blocked_entities | Source kind, allowlist, permission basis, external ID or digest, observation timestamps, canonical vacancy/dedupe key, trust and stage history. Unique observation and stable job key per owner. Block by typed company/domain/address plus reason. |
| risk_assessments, risk_checks | Immutable versioned score, ruleset, check-level reasons and uncertainty. Link the decision to an assessment version. |
| github_projects, evidence_items, claims, claim_evidence, embedding_chunks | Repo metadata, immutable revision/path, evidence hash, review state, ownership and source links. Version model and dimension per embedding index. Revocation invalidates dependent claims and unexecuted approvals. |
| applications, artifacts, artifact_claims, evaluations, answers | Unique owner/job/application intent, method, versioned packet, cover letter, LaTeX diff and PDF reference/hash. Track compiler/template/rubric versions, retries, question provenance and ATS exception. |
| contacts, outreach_steps, suppressions | Source, permitted channel, company relationship, opt-out, acceptance/reply state and due time. Unique sequence/step and one follow-up per sequence. |
| mail_events, mailbox_actions | Unique provider message/event ID, cursor, thread link, classification evidence, original labels, proposed/confirmed action, restore status and observed limitations. |
| action_intents, approvals, dispatch_attempts, audit_events | Canonical action hash, owner, destination, immutable version, expiry, actor and intent outcome. Single consumption of each approval. Append-only audit references encrypted snapshots under a retention policy. |
| tasks, outbox, provider_events | Unique operation key, user, due time, attempt, lease/fence, result or ambiguity. Inbox dedupes provider event IDs. Outbox rows commit atomically with domain state. |

Page 6 supplies complete definitions only for the enums and users, plus the start of github_projects. Proposed tables above complete the workflows. Use native UUID generation where available and install vector explicitly. Confirm provider support before running migrations. Keep schema migrations additive with a tested backup/restore path.

| Source enum | Values retained for reporting |
|---|---|
| Job source | whatsapp, linkedin_feed, linkedin_post, manual |
| Job status | discovered, pending_approval, tailoring, applied, outreach_active, shortlisted, assessment, interview, offer, rejected, scam_blocked, skipped |
| Application method | cold_email, linkedin_easy_apply, greenhouse, lever, workday, wellfound, internshala, custom_portal |
| Outreach status | queued, connect_sent, accepted, dm_sent, followup_sent, replied, failed |
| Email class | application_ack, assessment, shortlist_interview, offer, rejection, scam_spam, unrelated |

## HTTP boundary

All application routes below have prefix `/api/v1`. The dashboard authenticates with an HTTP-only, Secure hosted cookie and CSRF/origin checks on mutations. In the local slice the API issues eight-hour opaque bearer sessions on proof of the owner key. Next.js keeps them in HTTP-only same-site cookies and forwards them server-side. Scoped copilot tokens and hosted identity are future work. Never trust a user_id header from a browser. The external Telegram ingress authenticates the provider and verifies the bound owner separately. Filter queries paginate by cursor. Enforce payload size, validated URLs and allowlisted setting names. Use 202 plus task ID for async operations, 403 for insufficient scope, 404 for foreign resources, 409 for stale versions or conflicting idempotency keys and 422 for invalid inputs.

| Route (PRD p7 unless indicated) | Contract and authorization |
|---|---|
| GET /profile; PATCH /profile/settings | Return authorized profile and redacted per-provider health. Validate thresholds, caps, inbox policies and expected settings version. |
| POST /system/kill-switch | Explicit paused boolean, actor, reason and version. Update durable dispatch gate and audit synchronously. |
| POST /integrations/github/sync | Queue bounded sync of allowlisted repos with idempotency key. Return task reference. |
| GET /sources/whatsapp; PATCH /sources/whatsapp/:id | List registered, owner-permitted source identifiers and toggle allowlist. No enumeration of private chats. |
| GET /sources/whatsapp/qr | Retired pairing route, 410 with manual import guidance. No session material. |
| POST /blocklist | Typed normalized company, domain or email plus reason. Recheck pending intents immediately. |
| GET /jobs; POST /jobs/manual | Cursor/filter by status or trust. Submit text or URL plus source and permission basis. Return job or intake task and dedupe result. |
| POST /jobs/:id/decision | Approve preparation, skip or block against assessment version. Record actor and reason. Separate command for sending. |
| GET /jobs/:id/artifacts | Authorized manifest, LaTeX diff, cover letter, PDF stream/short-lived link, evaluation breakdown and review state. |
| POST /extension/ingest-posts | Optional explicit single user-shared item with provenance. Disabled until permitted bridge exists. |
| GET /extension/tasks/next; POST /extension/tasks/:id/report | Optional owner-facing reminder and idempotent manual connection, acceptance, DM, reply or error report. No automated action instructions. Disabled adapter returns a capability-disabled response. |
| GET /emails/audit; POST /emails/audit/:id/restore | Cursor by event time. Restore after owner review against current provider labels. Record success, conflict or expiry. |
| POST /webhooks/telegram | Verify secret header, dedupe update ID, validate user/chat and one-use opaque callback. Approve/skip/block and slash pause/resume route through the same command handlers as web. |
| Proposed additions | GET /jobs/:id, /tasks/:id, /evidence, /audit and /integrations; POST /evidence/:id/review, /applications/:id/prepare, /applications/:id/answers, /intents/:id/decision and /applications/:id/manual-outcome. Add scoped connect/callback/revoke routes per enabled provider. All decisions require expected revision. |
| Operational probes | /health/live for process and /health/ready for required dependencies outside tenant API. Separate worker heartbeat, backlog age and failed-task diagnostics for the authenticated operator. |

## Queue, pause and recovery

Postgres owns intent and progress. Redis carries work references. Use queues for intake, trust, evidence sync, artifact generation, inbox and delivery. Poll or schedule by durable due time, batch by tenant, bound concurrency per provider. The relay can enqueue twice. A worker atomically claims a task lease and uses the operation key to reuse completed work. Backoff with a maximum attempt count, respect Retry-After, record reason and route permanent failures to the operator. Replay with the same key. Rebuild missing queue entries from unfinished database rows.

For external effects, serialize the transition to dispatching with pause/revocation checks on the owner's gate. Record the attempt before the provider call. A pause prevents new dispatch claims, cancels unstarted work and displays claims already in flight. A network call already handed to a provider may finish. Use provider idempotency if supported. On timeout or crash after invocation, mark uncertain, reconcile against a provider receipt or sent item and require explicit review if inconclusive. Never blindly resend. Send mobile approval requests only to a paired owner under an opted-in event policy. Pausing preserves inbound read state and local audit while deferring outbound notifications.

## Provider boundaries

| Adapter | Reads and writes | Failure or permission boundary |
|---|---|---|
| GitHub and portfolio | Selected repositories with minimum read grants, portfolio URLs supplied by owner. Private repo content stays local unless expressly permitted for a processor. | Cache by commit and ETag. Revoke tokens, prune index and invalidate dependent packets. Private resume Git write credential is separately scoped. |
| Overleaf and Tectonic | User-controlled private Git mirror, job branch and pinned compiler bundle. Owner may opt into reviewed sync. | Verify Git entitlement and upstream branch. Handle divergence by review. Local compilation remains usable independently. |
| WhatsApp and LinkedIn | Accept specifically shared job content after permission and allowlist checks. Manual contact search, copy, open official site, owner reports outcome. | No linked-device session, scraping, browser-session impersonation, account discovery or scheduled messaging. New official capabilities require documented entitlement before activation. |
| Employer portals | Source rights and capability matrix per employer/ATS. Manual answer packet and link-out by default. | Unknown fields or identity attestations always return to owner. Only documented and owner-authorized submission interfaces can receive a packet. |
| Gmail | Incremental OAuth. Read-only for tracking, send scope for approved mail, modify only for enabled hygiene. Classify a limited owner-selected mailbox scope, correlate by provider ID/thread, recipient and vacancy evidence. | Cursor after durable import, bounded resync on expiry. No permanent delete. Treat Trash expiry and concurrent changes as visible conflicts. Gmail OAuth scopes and public verification affect SaaS timing. [Google scopes](https://developers.google.com/workspace/gmail/api/auth/scopes) |
| Telegram | Pair via short-lived owner challenge, bind private chat and sender. Use local polling for development, HTTPS webhook in production, minimal text and deep link for private details. | Verify webhook secret and TTL, reject replay and foreign chats. Avoid sending full resumes or sensitive answers. [Telegram Bot API](https://core.telegram.org/bots/api#setwebhook) |
| Trust lookups and AI | Permit documented domain/registration and employer sources. Optional model sees minimized approved facts and untrusted job text as data. | Reject private/reserved network destinations on DNS resolution and redirects, restrict egress, cap response size. Model has no dispatch tools, secrets or unrestricted filesystem. Missing service gives an unknown result or offline draft. |

## Open decisions and release risks

| Missing detail or weakness | Decision now | Evidence needed to change it |
|---|---|---|
| Authentic evidence, resume master and attribution | Synthetic fixtures for build. Candidate reviews facts and uploads an authorized template privately. | Owner-approved source list, roles, metrics, template rights and a human-checked golden packet. |
| Legitimacy formula, ATS calibration and notification latency unspecified | Versioned indicators and documented scores. Target owner alert enqueued within 5 seconds of persisted classification in a healthy local fixture. Poll interval and provider time reported separately. | Labeled good/scam/borderline jobs, representative resumes and actual provider latency before production SLO. |
| Broad provider access presumed | Capability flags default off. Manual handoff and web review work when integrations are unavailable. | Approved providers, scopes, accounts, portal permissions and opt-in notification channel. |
| Ambiguous approval scope and retries | Single-use action approval, proposed 24-hour expiry, version-bound intent and uncertain state. | Owner selects expiry, per-channel caps, timezone and permitted standing inbox/alert rules. |
| Indefinite evidence, mail and artifact retention | Proposed private defaults: minimize source text, retain generated packets until owner deletion, purge temporary inputs after processing. Keep redacted audit metadata, with separate key destruction for sensitive snapshots. | Owner selects exact retention, backup expiry, residency and restore targets before using real data in hosted services. |
| Availability and budget unknown | Laptop-only execution initially. An always-on worker, durable storage, backups and monitoring require a funded hosted design. | Approved monthly ceiling, Vercel/Render targets, recovery objectives and tested restore. |
| PDF DDL truncated; tenancy and provider delivery under-specified | Design above adds composite keys, row policies, idempotency, receipts and explicit ambiguity. | Migration, cross-tenant, restart and fault-injection tests before release. |

## Implemented private data boundary · phase 1B

The physical schema is in apps/api/migrations/sql/0002_upgrade.sql and the SQLAlchemy metadata. The five native PostgreSQL enums preserve the PRD labels and order. Identity is in users, candidate fields and profile_vault_json in candidate_profiles, and typed preferences in user_settings. The profile API projects settings_json with the installation-wide pause flag. Encrypted credentials and credentials_iv reside on the matching integration connection. Each tenant resource has a required user_id. The users identity root and singleton system_control are the two exceptions to tenant ownership.

PostgreSQL applies row policies to every tenant table. Authentication resolves a digest through one fixed-search-path database function that checks expiry and active status. The private API role cannot create users or change schema. Composite keys enforce ownership on relationships even during maintenance writes. Session and business mutations append redacted audit records. Idempotency receipts, their keyed payload digest, the domain write and its audit record commit together.

The private worker currently handles only local_probe. The pending task row serves as its outbox. Redis transports the UUID, PostgreSQL decides eligibility and records completion. The global pause row serializes worker dispatch and control updates. A database trigger also rejects prohibited task status transitions. Provider dispatch, approval consumption, billing, public signup and hosted tenancy qualification remain later milestones.
