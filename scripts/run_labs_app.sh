#!/usr/bin/env bash

set -euo pipefail

MODE="${1:-dev}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONTEND_DIR="$ROOT_DIR/labs_app/frontend"
PYTHON_BIN="${PYTHON:-python}"
FLASK_PORT="${FLASK_RUN_PORT:-4000}"

if [ ! -d "$FRONTEND_DIR" ]; then
  echo "labs_app/frontend is missing. Did you clone the full repository?"
  exit 1
fi

if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
  echo "Installing frontend dependencies (yarn install)…"
  (cd "$FRONTEND_DIR" && yarn install)
fi

start_flask() {
  export FLASK_APP="labs_app.api.app"
  export FLASK_RUN_PORT="$FLASK_PORT"
  echo "Starting Flask backend on http://localhost:${FLASK_PORT}/"
  cd "$ROOT_DIR"
  "$PYTHON_BIN" -m flask run --port "$FLASK_PORT"
}

if [ "$MODE" = "prod" ]; then
  echo "Building frontend (production assets)…"
  (cd "$FRONTEND_DIR" && REACT_APP_API_HOST=/api yarn build)
  start_flask
  exit 0
fi

if [ "$MODE" != "dev" ]; then
  echo "Unknown mode: $MODE"
  echo "Usage: $0 [dev|prod]"
  exit 1
fi

echo "Running labs app in development mode."
echo "- Flask API on port ${FLASK_PORT}"
echo "- React dev server on port 3000"

cleanup() {
  if [ -n "${FLASK_PID:-}" ] && kill -0 "$FLASK_PID" 2>/dev/null; then
    kill "$FLASK_PID"
  fi
}

trap cleanup EXIT INT TERM

start_flask &
FLASK_PID=$!

echo "Waiting for Flask backend to become ready…"
attempt=0
until curl --silent --fail "http://127.0.0.1:${FLASK_PORT}/health" >/dev/null 2>&1; do
  attempt=$((attempt + 1))
  if ! kill -0 "$FLASK_PID" 2>/dev/null; then
    echo "Flask process exited early. Check the logs above for details."
    exit 1
  fi
  if [ "$attempt" -ge 60 ]; then
    echo "Backend did not respond after 60 attempts (~60s)."
    exit 1
  fi
  sleep 1
done
echo "Flask backend is ready."

export REACT_APP_API_HOST="http://localhost:${FLASK_PORT}/api"
cd "$FRONTEND_DIR"
yarn start
