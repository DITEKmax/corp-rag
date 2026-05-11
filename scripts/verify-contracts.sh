#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)

if command -v uv >/dev/null 2>&1; then
    cd "$ROOT/ai-service"
    exec uv run python "$ROOT/scripts/verify-contracts.py" "$@"
elif command -v python3 >/dev/null 2>&1; then
    exec python3 "$ROOT/scripts/verify-contracts.py" "$@"
elif command -v python >/dev/null 2>&1; then
    exec python "$ROOT/scripts/verify-contracts.py" "$@"
else
    echo "No Python found: need uv (preferred), python3, or python" >&2
    exit 1
fi
