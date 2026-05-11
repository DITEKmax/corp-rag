#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)

exec uv run --project "$ROOT/ai-service" python "$ROOT/scripts/verify-contracts.py" "$@"
