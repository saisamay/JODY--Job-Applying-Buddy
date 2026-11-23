# JODY progress

## Phase 0 · Planning checkpoint · 2026-11-23

| Item | Observed state |
|---|---|
| Starting point | Empty checkout and unborn main. The authorized public GitHub origin initially advertised no refs. No source, existing test command, CI workflow, environment template or deployment manifest was present. |
| Source | Recovered the formerly titled AutoApply AI PDF from the owner's local Downloads, verified the title and all eight printed pages and copied it locally to docs/JODY_PRD.pdf. SHA-256 and the truncated DDL boundary are in the build contract. Only the seven planning documents are intended for this public Git commit. |
| Planning output | Contract, 55-row requirements matrix, component and route design, private MVP and production roadmap, cost plan and two handoff ledgers. All application work is outstanding. |
| Local tooling | Git, Node/npm, Docker CLI, PostgreSQL client and PDF extraction tools found. Tectonic, Redis server and Vercel/Render CLIs were absent from PATH. Runtime services and Docker daemon have not been qualified. |
| GitHub | Public repo metadata readable, local HTTPS Git credentials and gh login unavailable. Existing SSH agent successfully authenticated to GitHub on port 443. Authorized target is saisamay/JODY--Job-Applying-Buddy, branch main. |
| Design and portfolio | Figma screenshot returned for node 131:1408. Architecture records observed layout cues. The portfolio URL resolved, but the web reader returned no extractable text. No candidate fact was imported or verified. |
| Integrations | GitHub, Figma, Gmail and Render connector tools are exposed to the development session. No personal mailbox data was accessed. Render reported no selected workspace. No Vercel connector or project link was found. Telegram, resume Git, portal access and runtime credentials are unconfigured in the repository. |
| Deployment evidence | Initial public GitHub checks found zero workflows and deployments. No application or provider target is defined in this checkout. External account-level links are unverified. No infrastructure was provisioned. |
| Application tests | No application exists at this checkpoint. Zero runtime features have been verified. |

## Verification record

A local Python validation against the original PDF and Markdown passed. It found seven documents, 16 resolving local links, 55 unique IDs with six populated fields each, valid priority/status values and no undefined requirement references. PDF text extraction matched eight numbered footers and the source SHA-256. Parsing page 7 and comparing method/path pairs against the architecture matched all 18. The screenshot and rendered page 6 were also visually inspected.

For a repeat check, use `sha256sum docs/JODY_PRD.pdf`, `pdfinfo docs/JODY_PRD.pdf`, and `pdftotext -f 7 -l 7 -layout docs/JODY_PRD.pdf -` to compare the source ledger. Run `git diff --cached --check` and inspect staged paths and secret signatures before committing. The phase report supplies the SHA and post-push observations.

Use `git log -1 --format='%H %s' -- docs/PROGRESS.md` to identify the commit containing this checkpoint. The current commit cannot embed its own SHA. For each later phase append the prior verified SHA, current requirements and test commands/results, any real-provider validation, push/deploy evidence or blockers, and the next action. Keep phase 0's baseline as historical evidence.

## Outstanding gates

The next development slice uses fixtures and can run locally after the owner starts implementation. Real candidate evidence, resume template, provider entitlements, retention choices and hosting budget belong to later gates. Hosting requires an identified Vercel project and confirmed Render workspace/service mapping with deployment read/trigger access. Any billable addition needs a separately approved estimate. [Next action](NEXT_STEP.md)
