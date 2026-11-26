# Private Gmail connection

Prompt 6 runs locally with the existing private owner login. The deployed API keeps its automation lock. The operator's previous profile/refresh probe checked a different ceremony and discarded its grant.

1. In Google Auth Platform → Clients → the existing Web client → Authorized redirect URIs, **add** `http://127.0.0.1:3000/gmail/callback`. Keep the previous port-8765 verifier URI. Use the literal IP when opening the frontend. JavaScript origins can stay empty. The authenticated Next callback forwards the code to FastAPI by POST. The older FastAPI GET path in the Prompt 5.5 guide is reserved for the operator workflow.
2. Keep Gmail API enabled, the External/Testing test-user allowlist and only `https://www.googleapis.com/auth/gmail.readonly`. An External/Testing grant may expire after seven days. Reconnect using the same Google account. Switching accounts requires disconnecting first. [Google OAuth guidance](https://developers.google.com/identity/protocols/oauth2/web-server)
3. On Ubuntu use the existing local PostgreSQL/Redis environment from the README. For the API, import **only** `JODY_GOOGLE_CLIENT_ID` and `JODY_GOOGLE_CLIENT_SECRET` from the owner's mode-0600 provider file. With the existing trusted shell-format file use the following command from the repository. This allowlists variables in a subshell and keeps unrelated provider secrets out of the server. Confirm the local database target before startup, which upgrades it. Use loopback for both web and API.

   ```bash
   (
     set +x
     readarray -t google_client < <(
       source "$HOME/.config/jody/providers.env"
       printf '%s\n' "$JODY_GOOGLE_CLIENT_ID" "$JODY_GOOGLE_CLIENT_SECRET"
     )
     export JODY_GOOGLE_CLIENT_ID="${google_client[0]}" JODY_GOOGLE_CLIENT_SECRET="${google_client[1]}"
     unset google_client
     JODY_USE_EXISTING_SERVICES=1 JODY_WEB_MODE=start ./infra/run-local.sh
   )
   ```

   Build with `npm run build` first. The API uses existing `JODY_ENCRYPTION_KEY`, restricted runtime DB and owner session configuration. The enrollment callback is fixed to loopback. `JODY_GOOGLE_REDIRECT_URI` controls the old operator verifier only. Keep the Google secret on the backend. Use query-free access logs on any proxy. The local API runs with access logging disabled and Next suppresses callback request logging.
4. Sign in at `http://127.0.0.1:3000`. In **Gmail updates**, save exact sender addresses and optional Gmail label ID and subject phrase. Choose 1–7 days and 1–25 initial messages. Resume the global gate locally for authorized reads. **Connect Gmail** opens Google consent. A five-minute, single-use state digest and encrypted PKCE verifier bind the return to the initiating tenant and live session. The scoped HttpOnly return cookie is cleared on callback. A successful exchange verifies the scope and mailbox identity before storing an AES-GCM encrypted refresh token. Access tokens remain process-local.
5. Compare the displayed account before authorizing a read. A client configuration, legacy vault entry or operator check alone cannot establish a Gmail connection. For a redirect mismatch check scheme, IP, port, path and trailing slash. For declined/expired consent start a new connection. For missing offline credentials check previous Google grants. A missing replacement refresh token requires validation of the existing same-account grant.
6. **Disconnect Gmail** clears credentials, filters, cursor and pending authorization and cancels outstanding reads. A successful Google revocation displays **Revoked**. If only local removal succeeded, use Google Account → Third-party connections to remove JODY. Google may return the same invalid-grant error for external revocation and expiry. Both require reconnection.

Follow the shadow-run gate in [Gmail ingestion](GMAIL_INGESTION.md) before reading actual messages.
