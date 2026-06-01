$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Error "uv is required to run the demo corpus seed reset."
    exit 1
}

Push-Location $Root
try {
    & uv run --project ai-service python ai-service/eval/seed_corpus.py @args
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
