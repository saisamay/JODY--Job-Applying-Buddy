# JODY next step

**Phase 1B: build and verify the durable local task outbox.** The first slice should process one inert synthetic task from a transaction through Redis to a persisted completion. The current worker probe verifies connectivity. It does not consume work.

1. Read the [latest checkpoint](PROGRESS.md), [build contract](BUILD_CONTRACT.md) and T04/S03 in the [matrix](REQUIREMENTS_MATRIX.md). Compare local HEAD to origin/main and preserve any unrelated changes.
2. Add an additive Alembic migration for owner-scoped tasks and outbox records. Commit the domain record and outbox item in one transaction, with a unique operation key.
3. Implement a Python relay and a separately runnable worker. Use Redis only for task references. Persist claims, attempts and terminal results in PostgreSQL.
4. Demonstrate duplicate delivery, worker restart, Redis loss/rebuild, owner isolation and global pause on a synthetic action. Keep all provider effects disabled.
5. Re-run phase 1A regression checks from the [Ubuntu runbook](../README.md), record test evidence and remaining acceptance criteria, then follow the commit/push/verify/deployment checkpoint.

The local workspace, API and typed contracts are already present. Future hosted operation still requires owner-approved resources and provider targets.
