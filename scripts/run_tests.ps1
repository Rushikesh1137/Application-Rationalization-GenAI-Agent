$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

.\.venv\Scripts\python.exe tests\test_hardening.py
