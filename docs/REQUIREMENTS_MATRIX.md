# JODY requirements matrix

Each row has a permanent ID. Source references use the printed PDF page and section. **Owner** denotes the accompanying build instructions and **Design** denotes a control added to make a source requirement testable. Rows retain the original request when a delivery mechanism changes. Phase exits and fixtures are defined in the [roadmap](ROADMAP.md).

**Priority** P0 protects the user or enables the private MVP, P1 completes the private production workflow, P2 supports optional adapters or public SaaS. **Status** Planned means implementation is outstanding. Adapted means the source intent has a safer planned implementation. Deferred means work is assigned to a later phase or access gate. Documented applies only to planning artifacts. **Partial** denotes a tested subset with outstanding criteria. **Tested** requires the entire row to pass. Current evidence and limits are in PROGRESS.md.

## Functional requirements

| ID | Source | Priority | Requirement and disposition | Acceptance criterion | Status |
|---|---|---|---|---|---|
| F01 | pp1–3 §§1–4.1 | P0 | Discover jobs from multiple channels and manual links or text. | Manual text and URL create owner-scoped opportunities. A supplied WhatsApp or LinkedIn item retains its group, feed or post source type and permission basis. | Partial |
| F02 | p3 §4.1 | P0 | Extract role, employer, location, remote flag, application URL and HR/recruiter email. | Fixture yields all present fields with provenance and unknowns for missing fields. | Planned |
| F03 | p3 §4.1 | P0 | Normalize and deduplicate across sources. | Concurrent imports of one requisition yield one job, two sightings and one application intent. Similar roles with distinct requisitions remain separate. | Partial |
| F04 | p3 §4.2 | P0 | Assess legitimacy before tailoring or sharing details. | Record 0–100, flags, evidence and check time for domain age, recruiter/site domain alignment including free webmail, authorized LinkedIn company/recruiter evidence, fee/deposit/security-payment language and off-platform demands. Unavailable signals remain unknown. | Planned |
| F05 | pp1–3 §§1,4.2 | P0 | Route trusted, doubtful and scam jobs. | At default 80, high trust may start preparation. Borderline or insufficient evidence shows score and flags for approve/skip/block. Confirmed scam blocks dispatch, updates blocklist and proposes matching inbox cleanup. | Adapted |
| F06 | p3 §4.3 | P0 | Select real projects relevant to the job description. | Ranked results show supporting passages, source revision and unmet requirements. Cross-owner and unverified claims are excluded. | Tested |
| F07 | pp1,3 §§1,4.3 | P0 | Tailor resume emphasis and wording to verified experience. | Each output claim maps to reviewed facts. A fixture asking for an unsupported employer, skill, achievement or numerical result fails validation or omits it. | Tested |
| F08 | pp1,3,5 §§2,4.3,5 | P0 | Produce versioned LaTeX and compiled PDF. | Given a pinned template, review shows source diff, readable PDF and artifact hash for this job. Concurrent jobs preserve the master. | Partial |
| F09 | p3 §4.3; p6 §6 | P0 | Score ATS compatibility and refine within limits. | Show keyword alignment, role relevance, clarity and structure on extracted PDF text. Score below default 82 triggers bounded refinements then human review. Parsing failure blocks release. | Adapted |
| F10 | p3 §4.3 | P0 | Prepare a job-specific CV and cover letter when requested. | Package shows matching projects, reviewed claim IDs and job-specific letter. Unsubstantiated claims block approval. | Partial |
| F11 | p3 §4.4 | P0 | Prepare recruiter, founder or HR email with resume and cover letter. | Owner can preview destination, subject, body and exact attachments. Delivery requires fresh matching approval and logs a receipt or uncertain outcome. | Adapted |
| F12 | p3 §4.4; p6 §6 | P1 | Assist portal applications using standard vault fields. | Map supported fields and show a reviewable answer packet. Manual completion works for each recorded method. Only an explicitly authorized adapter can submit after approval. | Adapted |
| F13 | p3 §4.4 | P1 | Ask about unfamiliar custom questions. | Unknown field pauses preparation, requests owner input on web or paired Telegram and resumes only with an attributed answer. Sensitive answers stay in the dashboard. | Planned |
| F14 | p4 §4.5 | P1 | Identify decision makers at applied companies and prepare concise connection notes. | Owner can record a sourced recruiter, engineering manager, CTO or founder, role and tailored note for a specific job. | Adapted |
| F15 | p4 §4.5 | P1 | After confirmed acceptance, prepare value-focused rapport and one follow-up. | Manual acceptance unlocks a draft referencing reviewed GitHub work and portfolio. After configurable wait, at most one reminder/draft appears. A reply, decline, opt-out or follow-up ends the sequence. | Adapted |
| F16 | pp2,4 §§3,4.6; p6 §6 | P1 | Classify incoming mail and update Kanban. | Fixtures cover acknowledgment, assessment, shortlist/interview, offer, rejection, scam/spam and unrelated. Link using message/thread and job evidence. Ambiguity goes to review and late mail cannot silently regress an offer. | Planned |
| F17 | pp2,4 §§2,4.6–7 | P1 | Notify owner of applications, doubtful companies, shortlists, assessments and interviews. | Each qualifying event queues one opted-in mobile alert after commit. Show time, delivery outcome and retry or dashboard fallback. | Planned |
| F18 | pp1–2,4 §§1–2,4.6 | P1 | Reversible inbox hygiene. | Confirmed scam can be labeled/trashed. Rejection can be labeled/archived or explicitly trashed per settings. Undo restores prior labels where available and records outcome. Ambiguous mail stays untouched. | Adapted |
| F19 | pp2,4 §§3,4.7 | P0 | Live pipeline and operator controls. | Board updates after persisted events, filters by status/trust, opens evidence and artifacts, shows sync health, rule controls, pause state and chronological audit of outreach and mail changes. | Partial |
| F20 | p4 §§4.7–8 | P2 | Guided SaaS onboarding. | New tenant can enter profile manually or import GitHub, see requested permissions, opt in per channel, revoke access and complete an isolated first job. | Deferred |

