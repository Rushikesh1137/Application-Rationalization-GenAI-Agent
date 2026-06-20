param(
    [string]$L3
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

if (-not (Test-Path ".env")) {
    throw "Missing .env. Copy .env.example to .env and set your API key and input file."
}

if ($L3) {
    .\.venv\Scripts\python.exe -m src.orchestrator $L3
} else {
    .\.venv\Scripts\python.exe -m src.orchestrator
}
