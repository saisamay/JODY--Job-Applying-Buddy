# JODY next step

**Prompt 4 can implement the Figma UI on the existing profile and onboarding contracts.** Resume on the verified main checkpoint, read [progress](PROGRESS.md) and inspect the new UI brief before changing screens.

- Use the existing private session and the server-side candidateApi in apps/web/lib/api.ts. GET /api/v1/candidate returns identity, preferences, suggestions and origins, verified-field evidence, available resumes, permissions, revision and ordered step statuses. Types come from packages/shared/api.d.ts.
- Render the eight steps returned by the API. Show skip only on optional steps. Keep proposed values visually separate until the owner accepts them. Provide explicit field review and final confirmation actions. A portfolio URL or a GitHub username does not establish skills or achievements.
- Save against the displayed revision with an idempotency key. Reload on conflict and preserve the user's unsaved edits for review. Refresh after changes to automation permissions. Use an authenticated server-side upload path that can handle the 5 MiB PDF limit.
- Use the preparation preview to display missing required questions and let the owner explicitly select a role-specific resume. Preserve pause and approval controls.
- Test keyboard/mobile navigation, skip and resume, stale edits, the suggestion-to-review flow and private file access. Run the existing migration, API and browser suites and complete the normal Git checkpoint.

The [Ubuntu runbook](../README.md) documents the route map, file limits and confirmation semantics. Live evidence sync and delivery remain later slices.