## Technical requirements

| ID | Source | Priority | Requirement and disposition | Acceptance criterion | Status |
|---|---|---|---|---|---|
| T01 | pp2,4 §§3,5; Owner | P0 | Next.js, TypeScript and Tailwind dashboard, mobile and keyboard access. | Build passes. Board and approval flow work by keyboard and narrow viewport. Figma-derived hierarchy and controls use JODY content. | Partial |
| T02 | pp2,4–5 §§3,5 | P0 | Separate API and worker lifecycles. The owner selected FastAPI and Python workers for the implementation. | Closing the dashboard leaves an enqueued job running. A worker restart recovers it. Services communicate through versioned contracts. | Partial |
| T03 | pp2,4–6 §§3,5–6 | P0 | PostgreSQL 16, pgvector and relational constraints. | Clean migrations and upgrade fixture provide UUIDs, owned keys, validated scores/statuses and vector search. Verify extension availability. Source lists uuid-ossp, pgcrypto and vector. | Tested |
| T04 | pp2,4,8 §§3,5,8 | P0 | Redis work queue and durable recovery. | DB commit plus outbox survives Redis loss. Duplicate task, lost lease and process crash cannot repeat a confirmed action. Dead letters and replay are visible. | Partial |
| T05 | pp5–6 §6 | P0 | User/profile vault and settings. | Store unique email, name, GitHub handle, LinkedIn/portfolio URLs, unique Telegram binding, repo/branch (main default), template, vault, settings, active flag, UUID and timestamps. Validate typed updates. Separate secret envelopes. | Partial |
| T06 | p6 §6 | P0 | Represent the specified source, job, application method, outreach and email vocabularies. | Round-trip every value listed in the architecture. Dashboard distinguishes confirmed application from prepared or approval-pending packet. Unknown values fail validation. | Partial |
| T07 | pp5–6 §6; p7 §7 | P0 | Preserve threshold, cap and inbox preferences. | Read defaults 80 trust, 82 ATS, 12 connections/day and 20 DMs/day as manual guidance. PRD enables scam Trash/rejection archive and starts unpaused. First run instead starts paused with mailbox writes opt-in. | Tested |
| T08 | pp2–3 §§3,4.3 | P1 | GitHub semantic retrieval with versioned embeddings. | Golden job finds an expected project. Changed commit refreshes affected chunks, revoked repo disappears from retrieval. Lexical mode works offline. | Planned |
| T09 | p7 §7 | P0 | Authenticated /api/v1 REST contracts, including extension and callback dispositions. | Contract tests cover every route in the architecture ledger, including disabled routes, tenant derivation, validation, duplicate mutations and stale versions. | Partial |
| T10 | p7 §7; Design | P0 | Artifact access and reproducible evaluations. | Authorized job view returns private PDF access, LaTeX diff, cover letter and ATS breakdown with input hashes and evaluator version. Foreign owner access fails. | Partial |

