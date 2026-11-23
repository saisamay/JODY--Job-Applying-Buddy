#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ -f .env ]]; then
  set -a
  source .env
  set +a
fi
export PYTHONPATH="$PWD/apps/api"
export NEXT_TELEMETRY_DISABLED=1

if [[ "${JODY_USE_EXISTING_SERVICES:-0}" != 1 ]]; then
  docker compose --env-file .env -f infra/compose.yaml up -d --wait
fi
.venv/bin/alembic upgrade head
.venv/bin/python apps/worker/check.py

.venv/bin/uvicorn jody.main:app --host 127.0.0.1 --port 8000 --no-access-log &
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
(unset POSTGRES_PASSWORD DATABASE_URL REDIS_URL JODY_OWNER_KEY; cd apps/web && exec ../../node_modules/.bin/next "${web_args[@]}" --hostname 127.0.0.1 --port 3000) &
web_pid=$!
wait -n "$api_pid" "$web_pid"
