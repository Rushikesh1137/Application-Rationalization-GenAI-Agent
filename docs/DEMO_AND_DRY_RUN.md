# Demo And Dry Run Guide

This repository includes synthetic demo data so the project can be shown publicly without client files.

## Generate Demo Input And Reference Output

```powershell
.\.venv\Scripts\python.exe scripts\create_demo_artifacts.py
```

This writes:

- `sample_data/app_inventory_demo.xlsx`
- `sample_output/ecr_results_demo.xlsx`

The reference output is deterministic and is meant to show the expected workbook structure and analysis style.

## Evaluate The Demo Output

```powershell
.\.venv\Scripts\python.exe scripts\evaluate_output.py sample_output\ecr_results_demo.xlsx --out sample_output\evaluation_report_demo.md
```

## Run The Full LLM Workflow On Demo Data

Copy `.env.example` to `.env`, set your API values, then set:

```env
INPUT_FILE=sample_data/app_inventory_demo.xlsx
INPUT_SHEET=Sheet1
OUTPUT_DIR=output
LOG_DIR=logs
```

Run:

```powershell
.\.venv\Scripts\python.exe -m src.orchestrator
```

This produces a live LLM-generated workbook in `output/`. Review the Summary sheet and compare the counts and rationale style with the reference output.