## Integration requirements

| ID | Source | Priority | Requirement and disposition | Acceptance criterion | Status |
|---|---|---|---|---|---|
| I01 | pp1–4 §§1–4.3; p7 §7 | P0 | Sync selected GitHub repos, descriptions, README summaries, stacks, live links and evidenced metrics. | Read-only scoped sync records revision/path. Unverified metrics remain candidates. Incremental retries avoid duplicate facts and embeddings. | Partial |
| I02 | pp1,5 §§2,5 | P1 | Private Git master and optional Overleaf Git sync, Tectonic locally. | Compile pinned template offline, isolate per-job revisions, approve and safely push intended Git changes. Concurrent upstream edit creates a reviewable conflict. Verify Overleaf account entitlement before enabling remote sync. | Adapted |
| I03 | pp2–3 §§2–4.1; pp4,7–8 | P1 | WhatsApp group/channel allowlist. Replace persistent linked-device monitoring, discovery and pairing QR with owner-supplied permitted items. | Reject an unlisted source before parsing or raw-content persistence. Toggling a group stops subsequent intake. QR route is disabled and no personal session exists. | Adapted |
| I04 | pp2–4 §§3–4.5; pp5,7–8 | P1 | LinkedIn feeds, job/hiring posts and outreach. Use manual import, link-out, user-confirmed outcomes or a separately entitled API. | No background feed scan, scraping, DOM-driven connections, acceptance polling, DMs or simulated human delays. One manual post creates one attributed job. | Adapted |
| I05 | pp4–5,7–8 §§4.5,5,7–8 | P2 | Optional Manifest V3 Chrome copilot. | Owner explicitly shares selected content or copies a draft. Scoped token and origin checks protect bridge. Only manual outcome reporting and reminder tasks are available. | Deferred |
| I06 | pp2–4 §§3,4.4,4.6 | P1 | Gmail OAuth for outgoing mail, inbound tracking and reversible mailbox changes. | Incremental consent, cursor recovery, provider throttling and revocation tested. Approved message receipt or reconciliation prevents automatic duplicate sends. | Planned |
| I07 | pp1–4,7–8 §§1–4,7–8 | P1 | Telegram Bot API alerts, one-tap decisions, answers and slash pause/resume. | Paired owner receives minimal alert. Signed-in account binding, secret webhook header, callback expiry and replay checks protect all actions. Unknown chat cannot operate the bot. | Planned |
| I08 | pp3,6,8 §§4.4,6,8 | P1 | Portal-specific application support. | Capability registry records read/prepare/submit rights per provider. An unsupported portal produces a packet and link. A documented permitted write needs a matching approval and receipt. | Adapted |
| I09 | Owner | P0 | Use portfolio as a reference and Figma as visual direction. | Owner can cite a reviewed portfolio item. UI review compares hierarchy and palette to node 131:1408 and checks for JODY-specific copy. | Tested |

