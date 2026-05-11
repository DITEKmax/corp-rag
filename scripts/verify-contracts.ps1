$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
& python (Join-Path $Root "scripts/verify-contracts.py") @args
exit $LASTEXITCODE
