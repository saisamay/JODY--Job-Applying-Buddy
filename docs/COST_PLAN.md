# JODY cost and credit plan

**Current authorization is zero incremental paid cloud or model spend.** Existing machine, storage, electricity, network and any existing Codex subscription are outside that incremental cloud total. The available Codex credit balance and future monthly hosting ceiling are unknown. The private MVP must work without a paid model.

| Stage | Resources and unit of cost | Spending decision |
|---|---|---|
| Planning and local MVP | Local Postgres/pgvector, Redis, Node processes, Tectonic, private local files and small synthetic fixtures. Use deterministic extraction, lexical ranking and templates. | Zero new hosted services, model calls or paid integration entitlements. Stop processes when idle. |
| Optional private pilots | Selected GitHub reads, paired bot updates, Gmail operations and optional model tokens/embeddings. Usage and rate limits vary by account. | Check consent, entitlement and quota per adapter. An existing connector for the developer session does not grant runtime credentials to JODY. Keep paid inference disabled until explicitly budgeted. |
| Hosted private release | Vercel project/usage, Render API instance-hours, worker instance-hours, Postgres compute/storage/backups, Redis-compatible capacity, artifact storage/egress, logging and bandwidth. | Quote region, tier, quantity, backup and overage terms for each item before provisioning. Render's free preview services have availability and persistence limits. Continuous worker hosting needs a separate provisioned plan. [Render free services](https://render.com/docs/free) · [Render pricing](https://render.com/pricing) · [Vercel plans](https://vercel.com/docs/plans) |
| Optional Overleaf sync | Overleaf Cloud Git integration and GitHub synchronization require a premium entitlement. Local Git plus Tectonic covers document preparation. | Use an existing permitted subscription or leave sync off. [Overleaf integration documentation](https://docs.overleaf.com/integrations-and-add-ons/git-integration-and-github-synchronization) |
| Public SaaS | Per-tenant compute, private storage, mail/provider usage, support, monitoring, backups and any provider review costs. | Re-quote commercial eligibility, volume and worst-case overages before opening signup. |

## Estimation and enforcement

Build an estimate in one currency from the provider quote on the approval date. Use API hours × hourly rate + worker hours × hourly rate + database and queue monthly charges + artifact GB-month and egress + backups/logs + model input/output tokens × unit rates. Include any separate workspace minimums, regional taxes, data transfer and overlap during rollout. For an always-on month estimate up to 744 hours per instance. Document the estimate, maximum authorized amount, owner, resource, region, purpose, expiry and teardown owner. An alert alone cannot enforce a spending cap.

Track job imports, dedupe rate, GitHub bytes/requests, changed chunks embedded, cache hit rate, model tokens, compile duration/retries, mail operations, queue age and stored artifact bytes. Cache by repo commit, job/evidence/template hash and evaluator version. Deduplicate before trust lookups and generation. Bound concurrent compiles, retries and provider batches. Use deterministic backoff for rate limits. Quota exhaustion leaves a resumable pending task. Require new approval to enable a paid provider, raise a cap or create a billable resource. On approaching a cap disable optional refresh and paid generation first; reserve local review, pause and audit.

## Limited Codex credits

- Work on one acceptance slice per session. Read the two ledgers and only the rows and files named by the slice. Reopen the PDF on source ambiguity or edition change.
- Use small labeled fixtures and deterministic fake adapters. Run targeted tests while iterating, then the impacted suite and required phase gates once before publishing.
- Preserve a failing fixture and the shortest reproducer. Repeated identical failures call for diagnosis or a recorded blocker. Avoid full-repo regeneration, paid model evaluation and repeated cloud deployments.
- Before credit exhaustion, record last passing commit, dirty paths, test command/outcome, outstanding risk and one next command in the ledgers. Keep partial work identified. Only commit/push a passing slice as a completed checkpoint.
- Resume by reconciling HEAD, remote and working tree with the checkpoint. Reuse proven tests, fixtures and decisions. Keep credentials, raw PDFs, mailbox payloads and private evidence out of handoff notes.