## Security and reliability requirements

| ID | Source | Priority | Requirement and disposition | Acceptance criterion | Status |
|---|---|---|---|---|---|
| S01 | pp1,3–4,8 §§1,4.3,8; Owner | P0 | Ground all candidate representations. | Fabrication fixture covering skills, employers, achievements, experience and metrics fails closed across resume, letter, email, messages and form answers. | Partial |
| S02 | pp1,4,7–8 §§1,4.7,7–8; Owner | P0 | Explicit approval and attributable audit for external communications. | Store actor, purpose, consent or approval, recipient, content digest, artifact version, time and outcome. Altered, expired or replayed approval cannot dispatch. | Planned |
| S03 | pp4,6–8 §§4.7,6–8 | P0 | Global pause for outbound work, including extension tasks. | Pause blocks new dispatches at the final gate, tracks already in-flight effects, preserves pending tasks and never silently replays uncertain sends on resume. | Partial |
| S04 | pp4,6,8 §§4.8,6,8; Owner | P0 | Encrypt OAuth tokens, API keys and sessions, minimize sensitive data. | Per-owner authenticated encryption with separate keys and rotation. Revocation disables jobs. Secret scan and redaction tests pass. Backups and private artifacts are access controlled. | Partial |
| S05 | pp1,4–7 §§1,4.8,6–7 | P0 | Authenticate private release and derive tenant from session on API, storage, queries, workers and callbacks. | A second test identity cannot access any other owner's row, artifact, cache entry, task or audit. Signup is closed in private mode. | Partial |
| S06 | pp2,4,7–8 §§2,4.6,7–8 | P1 | Audit and restore all automated inbox changes. | Prior label set and provider message ID survive restart. Repeated restore is safe. Expired Trash or conflicting later edits show a recoverability warning. | Planned |
| S07 | pp1,3–4 §§2,4.4–5 | P1 | Enforce caps, consent, suppression and bounded follow-up. | Provider limits, owner limits and opted-out recipients suppress queued work at dispatch. Backoff respects provider guidance. Replies cancel pending follow-up. | Adapted |
| S08 | Design for pp2–3 §§3–4 | P0 | Treat third-party text, links and LaTeX as untrusted. | Host validation, bounded downloads, isolated compiler and escaped fields withstand fixtures containing private URLs, instructions to send, shell syntax and malicious template content. | Planned |
| S09 | p4 §4.8; p8 §8 | P2 | Public authentication, per-user credentials and isolated queues without core table redesign. | Two concurrent tenants onboard, rotate/revoke credentials and process jobs under separate quotas. Isolation and noisy-neighbor tests pass before signup opens. | Deferred |

## Deployment and delivery requirements

| ID | Source | Priority | Requirement and disposition | Acceptance criterion | Status |
|---|---|---|---|---|---|
| D01 | pp1–2,5,8 §§1–3,5,8; Owner | P0 | Local-first development, Docker-compatible processes and private single-user MVP. | Offline fixture path works after dependencies are installed, with one owner and restart persistence. Laptop downtime is reported in health. | Partial |
| D02 | pp1–2,5,8 §§1–3,5,8; Owner | P1 | Always-on hosted ingestion, scoring, tailoring, dispatch and inbox workers. Vercel frontend and Render backend. | Against approved resources, close browser and stop local machine. Hosted scheduled work continues, API/worker health checked and mobile event verified. | Deferred |
| D03 | p8 §8; Owner | P0 | Preserve five source milestones and define smaller resumable phases. | Roadmap crosswalk covers infrastructure/RAG/ATS, ingestion/trust/bot, application/mail, copilot/dashboard, then SaaS, with testable exits. | Documented |
| D04 | Owner | P0 | Plan only, preserve working code and establish baseline. | Seven named planning files, source fingerprint and inspection record exist. Phase diff contains documentation only. | Documented |
| D05 | Owner | P0 | Control cloud and Codex spend. | Cost plan defines zero-spend baseline, budget decision, bounded work, usage signals and restart steps. Each future billable action records owner approval. | Documented |
| D06 | Owner | P0 | Test, update both ledgers, commit, push normally and verify remote branch each phase. | Each phase reports tests, hash, branch, remote proof or the precise access blocker. No feature marked tested without evidence. | Documented |
| D07 | Owner | P0 | Check branch deployment configuration, trigger enabled Vercel/Render releases and verify health. | Report verified revision, actual URLs, smoke checks, blockers and next action. Record unsupported or unavailable checks explicitly. | Documented |

