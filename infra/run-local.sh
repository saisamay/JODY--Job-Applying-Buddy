#!/usr/bin/env bash
set +x
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH="$PWD/apps/api"
provider_names=$(.venv/bin/python -c 'from jody.local_providers import NAMES; print(" ".join(sorted(NAMES)))')
declare -A provider_overrides=()
for name in $provider_names JODY_PROVIDERS_FILE; do
  if [[ -v $name ]]; then provider_overrides[$name]=${!name}; fi
done
if [[ -f .env ]]; then
  set -a
  source .env
  set +a
fi
for name in "${!provider_overrides[@]}"; do export "$name=${provider_overrides[$name]}"; done
export NEXT_TELEMETRY_DISABLED=1

if [[ "${JODY_USE_EXISTING_SERVICES:-0}" != 1 ]]; then
  docker compose --env-file .env -f infra/compose.yaml up -d --wait
fi
.venv/bin/alembic upgrade head
.venv/bin/python -m jody.provision
.venv/bin/python apps/worker/check.py

(
  # Derive the restricted URL before removing administrative credentials from the API process.
  JODY_RUNTIME_DATABASE_URL="$(.venv/bin/python -c 'from jody.config import runtime_url; print(runtime_url().render_as_string(hide_password=False))')"
  export JODY_RUNTIME_DATABASE_URL
  unset DATABASE_URL POSTGRES_PASSWORD JODY_DB_APP_PASSWORD
  exec .venv/bin/python -m jody.local_providers .venv/bin/uvicorn jody.main:app --host 127.0.0.1 --port 8000 --no-access-log
) &
api_pid=$!
web_pid=""
cleanup() {
  if [[ -n "$web_pid" ]]; then kill "$web_pid" 2>/dev/null || true; fi
  kill "$api_pid" 2>/dev/null || true
  wait || true
}
trap cleanup EXIT
trap 'exit 130' INT TERM
for attempt in {1..30}; do
  if ! kill -0 "$api_pid" 2>/dev/null; then wait "$api_pid"; exit 1; fi
  if curl -fsS http://127.0.0.1:8000/health/ready >/dev/null 2>&1; then break; fi
  sleep 1
done
curl -fsS http://127.0.0.1:8000/health/ready >/dev/null

if [[ "${JODY_WEB_MODE:-dev}" == start ]]; then
  web_args=(start)
else
  web_args=(dev --webpack)
fi
(unset JODY_TRUST_EMPLOYERS JODY_TRUST_PUBLIC_CHECKS $provider_names JODY_ENCRYPTION_KEY JODY_DB_APP_PASSWORD JODY_RUNTIME_DATABASE_URL POSTGRES_PASSWORD DATABASE_URL REDIS_URL JODY_OWNER_KEY \
  JODY_NEON_TEST_DATABASE_URL JODY_GOOGLE_CLIENT_SECRET JODY_GOOGLE_CLIENT_ID \
  JODY_GITHUB_TOKEN JODY_TELEGRAM_BOT_TOKEN JODY_GEMINI_API_KEY JODY_GROQ_API_KEY \
  JODY_OPENROUTER_API_KEY JODY_NTFY_TOKEN; cd apps/web && exec ../../node_modules/.bin/next "${web_args[@]}" --hostname 127.0.0.1 --port 3000) &
web_pid=$!
wait -n "$api_pid" "$web_pid"
