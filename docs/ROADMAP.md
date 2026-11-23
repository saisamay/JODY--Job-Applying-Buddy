# JODY release roadmap

The **private MVP exits at phase 3** when one owner can take a manually supplied vacancy through a trust decision, evidence-grounded resume and cover letter, artifact review, and a recorded manual application. It must work with live sending disabled. A red trust check, missing claim or stale packet must stop the same workflow that a good fixture can complete.

## Delivery sequence

| Phase | Deliverable and dependencies | Exit evidence |
|---|---|---|
| 0 · Planning | Source recovery, requirement register, architecture, cost boundaries, checkpoint and handoff. D03–D07. | Verify eight-page source, seven documents, row schema and ID uniqueness, links and route coverage. Record Git and deployment disposition. |
| 1 · Local foundation | First slice 1A is the owner-scoped intake round trip below. In 1B add durable task/outbox, worker lease, audit and pause. Start with local fixtures. T01–T07, T09, S03–S05, D01. | Cold migration, authenticated web→API→DB round trip, foreign-owner denial, restart recovery, duplicate task and pause/dispatch race. Local secrets stay outside Git. |
| 2 · Evidence and compilation | With phase 1 storage, add reviewed GitHub fixture/import, optional read-only sync, template, PDF, job match, ATS rubric and letter. F06–F10, T08, T10, I01–I02, I09, S01, S08. | Known fixture produces parseable PDF and correct cited claim IDs. Unsupported metrics cannot appear. Compiler isolation, bad template, revoked evidence, threshold and retry exhaustion tests pass. Benchmark a small vector index separately. |
| 3 · Private MVP | Add full permitted manual intake, dedupe, trust review, blocklist, pipeline view, reviewable email/portal packet, owner-confirmed handoff, audit and settings. F01–F05, F11–F12, F19, S02. | Browser walkthrough from pasted job to reviewed packet and manual outcome. Scam blocks preparation. Editing a packet invalidates approval. Two concurrent sightings create one job. Restart preserves board and audit. |
| 4 · Private provider pilots | Pair Telegram, then read-only Gmail tracking, then opt-in approved send and reversible hygiene. Add labeled, allowlisted owner-supplied WhatsApp/LinkedIn items, contact sequence, unknown-question handoff and permitted portal adapters individually. F13–F18, I03–I04, I06–I08, S06–S07. | Each adapter first passes fixtures for duplicates, revocation, quota, ambiguous results and recovery. Then use owner-approved test destination/account for a bounded live smoke. Demonstrate mail undo and one follow-up maximum. |
| 5 · Hosted private release | With owner-approved resources, link Vercel and Render, run API, scheduler and workers continuously. Harden monitoring, migrations, backups, restore and rollback. Optional manual MV3 helper can ship separately after entitlement review. I05, D02, D06–D07. | Verified SHA at remote and both targets, private auth, synthetic smoke, worker heartbeat while clients are offline, backup restore and rollback drill. Record real URLs and latency. |
| 6 · Public SaaS | Add public identity, onboarding, per-user authorization and key management, compute isolation, rate limits and deletion/export lifecycle. F20, S09. | Two-tenant isolation matrix across API, queue, artifact, retrieval, callbacks and audit. Noisy tenant cannot starve another. Pass rotation, account closure, OAuth review and support/recovery readiness before opening signup. |

An ID can span phases. For example F11 has a reviewable local email packet in phase 3 and requires a provider receipt or reconciled uncertain result in phase 4. Keep its status partial until the entire row has passing evidence.

## PRD milestone crosswalk

| Original milestone (p8) | JODY implementation order |
|---|---|
| 1. Infrastructure, GitHub RAG and ATS | Phases 1–2. Local deterministic ranking and fixtures make progress possible before model or GitHub credentials exist. |
| 2. Multi-source intake, scam checks and Telegram | Manual intake starts in phase 1, scored review in phase 3, approved source imports and mobile control in phase 4. |
| 3. Application submission and Gmail intelligence | Phase 3 prepares packets and records manual submission. Phase 4 adds explicitly approved email and any authorized portal submit, tracking and recovery. |
| 4. LinkedIn extension and dashboard | Safety controls and operator UI move into phases 1–3. Manual relationship sequence follows in phase 4. Optional user-invoked copilot follows in phase 5. |
| 5. Public SaaS | Ownership starts at phase 1, public onboarding and isolation qualification at phase 6. |

## First implementation slice

1A has one user-visible result. The authenticated owner pastes a synthetic job, reloads the page and sees it in their pipeline. Proposed paths are apps/web, apps/api, packages/shared and apps/api/migrations. Phase 1A adds a broker probe in apps/worker. Introduce a durable consumer in 1B. Use PostgreSQL with a volume, a closed owner session, one migration and a fake second owner in tests. Leave provider adapters unplugged. [Next step](NEXT_STEP.md)

At every exit follow the [build contract](BUILD_CONTRACT.md), publish the verified commit and preserve the last passing slice. Validate cloud access only when its phase needs it.