## Coverage index

Pages 1–2 introduce the objectives, guardrails and service diagram (F01, F04–F11, F18, T02–T04, I02–I07, S01–S07, D01–D02). Page 3 specifies intake, trust, tailoring and applications (F01–F13). Page 4 adds outreach, inbox, controls, tenancy and the stack (F14–F20, T01–T04, S03–S06, S09). Pages 5–6 specify remaining stack choices, partial DDL, vocabularies and defaults (T03, T05–T08, I02, I05, I07). Page 7 is mapped route by route under T09 in the architecture. Page 8 maps to D03 and the milestone crosswalk, S01–S06 and S09. The [build contract](BUILD_CONTRACT.md) records source precedence and future checkpoint obligations.

## Foundation acceptance supplement

These rows capture the owner's phase 1 foundation instructions. The original product rows above retain their wider release criteria.

| ID | Source | Priority | Requirement and disposition | Acceptance criterion | Status |
|---|---|---|---|---|---|
| T11 | Owner, phase 1 | P0 | Typed FastAPI / SQLAlchemy / Alembic and Next.js App Router foundation. | From a clean database, upgrade the schema and verify pgvector, then use the typed client in a browser to sign in, save, reload, retry and sign out. | Tested |
| T12 | Owner, phase 1 | P0 | Health, readiness, request logging and basic errors. | Reach live/ready endpoints, fail readiness with an offline dependency, capture a request ID and structured request record, return sanitized errors for invalid input. | Tested |
| D08 | Owner, phase 1 | P0 | Reproducible Ubuntu stack, environment template and Compose services. | Generate private local configuration, start both data services from Compose, migrate and run the complete application. | Tested |
| D09 | Owner, phase 1 | P0 | Lint, format, type checks, backend and browser tests in GitHub Actions. | Local checks pass and a remote CI run for the same commit passes. The linked CI run in PROGRESS.md records the result. | Tested |
| T13 | Owner, secure data | P0 | Migrate all requested PRD domains and keep tenant ownership explicit. | Upgrade legacy fixtures, preserve IDs and five enum sets, verify every owned table has mandatory user_id and reject cross-tenant references. | Tested |
| S10 | Owner, secure data | P0 | Secure the private control API and stored credentials. | Registered private routes reject missing/invalid sessions, inactive users and expired sessions lose access, stored secrets decrypt only with matching key and context, and the API omits secret values. | Tested |
| S11 | Owner, secure data | P0 | Pause, idempotency and redacted audit for local commands. | Duplicate commands commit one change, conflicting keys return 409, a racing pause fences the worker and scoped audit history is append-only to the runtime role. | Tested |
| F21 | Owner, candidate foundation | P0 | Editable candidate identity, history, skills, projects, links, job and application preferences, plus role-specific private resumes. | Save and read fields via an authenticated session, manage two uploads, reject invalid uploads and foreign downloads, preserve the existing profile endpoint. | Tested |
| F22 | Owner, onboarding | P0 | Eight persisted onboarding steps, optional skips, return visits, permission review and explicit final confirmation. | A new profile can skip five sections, finish, then revisit one. Sensitive changes invalidate the relevant review and confirmation. | Tested |
| S12 | Owner, candidate foundation | P0 | Separate suggestions, owner-provided data and owner-reviewed evidence in application preparation. | Inferred values and unreviewed qualifications cannot answer required questions. Missing information yields a clarification. Editing a verified field revokes its verification. Selecting a portfolio or resume does not grant outbound approval. | Tested |

