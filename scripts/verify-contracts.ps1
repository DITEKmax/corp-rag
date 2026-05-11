$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
& uv run --project (Join-Path $Root "ai-service") python (Join-Path $Root "scripts/verify-contracts.py") @args
exit $LASTEXITCODE
