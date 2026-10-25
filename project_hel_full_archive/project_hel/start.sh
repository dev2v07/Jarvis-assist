#!/usr/bin/env bash
set -e

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"

cd "$ROOT_DIR/backend"
if [ ! -d venv ]; then
  python3 -m venv venv
fi
source venv/bin/activate
pip install -r requirements.txt
python main.py &
BACK_PID=$!

cd "$ROOT_DIR/frontend"
npm install
npm start

kill $BACK_PID || true
