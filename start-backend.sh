#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="${SCRIPT_DIR}/backend"

cd "${BACKEND_DIR}"

if [[ -x "${BACKEND_DIR}/.venv/bin/python" ]]; then
  PYTHON="${BACKEND_DIR}/.venv/bin/python"
elif [[ -x "${SCRIPT_DIR}/.venv/bin/python" ]]; then
  PYTHON="${SCRIPT_DIR}/.venv/bin/python"
else
  python3 -m venv "${BACKEND_DIR}/.venv"
  PYTHON="${BACKEND_DIR}/.venv/bin/python"
fi

"${PYTHON}" -m pip install -r "${BACKEND_DIR}/requirements.txt"
"${PYTHON}" -m alembic upgrade head

exec "${PYTHON}" -m uvicorn app.main:app --reload
