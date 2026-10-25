#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"
VENV="$BACKEND/.venv"

command -v python3 >/dev/null 2>&1 || { echo "[Hel] Python 3 не найден"; exit 1; }
command -v npm >/dev/null 2>&1 || { echo "[Hel] npm не найден"; exit 1; }

mkdir -p "${HOME}/.config/project_hel"
[ -f "${HOME}/.config/project_hel/.env" ] || cp "$ROOT/.env.example" "${HOME}/.config/project_hel/.env"

if [ ! -x "$VENV/bin/python" ]; then
  echo "[Hel] Creating virtualenv..."
  python3 -m venv "$VENV"
fi

"$VENV/bin/python" -m pip install --upgrade pip
"$VENV/bin/python" -m pip install -r "$BACKEND/requirements.txt"
(
  cd "$FRONTEND"
  npm install
)
(
  cd "$BACKEND"
  "$VENV/bin/python" main.py
) &
sleep 3
(
  cd "$FRONTEND"
  npm start
)
