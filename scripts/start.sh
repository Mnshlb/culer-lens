#!/usr/bin/env bash
# One command from a fresh clone to a running app: `make start`.
#
# Installs what is missing, builds the data, models and database on the first
# run, builds the web app when its code changed, then serves the API and the
# web app together until Ctrl+C.
#
#   API_PORT=8001 WEB_PORT=3001 make start   # other ports
#   NO_BROWSER=1 make start                  # do not open a browser tab
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

API_PORT="${API_PORT:-8000}"
WEB_PORT="${WEB_PORT:-3000}"
API_URL="http://localhost:${API_PORT}"
WEB_URL="http://localhost:${WEB_PORT}"
WEB="$ROOT/apps/web"

say() { printf '\033[1m▸ %s\033[0m\n' "$*"; }
fail() { printf '\033[31m✗ %s\033[0m\n' "$*" >&2; exit 1; }

# --- prerequisites -------------------------------------------------------------

command -v uv >/dev/null || fail "uv is not installed: https://docs.astral.sh/uv/getting-started/installation/"
command -v node >/dev/null || fail "Node.js is not installed (20.9 or newer): https://nodejs.org"
node -e 'const [a, b] = process.versions.node.split(".").map(Number); process.exit(a > 20 || (a === 20 && b >= 9) ? 0 : 1)' \
  || fail "Node.js $(node --version) is too old: 20.9 or newer is needed"

port_busy() { lsof -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1; }
port_busy "$API_PORT" && fail "port $API_PORT is in use (another copy running?). Choose another: API_PORT=8001 make start"
port_busy "$WEB_PORT" && fail "port $WEB_PORT is in use (another copy running?). Choose another: WEB_PORT=3001 make start"

# --- dependencies ------------------------------------------------------------

if [ ! -x .venv/bin/python ]; then
  say "Installing Python dependencies (first run only)"
  uv sync --all-extras --frozen
fi
if [ ! -d "$WEB/node_modules" ]; then
  say "Installing web dependencies (first run only)"
  (cd "$WEB" && npm ci --no-audit --no-fund)
fi

# --- data, models, database -----------------------------------------------------

if [ -z "${DATABASE_URL:-}" ] && [ ! -f barca.db ]; then
  say "Building data, models and database (first run only, about 4 minutes, needs internet)"
  echo "  StatsBomb asks users of its open data to register at https://statsbomb.com/resource-centre"
  make --no-print-directory pipeline
fi

# --- web build ----------------------------------------------------------------

stamp="$WEB/.next/api-url"
needs_build=0
if [ ! -f "$WEB/.next/BUILD_ID" ] || [ "$(cat "$stamp" 2>/dev/null)" != "$API_URL" ]; then
  needs_build=1
elif [ -n "$(find "$WEB/src" "$WEB/public" "$WEB/package.json" "$WEB/next.config.ts" -newer "$WEB/.next/BUILD_ID" -print -quit)" ]; then
  needs_build=1
fi
if [ "$needs_build" = 1 ]; then
  say "Building the web app"
  (cd "$WEB" && NEXT_PUBLIC_API_URL="$API_URL" npm run build --silent >/dev/null)
  echo "$API_URL" > "$stamp"
fi

# --- run ------------------------------------------------------------------------

pids=()
cleanup() {
  trap - INT TERM EXIT
  echo
  say "Stopping"
  for pid in ${pids[@]+"${pids[@]}"}; do kill "$pid" 2>/dev/null || true; done
  wait 2>/dev/null || true
}
trap cleanup INT TERM EXIT

say "Starting the API on $API_URL"
CORS_ORIGINS="$WEB_URL,http://127.0.0.1:${WEB_PORT}" \
  .venv/bin/uvicorn app.main:app --app-dir apps/api --host 127.0.0.1 --port "$API_PORT" --log-level warning &
pids+=($!)

say "Starting the web app on $WEB_URL"
(cd "$WEB" && exec ./node_modules/.bin/next start --port "$WEB_PORT" >/dev/null) &
pids+=($!)

for _ in $(seq 1 60); do
  if curl -fs "$API_URL/health" >/dev/null && curl -fs -o /dev/null "$WEB_URL"; then
    ready=1
    break
  fi
  sleep 0.5
done
[ "${ready:-0}" = 1 ] || fail "the servers did not start; see the messages above"

echo
say "Culer Lens is running"
echo "  App:       $WEB_URL"
echo "  API docs:  $API_URL/docs"
echo "  Press Ctrl+C to stop."
echo

if [ -z "${NO_BROWSER:-}" ]; then
  if command -v open >/dev/null; then open "$WEB_URL"
  elif command -v xdg-open >/dev/null; then xdg-open "$WEB_URL" >/dev/null 2>&1 || true
  fi
fi

wait