## Career intelligence acceptance supplement

| ID | Source | Priority | Requirement | Acceptance criteria | Status |
|---|---|---|---|---|---|
| CI01 | Career brief §1 | P0 | Import multiple resume variants and immutable originals. | Extract text from real PDF, DOCX and LaTeX fixtures, select among two baselines and return original bytes after tailoring. | Tested |
| CI02 | §1 | P0 | Preserve attributed repository, portfolio and candidate sources. | Accept commit-pinned content and profile-selected portfolio imports, isolate tenants and require owner review before using a claim. | Tested |
| CI03 | §1 | P0 | Canonical history, skills, dates, research, achievements and source conflicts. | Extract all requested sections with locators, reject stale or conflicting verification and reconstruct a prior review revision. | Tested |
| CI04 | §2 | P0 | Interpret the actual job with structured inference. | Classify original clauses into facets and priorities, retain explicit preferences and produce matching functional terms for equivalent responsibilities. | Tested |
| CI05 | §§2–3 | P0 | Retrieve semantic evidence and explain qualification fit. | Return a bounded estimate, confidence, four possible recommendations, supporting quotes and distinct direct, transferable, required, preferred and eligibility outcomes. Demonstrate different titles matching and an identical title failing. | Tested |
| CI06 | §4 | P0 | Expose authorized MCP career resources and tools. | Negotiate the official protocol, list the nine read tools, read a fact resource, compare a job and save a proposal with the separate write server. | Tested |
| CI07 | §§3–4 | P0 | Contain untrusted inputs and scope delegated access. | Invalid model indices cannot introduce a claim. Mixed scopes and owner-route token reuse are denied. Owner logout revokes a child capability. | Tested |
| CI08 | §5 | P0 | Prepare grounded versions per application and record changes. | Select a relevant authorized original, preserve verified dates and education, link an idempotent version and application, record reasons and unresolved questions, and honor owner exclusions. | Tested |
| CI09 | §6 | P0 | Configure local inference and enforce spending controls. | Exercise actual local embeddings and structured chat with synthetic evidence. Offline retries count against the daily budget, replays reuse ciphertext-backed cached results, and the monetary limit is zero. | Tested |
| CI10 | §§7–8 | P0 | Evaluate, migrate and checkpoint. | Run a labeled fixture set with precision, recall and errors, migrate legacy and clean databases, verify regressions and report remote disposition. | Tested |

## Public and private UI acceptance supplement

| ID | Source | Priority | Requirement | Acceptance criteria | Status |
|---|---|---|---|---|---|
| UI01 | UI brief A | P0 | Public JODY landing page and interactive product preview. | Visitors can search the labeled sample openings, reach discovery, matching and privacy sections, switch preview views and navigate to sign-in on mobile and desktop. | Tested |
| UI02 | UI brief B | P0 | Private career workspace with twelve navigable sections. | Signed-in owner can inspect jobs and trust, group applications by stage, read approvals and activity, manage resumes and policy entries, and pause work. Backend-backed views distinguish empty data, examples and unavailable operations. | Tested |
| UI03 | UI brief, verification | P0 | Responsive and accessible interactions and screenshot evidence. | Exercise both experiences and workspace navigation at 360, 390, 768, 1024 and 1440 pixels, check overflow and automated accessibility, and retain a pair of synthetic captures at each width. | Tested |

## Private preview acceptance supplement

