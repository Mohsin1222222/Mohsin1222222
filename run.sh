#!/usr/bin/env bash
# Convenience launcher for SubSync Studio.
set -euo pipefail

cd "$(dirname "$0")"

PYTHON=${PYTHON:-python3}
PORT=${PORT:-8000}
HOST=${HOST:-0.0.0.0}

if [ ! -d ".venv" ]; then
  echo "→ creating virtualenv (.venv)"
  "$PYTHON" -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

echo "→ installing dependencies"
pip install --quiet --upgrade pip
pip install --quiet -r backend/requirements.txt

# Check for ffmpeg
if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "⚠️  ffmpeg not found. Install it: apt-get install ffmpeg / brew install ffmpeg"
fi

echo "→ starting server on http://${HOST}:${PORT}"
exec uvicorn backend.main:app --host "$HOST" --port "$PORT" --reload
