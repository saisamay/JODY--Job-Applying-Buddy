# Connect one integration at a time

This is the Prompt 5.5 operator guide for the existing private owner. The protected preview remains on its verified November 24 release. Run these new checks from the November 25 checkout on Ubuntu. They authenticate the local operator, exercise one provider, and print a short result. A passing check proves the capability named in the result. It does not activate ingestion, sending, hosted inference, chat pairing or account registration.

## 1. Prepare a private environment

1. Follow the Ubuntu setup in the [README](../README.md). Start the local API and web app with `./infra/run-local.sh`. Use the generated local owner key. Keep the hosted owner and encryption keys separate.
2. From the repository root, create an owner-only file outside the checkout. Keep the machine and backups encrypted. The following setup preserves an existing file.

   ```bash
   install -d -m 700 ~/.config/jody
   (umask 077; touch ~/.config/jody/providers.env)
   chmod 600 ~/.config/jody/providers.env
   ```
3. Edit that file locally using an editor or password-manager integration. Copy **only** the relevant variable names from [.env.example](../.env.example). Use shell-quoted values in the trusted file. For the checks, leave the local owner's `.env` in place. Avoid shell tracing, CLI arguments containing tokens, screenshots of credentials and `NEXT_PUBLIC_*` secrets.
4. Open a second terminal in the repository and load the protected environment. Run only the individual check you intend. Close this shell afterward.

   ```bash
   source .venv/bin/activate
   set -a
   source ./.env
   source ~/.config/jody/providers.env
   set +a
   export PYTHONPATH="$PWD/apps/api"
   python -m jody.provider_check --help
   ```

If the first connection fails, confirm the private API is listening at `127.0.0.1:8000` and the local owner key belongs to it. Authentication opens and closes an audited owner session. The verifier reads its user ID; it accepts no arbitrary tenant ID. Secrets for these operator checks live only in this shell and its short-lived process. Store actual per-user GitHub and AI keys in the authenticated local **Integrations → Private credentials** vault. The database encrypts them with AES-GCM and user/provider-bound associated data. Vault entry and verification are separate. The probe never copies its inputs into a tenant account.

## 2. Infrastructure and operator secrets

| Exact name | Configuration location and custodian | Verification and failure action |
|---|---|---|
| `DATABASE_URL` | Active migration login, Render API Environment → Blueprint internal DB reference. Local admin can use `POSTGRES_PASSWORD` and `POSTGRES_PORT` instead. | Current readiness checks Alembic and pgvector. Use the migration runbook for role or version failures. Leave this variable pointed at the existing database. |
| `JODY_DB_APP_PASSWORD`, `JODY_RUNTIME_DATABASE_URL` | Render generates the restricted role password. The bootstrap derives the runtime DSN and removes admin credentials before API startup. Local worker receives the restricted DSN separately. | Startup verifies row security is active. An admin role, missing grant or stale password must fail. Reconcile the role and credential together. |
| `REDIS_URL` | Render API → Environment, internal Key Value reference. Ubuntu Compose uses `REDIS_PORT` locally. | `/health/ready` must report both Redis and PostgreSQL true. Check the private network and credentials after a restart. PostgreSQL retains pending tasks. |
| `JODY_ENCRYPTION_KEY` | Backend operator only. Existing Render Environment secret or local 0600 file. Separate 32-byte hex key for each environment. | Verify decryption with the restore rehearsal. Wrong key means stop and recover the original key. Rotation requires an explicit re-encryption plan. |
| `JODY_OWNER_KEY` | Existing private preview or local bootstrap owner. Render backend or local 0600 file only. Future SaaS users never receive the operator key. | Sign in to JODY, inspect your workspace, then sign out. A stale session must return 401. |
| `API_BASE_URL` | Vercel project → Settings → Environment Variables → Preview. Server-side HTTPS Render origin. Local web uses the loopback API origin. | Sign-in shows readiness, workspace loads. Check the environment scope, HTTPS origin and Render cold start on 503. |
| `JODY_NEON_TEST_DATABASE_URL` | Neon Console → selected project → **disposable rehearsal branch** → Connect → direct connection, correct database and role. Put the PostgreSQL URL only in the operator file. Neon Auth stays disabled. | Run `python -m jody.provider_check neon`. Expect verified TLS, a read-only transaction and an available vector extension. For failure, check the direct hostname, role, trusted CA, wake-up and quota. A passing check does not copy data or install extensions. |