| ID | Source | Priority | Requirement | Acceptance criteria | Status |
|---|---|---|---|---|---|
| DP01 | Deployment brief | P0 | Protected Vercel frontend and free Render backend with PostgreSQL. | Both providers report the pushed revision, anonymous frontend requests require Vercel Authentication, and live readiness confirms migrated PostgreSQL with pgvector and Key Value. | Tested |
| DP02 | Deployment brief | P0 | Secure owner access and disabled external automation. | A hosted browser verifies secure cookies, owner-scoped reads and sign-out revocation. Owner requests to resume automation are denied. No paid or background worker is configured. | Tested |
| DP03 | Deployment brief | P0 | Reproducible deployment and operator handoff. | Verify the Docker workflow and live desktop/mobile navigation. Record environment ownership, live URLs, exact free database expiry and persistence limits. | Tested |

## Prompt 5.5 acceptance supplement

| ID | Source | Priority | Requirement | Acceptance criteria | Status |
|---|---|---|---|---|---|
| IC01 | Autonomous spec §§1–4, 18; 5.5 §1 | P0 | Automatic discovery through permitted sources alongside supplementary manual intake. | All sources enter the same attributable, deduplicated pipeline; no action can bypass trust, evidence, pause or approval. Read-only pilot and subsequent dispatch remain staged. | Planned |
| IC02 | 5.5 §2 | P0 | Multi-user identity and onboarding. | Verified/recovered identity maps to a unique user, blank defaults, isolated resumable settings and verified disconnect/deletion. No public registration before two-tenant release gates. | Partial |
| IC03 | 5.5 §3 | P0 | Evidence-based integration state contract. | Seven typed states. Private UI distinguishes stored credentials and disabled adapters; tenant authorization and removal tested. Durable verification receipts required for persistent verified badges. | Partial |
| IC04 | 5.5 §3; owner setup | P0 | Official read-only Gmail setup and refresh. | Exact callback, one-use state, browser binding, PKCE, scope validation, refresh and metadata probe verified with fixtures. Hosted tenant grant lifecycle and real owner verification outstanding. | Partial |
| IC05 | 5.5 §3 | P0 | Read-only private Git and multiple resume formats. | Verify selected repository and pinned file; preserve immutable originals. Test bounded LaTeX ZIP import and private sync before enablement. | Partial |
| IC06 | 5.5 §§3,7 | P1 | Private notifications and single-use Telegram linking. | Verify bot identity separately. Bind expiring code to sender and tenant once; prevent replay and cross-user command execution before any delivery. | Partial |
| IC07 | 5.5 §3 | P1 | Policy-compliant WhatsApp and LinkedIn source boundaries. | Prevent storage before allowlist, unpair/revoke, and require independent platform permission. Permitted Gmail alerts form the LinkedIn automation path. | Planned |
| IC08 | 5.5 §4 | P0 | Per-task, consented, zero-spend model routing. | Local optional model and encrypted tenant BYOK, catalog and quota checks, deterministic decisions; live hosted calls require proven free capacity and task-specific consent. | Partial |
| IC09 | 5.5 §5 | P0 | Rehearse database portability before cutover. | Encrypted dump restores on isolated PG16, restricted grants and scopes pass, vector available, all application counts match, restored canary decrypts. | Tested |
| IC10 | 5.5 §5 | P0 | Qualify Neon and manage Render expiry. | Validate direct and pooled access, private hosted export, decryption and rollback in a separate branch before explicitly approved cutover. | Planned |
| IC11 | 5.5 §6 | P1 | Card-free worker runtime and Ubuntu fallback. | Identify card-free candidate, document limits, validate Ubuntu service/timer definitions and existing durable probe. Require restart/uptime trial before claiming hosted continuity. | Partial |
| IC12 | 5.5 §§8–9 | P0 | Operator configuration and checkpoint. | Every provider has names, storage location, owner/user boundary, safe check, expected result and failure handling; placeholders only, tested change pushed, existing preview preserved. | Tested |
