#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="${ROOT_DIR}/backend"
DATA_ROOT="${YETAOS_DEMO_ROOT:-/tmp/yetaos}"
HOST="${YETAOS_HOST:-0.0.0.0}"
PORT="${YETAOS_PORT:-8000}"

mkdir -p "${DATA_ROOT}" "${DATA_ROOT}/workspaces" "${DATA_ROOT}/secrets" "${DATA_ROOT}/models"

# Demo mode defaults: local temp data paths and auth disabled unless explicitly set.
export YETAOS_MOCK_LXD="${YETAOS_MOCK_LXD:-1}"
export YETAOS_API_KEY="${YETAOS_API_KEY:-}"
export YETAOS_STORE_PATH="${YETAOS_STORE_PATH:-${DATA_ROOT}/containers.json}"
export YETAOS_WORKSPACES_DIR="${YETAOS_WORKSPACES_DIR:-${DATA_ROOT}/workspaces}"
export YETAOS_SECRETS_DIR="${YETAOS_SECRETS_DIR:-${DATA_ROOT}/secrets}"
export YETAOS_MODELS_DIR="${YETAOS_MODELS_DIR:-${DATA_ROOT}/models}"

cd "${BACKEND_DIR}"
echo "Starting mock server at http://127.0.0.1:${PORT}/"
exec uv run uvicorn app.main:app --host "${HOST}" --port "${PORT}"
