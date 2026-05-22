#!/usr/bin/env bash
# Run from the project root to create the Python venv and install deps.
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VENV="$PROJECT_DIR/.venv"

echo "Creating virtual environment at $VENV…"
python3.11 -m venv "$VENV"

echo "Installing dependencies…"
"$VENV/bin/pip" install --upgrade pip -q
"$VENV/bin/pip" install -r "$PROJECT_DIR/requirements.txt" -q

echo "Downloading spaCy model…"
"$VENV/bin/python" -m spacy download en_core_web_sm -q

echo ""
echo "Venv ready. Activate with: source $VENV/bin/activate"
