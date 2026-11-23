# JODY next step

**Next action when implementation is requested:** build phase 1A, the local authenticated manual job intake round trip. Stop at that vertical slice and its checkpoint. Phase 0 delivers architecture and plans.

## Resume from the checkpoint

Run these from the repository root before editing. Resolve any unexpected remote or local changes without overwriting them. The recovered local source PDF may appear as untracked and is outside the planned public commit.

```sh
git status --short --branch
git log -1 --format='%H %s'
git ls-remote origin refs/heads/main
```

Read the [build contract](BUILD_CONTRACT.md), [progress](PROGRESS.md) and the F01–F03, F19, T01, T03, T05, T09, S05 and D01 rows in the [matrix](REQUIREMENTS_MATRIX.md). This slice contributes to those rows. Broader acceptance criteria continue into later phases.

## Scope and acceptance

1. Check Docker daemon and Node tooling, choose and pin a compatible project toolchain, then create the smallest web/API/contracts workspace and a local Postgres service. Record exact startup and test commands. Use synthetic data only.
2. Create the owner, source observation, job and minimal event migrations with tenant-scoped keys, a closed local owner session, and authenticated POST /api/v1/jobs/manual and GET /api/v1/jobs. Limit 1A intake to pasted job text and an optional source URL retained as text.
3. Implement one dashboard input and the persisted pipeline list. Test through the normal UI with a synthetic vacancy. Reload and restart the API. The owner still sees one job. Retrying the same command must keep one record.
4. Test empty input, unauthenticated access, a second identity attempting to list/read another owner's jobs and a duplicate concurrent import. Record test output and whether the build passes. Leave provider calls disabled.
5. Complete the phase checkpoint in the build contract. Update both ledgers with evidence and unresolved gates, commit working changes, push and verify the authorized ref, check deployment disposition and report the SHA, URLs/status, blockers and next action.

Slice 1B will add the durable outbox, queue consumer, audit and dispatch pause tests after 1A is verified. [Roadmap](ROADMAP.md)
