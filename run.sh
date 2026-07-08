#!/usr/bin/env bash
# Enduraw Testing Tool - Mac / Linux launcher
# Usage:  ./run.sh
#
# Prerequisites:
#   pip3 install -r requirements.txt
#
# The MongoDB URI must be set via:
#   - Environment variable:  export MONGO_URI="mongodb+srv://..."
#   - Or a .env file in this directory (see .env.example)

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Load .env if present
if [ -f .env ]; then
    set -a
    source .env
    set +a
fi

if [ -x ".venv/bin/python" ]; then
    ".venv/bin/python" main.py "$@"
else
    python3 main.py "$@"
fi