## 3. Gmail OAuth

1. Google Cloud Console → JODY project → Google Auth Platform → Audience. Keep External/Testing and the owner on the test-user list. Under Data Access keep only `https://www.googleapis.com/auth/gmail.readonly`. Confirm Gmail API is enabled.
2. Clients → existing **Web application** → Authorized redirect URIs. For the implemented operator check register this literal URL, including its port and path:

   ```text
   http://127.0.0.1:8765/api/v1/integrations/gmail/callback
   ```

   The path comes from `GMAIL_CALLBACK`, shared by the loopback verifier and the FastAPI route. The hosted URI for a future deployed authorization flow is **`https://jody-preview-api-xonu.onrender.com/api/v1/integrations/gmail/callback`**. The existing live release predates this route. On the new API a callback without a local verification ceremony is rejected. Register the hosted URL only when preparing that rollout. Authorized JavaScript origins can stay empty for this server-side flow. Neither Vercel's frontend origin nor a wildcard belongs in Redirect URIs.
3. Copy the web client values to `JODY_GOOGLE_CLIENT_ID` and `JODY_GOOGLE_CLIENT_SECRET` in the protected operator file. Set `JODY_GOOGLE_REDIRECT_URI` to the exact local URL above. Restart the check after editing the environment.
4. Run `python -m jody.provider_check gmail`. Open the printed, one-use local start link in the same machine's browser within five minutes. Select the intended Google test user and consent to read-only access. Expected result is **Gmail read-only profile and offline refresh verified**. The check exchanges the code with PKCE, refreshes the token and calls `users/me/profile`. It never reads message contents and discards both tokens on exit. Google can retain the user's consent. Revoke JODY under Google Account → third-party connections to withdraw that grant.
5. For `redirect_uri_mismatch`, compare scheme, IP literal, port, case, path and trailing slash. For `access_denied`, check test-user membership and consent. For `invalid_grant`, start a fresh browser check and verify time, client and redirect. External/Testing refresh tokens for Gmail normally expire in seven days. If a prior grant has extra scopes, review it in Google Account and reauthorize read-only. Never fix a read check by adding send or modify scopes. Public rollout requires Google's restricted-scope review and potentially a security assessment for server-side storage/transmission. [Web server OAuth](https://developers.google.com/identity/protocols/oauth2/web-server) · [Token expiry](https://developers.google.com/identity/protocols/oauth2#expiration) · [Gmail scopes](https://developers.google.com/workspace/gmail/api/auth/scopes)

## 4. Optional providers

Each row is independently repeatable after loading the file in step 1. Run `python -m jody.provider_check NAME` with the name in the first column. These requests use official read endpoints. They incur no generation or delivery calls.

