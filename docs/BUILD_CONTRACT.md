# JODY build contract

JODY — Your AI Job Applying Buddy helps one person find legitimate jobs and prepare truthful applications. The owner controls which facts leave the system, who receives them, and when. Public SaaS is a later release. This checkpoint authorizes planning only.

## Authority and source

The authoritative product specification is the eight-page **AutoApply AI — Software Requirements & Technical Architecture Specification**. The initial checkout contained only Git metadata. The local file named `jody(job applying buddy).pdf` matched the product, former title, modules and milestones. It was copied byte-for-byte to `docs/JODY_PRD.pdf` and read in full. SHA-256 is `704053e16fa01a748efd9545ac08c946d95c30a794d67a4923ede5c7f7b8c9c2`. The recovered PDF is kept locally. On another checkout obtain the owner's copy and verify its hash. Page 6 visibly ends inside the opening of the GitHub projects table. Later database definitions in the architecture are design decisions.

The owner's naming, safety, hosting, cost and Git instructions govern delivery. The matrix records the underlying intent wherever a mechanism changes. Record subsequent scope changes against stable IDs, with the reason, decision owner, test and phase. Update the source fingerprint and reconcile page coverage if a different edition arrives. [Requirements matrix](REQUIREMENTS_MATRIX.md)

## Operating agreement

| Boundary | Decision |
|---|---|
| Candidate evidence | Every affirmative claim in a resume, letter, email, portal answer or outreach draft must resolve to reviewed evidence. A repository dependency, portfolio statement or AI inference alone cannot establish proficiency, employment, authorship, dates, achievements or a metric. Missing evidence creates a question. |
| Discovery | Accept manual descriptions, links, permitted exports and documented feeds with permission. Keep source attribution, allowlist and deduplication. For LinkedIn and WhatsApp the default is owner-selected input and manual interaction. |
| Trust | High trust can start preparation. Missing or conflicting checks go to review. Confirmed scams block personal-data release. Neither a score nor a prior send grants permission for another action. |
| External effects | A recipient, channel, action, rendered text, answers and attachments form one version for approval. An edit, recipient change, expiry, block or revocation invalidates it. For owner-only alerts require prior opt-in by event class and verified destination. Log manual sends as owner-reported. |
| Inbound mail | Preserve prior labels and decisions, confirm destructive-looking moves, offer undo while recoverable. Do not request permanent-delete access. |
| Data and cost | Use synthetic fixtures in Git. Keep tokens, mail, candidate vault, document artifacts, private repo content and local environment files outside version control. Default spending authority is zero for new billable resources. |
| Working tree | Inspect status, instructions, current branch and tests first. Preserve unrelated changes and stage named paths. Keep real integrations disabled in previews and tests. |

## Checkpoint required after every phase

1. Read [progress](PROGRESS.md) and [next action](NEXT_STEP.md), identify the slice, acceptance IDs, baseline and allowed side effects. Record implementation and verification separately.
2. Run the slice tests and impacted regression suite. Capture commands, results, fixture/provider mode and failures. Only passing evidence can move a feature to **Tested**. An unverified provider remains unverified even if a fixture passes.
3. Update the matrix, PROGRESS.md and NEXT_STEP.md before the phase commit. Include scope, test evidence, blockers, outstanding operations and exactly one next slice. Review staged diff for unrelated changes, credentials and private artifacts. Commit working changes with a meaningful message.
4. Fetch or inspect the authorized branch, push the commit normally and verify its exact SHA at the remote ref (or prove ancestry if it advanced). Never force-push, rewrite shared history or overwrite unrelated files. Reconcile concurrent edits and rerun tests before any new push.
5. Check branch-to-project mappings, provider Git integrations, existing deployment records and SHA. For enabled branches, let a configured Git trigger fire once or trigger the existing authorized target if needed. Deploy frontend to Vercel, API and worker to Render. Creating billable infrastructure requires explicit approval of the estimate. A missing permission stops only that operation.
6. Verify provider revision and healthy status, dashboard sign-in, authenticated API readiness and a synthetic prepare/review flow with delivery disabled. Check worker heartbeat and backlog when applicable. Record actual URLs, revision, test outcome and failed components. On failure pause delivery, retain logs and use the last known compatible release with an additive schema. Never mark an unverified deployment successful.
7. Report commit hash, branch, remote verification, completed and tested features, blockers, next action and deployment URLs/status. Use the commit or final report for the current SHA and post-push observations. The next checkpoint may cite the prior hash directly without a self-referential commit loop.

## Definition of completion

Planning requires all seven documents, page coverage, traceable dispositions and valid internal references. Development requires passing acceptance tests through the normal entry point. Hosted release additionally requires verified push, health and a reversible deployment path. The roadmap distinguishes validation of the plan, a tested local application and a verified hosted release. [Roadmap](ROADMAP.md) · [Architecture](ARCHITECTURE.md) · [Cost plan](COST_PLAN.md)
