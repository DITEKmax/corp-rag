$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$AiService = Join-Path $Root "ai-service"

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Error "uv is required to run the demo corpus seed reset."
    exit 1
}

Push-Location $AiService
try {
    & uv run python eval/seed_corpus.py @args
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
