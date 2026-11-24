# Private preview deployment

JODY uses a protected Vercel Preview deployment for Next.js and one Render Free Docker web service. Both communicate over provider-managed HTTPS. The browser posts same-origin Next server actions. Only the frontend server calls FastAPI. The API issues an eight-hour opaque owner session and stores its digest. Next sets a host-only, HttpOnly, Secure, SameSite=Strict cookie. FastAPI grants no cross-origin browser access. Its health endpoints are public, and workspace data requires a bearer session.

## Environment checklist

| Service and scope | Variable | Value or source |
|---|---|---|
| Vercel, Preview only | `API_BASE_URL` | Actual Render service HTTPS origin after readiness succeeds. Server-side variable. |
| Render API | `DATABASE_URL` | Blueprint reference to the internal PostgreSQL migration connection. |
| Render API | `JODY_DB_APP_PASSWORD` | Generated once by Render. Used for the dedicated unprivileged runtime role. |
| Render API | `REDIS_URL` | Blueprint reference to internal Key Value. |
| Render API | `JODY_OWNER_KEY` | Independent 32-byte random owner login key, encoded as hex. Keep in the owner’s password manager. |
| Render API | `JODY_ENCRYPTION_KEY` | A different 32-byte random key, hex encoded. Retain securely with any encrypted backup. |
| Render API | `JODY_PRIVATE_PREVIEW=1`, `JODY_AI_PROVIDER=mock` | Set in the Blueprint. No worker, scheduler or external model is deployed. |
| Render API | `PORT` | Assigned by Render. The image defaults to 10000 for local use. |

Generate each manual secret separately using a password manager or `openssl rand -hex 32`. Use only preview-specific credentials. Integration tokens and database credentials belong off Vercel. Store the keys outside the checkout and enter them into the Render secret fields. Restoring encrypted records requires the original encryption key.

## Apply the checkpoint

1. Use the confirmed Render workspace and an eligible personal Vercel Hobby account. In Render billing, verify available free instance hours, pipeline minutes, bandwidth and a zero spend limit for any supplementary usage. Confirm that the free Postgres and Key Value slots are available.
2. Open the Blueprint for the pushed branch, review the exact resource plan, and enter the two manual secrets. Apply only if the web service, database and Key Value are all Free and the estimate fits the approved budget. All three use Oregon for private connectivity. PostgreSQL and Key Value block external connections. Use a fresh dedicated preview database. [Render Blueprint import](https://dashboard.render.com/blueprint/new?repo=https://github.com/saisamay/JODY--Job-Applying-Buddy)
3. The container startup runs Alembic up to head under a transaction-scoped PostgreSQL advisory lock. It provisions a restricted login under a second lock, removes admin credentials from the API process environment, and starts one Uvicorn process on the assigned port. A failure leaves the service unavailable. For a retry, retain the database, runtime-role password and encryption key. A runtime password change requires updating the PostgreSQL role password as well. The owner login checks active tenant row security before the service accepts traffic.
4. Copy the actual HTTPS service URL from Render. Request `/health/live` and `/health/ready`. Readiness requires the migration revision, pgvector extension and Redis ping. Use a signed request to verify the owner session as described below.
5. From the repository root, use `vercel login` and `vercel link` for the intended Hobby project. In Project Settings set Root Directory to `apps/web`, enable access to source files outside the root for npm workspaces and shared types, choose Next.js and Node 24.x, and retain the default install command. The checked-in Vercel configuration uses the web workspace build script. Enable Vercel Authentication with Standard Protection before deployment. Leave the production domain unused for this private preview. Use preview-only CLI deployments. Git deployments are disabled in the configuration.
6. Run `vercel env add API_BASE_URL preview` and paste the verified Render HTTPS origin at the prompt. Run `vercel deploy` from the linked repository root. Inspect the returned deployment URL with `vercel inspect <preview-url>`. Verify an anonymous visit reaches Vercel Authentication. Reapply the Preview deployment after changing its environment. [Vercel deployment protection](https://vercel.com/docs/deployment-protection)

## Verify the hosted release

Run these checks from the repository root. Set `WEB_BASE_URL` to the assigned Vercel Preview URL, `API_BASE_URL` to the assigned Render URL, and supply `JODY_OWNER_KEY` from the preview secret store. Supply an authorized browser's Playwright storage-state file using `JODY_BROWSER_STATE`, or inject an authorized short-lived Vercel OIDC token for the protected deployment. Keep browser state outside Git. Vercel trusted-source access is scoped to the project and environment. [Protected deployment access](https://vercel.com/docs/deployment-protection)

```bash
curl --fail --retry 5 --retry-all-errors "$API_BASE_URL/health/ready"
vercel curl / --deployment "$WEB_BASE_URL"
npx playwright install chromium
node tests/preview.mjs
```

The smoke test signs in, verifies cookie attributes and read-only API access, checks the automation lock, navigates the dashboard at 390 and 1440 pixels, signs out, and checks revocation. A session login and logout leave audit records. An anonymous readiness or landing-page response alone does not verify the private workflow. A build failure or partial rollout can be recovered by redeploying a compatible earlier Git revision. Preserve the database during rollback and check migration compatibility first.

## Persistence, privacy and cost

- Free Render PostgreSQL is limited to one active instance per workspace and 1 GB. It expires after 30 days. Access stops at expiration. Render deletes it after a further 14-day upgrade grace period. Managed backups and managed connection pooling are unavailable. Keep original resumes and other irreplaceable data elsewhere. An encrypted export before expiry is the owner's responsibility. [Render free limits](https://render.com/docs/free)
- The free web service can sleep after 15 minutes of inactivity and may take about a minute to wake. Its filesystem is ephemeral. Free Key Value loses all entries on restart. Durable application state and encrypted uploaded PDFs are in PostgreSQL. Free web compute, bandwidth and pipeline allowances are shared at the workspace level. [Render free limits](https://render.com/docs/free)
- Vercel Hobby is for eligible personal, noncommercial use. Budget and function limits apply. The preview frontend accepts PDFs up to 4 MiB to leave room for request framing within the default function payload limit. [Vercel Hobby](https://vercel.com/docs/plans/hobby) · [Function limits](https://vercel.com/docs/functions/limitations)
- The server locks automation even for the authenticated owner. External fetches, credential connection writes, background task creation and dispatch, enabling outbound mail, and destructive mailbox settings are disabled. Qualification estimates use the offline fixture provider. The preview does not send emails, apply to jobs, connect to LinkedIn or WhatsApp, or sync Gmail.
