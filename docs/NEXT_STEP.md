# JODY next step

**Phase 2A: import and review synthetic GitHub project evidence locally.** Begin with the current github_projects table and user-scoped access pattern. Use reviewed repository snapshots supplied as fixtures, including a commit, path and attribution. Keep live sync, generated resumes and delivery disabled.

1. Compare HEAD to origin/main, read the latest [progress](PROGRESS.md), and review F06, I01 and S01 in the [requirements matrix](REQUIREMENTS_MATRIX.md).
2. Add the minimum migration for versioned evidence items and explicit owner review. Link each item to the project with a tenant-aware foreign key.
3. Provide an authenticated local import and review path. Repeated imports of the same snapshot must preserve one revision. Unsupported metrics and unverifiable skill claims must remain unapproved.
4. Demonstrate provenance, revocation and second-tenant denial through the normal API. Run the existing migration, pause, isolation and browser tests from the [runbook](../README.md).
5. Update the ledgers, commit and push normally, verify the remote revision, CI and deployment disposition, and report the next slice.
