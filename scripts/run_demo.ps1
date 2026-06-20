$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

.\.venv\Scripts\python.exe scripts\create_demo_artifacts.py
.\.venv\Scripts\python.exe scripts\evaluate_output.py sample_output\ecr_results_demo.xlsx --out sample_output\evaluation_report_demo.md --json sample_output\evaluation_report_demo.json

Write-Host "Demo input: sample_data\app_inventory_demo.xlsx"
Write-Host "Demo output: sample_output\ecr_results_demo.xlsx"
Write-Host "Evaluation report: sample_output\evaluation_report_demo.md"
