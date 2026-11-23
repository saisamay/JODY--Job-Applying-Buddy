# JODY next step

**Prompt 8 can compile and evaluate an owner-reviewed proposal.** Start with the application ID, resume version ID and baseline ID returned by the career proposal command. The [career architecture](ARCHITECTURE.md#career-intelligence-and-evidence-backed-drafts) documents the import, review, comparison and MCP boundaries.

1. Start with a synthetic golden application containing dates, education, employment, punctuation and an unresolved required field. Read the proposed fragment and its claim manifest through the private API. Check the current evidence review and exclusions before rendering.
2. Choose an owner-authorized template and pin the compiler and bundle. Compile in an isolated environment with bounded time, memory and file access. The current version stores an escaped content fragment. Preserve originals, keep private files outside Git, and record artifact digest, template and compiler revisions.
3. Implement owner-only PDF download and text extraction. Verify source-to-PDF fidelity, line citations, dates, page readability, tenant isolation and cache invalidation. Present outstanding questions for owner confirmation.
4. Evaluate ATS compatibility on extracted PDF text, publish the rubric and component scores, and bound any refinement attempts. Keep the existing qualification estimate separate. Any changed claim must pass the existing evidence checks before creating another version.
5. Run migrations, the offline suite, authorized local-model smoke, PDF golden checks and the authenticated browser tests. Update the requirements matrix and both checkpoint documents, commit, push normally, verify the remote SHA and check configured hosting.

The existing eight-step onboarding contracts remain available to the future Figma UI. The current offline evaluation missed a transactional-schema paraphrase. Collect independently labeled examples and benchmark a dedicated local embedding model before enabling automated decisions. A public-document smoke exercised the GitHub reader and the supplied portfolio page. Rich JavaScript portfolio content and private repository claims still need owner-selected snapshots and review.