| NAME | Where to obtain it and exact local variables | Successful evidence | Common failures and recovery |
|---|---|---|---|
| `github` | GitHub Settings → Developer settings → Personal access tokens → Fine-grained. Select only the intended repo, Metadata read and Contents read. `JODY_GITHUB_TOKEN`, `JODY_GITHUB_REPOSITORY` (`owner/repository`). Keys belong to the individual account. | Selected repository metadata readable. | 401 expired PAT, 404 wrong selection or organization approval, 403 policy/quota. Reissue with the same limited scope. Record the owner's actual 90-day expiry. |
| `resume_git` | Same variables and selected private master repository. Add `JODY_RESUME_GIT_REF` (full 40-hex commit SHA) and `JODY_RESUME_GIT_PATH` (exact relative file such as the master TeX path). Same PAT can be entered locally in the separate Resume Git vault slot. | Pinned resume source readable. No file saved. | Check case, SHA, path, Contents read and repo approval. A metadata check alone does not prove file access. Never request write access or paid Overleaf sync. [Contents API](https://docs.github.com/en/rest/repos/contents#get-repository-content) |
| `gemini` | Google AI Studio → API keys, intended free project. `JODY_GEMINI_API_KEY`. BYOK belongs to the user. | Model catalog contains a generation-capable model. | 400/403 check API restriction, project, eligibility and region. Review active limits in AI Studio. A list response does not establish free generation entitlement. |
| `groq` | Groq Console → API Keys, intended Free organization. `JODY_GROQ_API_KEY`. User BYOK. | Active model catalog readable. | 401 replace key, 403 check organization/model policy, 429 respect Retry-After. Confirm project limits in Console → Limits. |
| `openrouter` | Optional OpenRouter Settings → Keys, separate restricted key, zero-spend policy. `JODY_OPENROUTER_API_KEY`. User BYOK. | Key recognized and a zero-input/output-price free variant listed. | 401 invalid key, 402/429 wait or disable. Never top up or fall back to a paid model automatically. |
| `ollama` | Ubuntu host running Ollama → installed model list. `JODY_OLLAMA_BASE_URL=http://127.0.0.1:11434`, `JODY_CHAT_MODEL`, `JODY_EMBED_MODEL`, `JODY_AI_PROVIDER` and optional `JODY_MODEL_REVISION`, `JODY_AI_DAILY_CALLS`. No API key. | Configured model installed. For synthetic inference use the optional live test in the AI guide. | Connection refused, missing model, memory pressure or timeout. Leave optional inference off, queue the job or use an explicitly authorized alternative. |
| `telegram` | Telegram → BotFather → intended bot's API token. Operator sets `JODY_TELEGRAM_BOT_TOKEN` once on the backend. Users never supply the shared bot token. | `getMe` confirms a bot identity. No message sent. | 401 rotate at BotFather. Having opened the bot chat does not link the owner to a JODY user. Complete single-use chat linking once implemented. [Bot API](https://core.telegram.org/bots/api#getme) |
| `ntfy` | Optional private ntfy instance with authentication and topic ACLs. `JODY_NTFY_BASE_URL` is its trusted HTTPS origin; `JODY_NTFY_TOKEN` is the user's scoped bearer token. | Authenticated account verified via `GET /v1/account`. | 401/403 check token, server version, auth and private-topic ACL. Never fall back to a public topic. Topic delivery requires a later separate test. [Access control](https://ntfy.sh/docs/config/#access-control) |

**WhatsApp and LinkedIn** have no supported credential environment variables in this release. No login password, session cookie or QR secret belongs in this file. Use explicitly authorized account workflows described in the [integration contract](INTEGRATIONS.md). Dashboard notifications need only the user's JODY session.

## 5. Record the result

For each provider record the date, operator/account, provider name, check performed and outcome. Omit tokens, codes, email addresses and response bodies. A read check can pass while the product adapter remains disabled. For network/TLS failures, confirm DNS, clock, certificates and connectivity. On 429 wait for the provider reset; on 401/403 stop and reauthorize. To disconnect a saved local user credential, choose its provider under Integrations, confirm removal, then revoke it at the provider. Runtime subscriptions, callback tokens and account deletion are separate lifecycle work. [Onboarding and deletion](ONBOARDING.md)

## Prompt 6 Gmail intake

Follow [private per-user enrollment](GMAIL_INTEGRATION.md) for the exact loopback frontend callback. The client ID and secret are reused. Stored Gmail vault text and the operator verifier cannot enroll a mailbox. Optional AI model environment and per-tenant consent are listed in [Gmail ingestion](GMAIL_INGESTION.md).

## Local provider loading

Store literal KEY=value lines in `~/.config/jody/providers.env` or set `JODY_PROVIDERS_FILE` to an alternate private regular file. The file must be owned by the running user and have no group/other permissions (0600 or 0400). Symbolic links are rejected. Outer matching quotes are optional. Shell commands, substitutions and variable expansion are never evaluated. Keep the file outside Git. Explicit process settings take precedence over repository defaults, which take precedence over the provider file. A missing optional file leaves those integrations unconfigured.

The local API/worker loader recognizes the Google web client, loopback Ollama origin and cloud model identifiers. Shared operator API keys, the Telegram token, GitHub PAT and Neon test DSN are intended for authenticated operator probes. Cloud Gmail extraction still requires tenant consent, a per-tenant vault entry and confirmed free-only configuration. Saving provider settings enables no polling timer. The frontend launcher strips recognized provider settings. Production uses its existing service environment.
