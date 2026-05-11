$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")

$python = $null
if (Get-Command uv -ErrorAction SilentlyContinue) {
    Push-Location (Join-Path $Root "ai-service")
    $python = (uv run python -c "import sys; print(sys.executable)")
    Pop-Location
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $python = "py"
} else {
    Write-Error "No Python found: need uv (preferred) or py launcher"
    exit 1
}

& $python (Join-Path $Root "scripts/verify-contracts.py") @args
exit $LASTEXITCODE
