# Setup And Run Guide

## 1. Create The Environment

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Or run:

```powershell
.\scripts\setup_venv.ps1
```

## 2. Configure `.env`

Minimum configuration:

```env
OPENAI_BASE_URL=https://your-openai-compatible-gateway/v1
OPENAI_API_KEY=replace-with-your-key
OPENAI_MODEL=gpt-5.1
VALIDATOR_MODEL=gpt-5.1

INPUT_FILE=input/your_inventory.xlsx
INPUT_SHEET=Sheet1
OUTPUT_DIR=output
LOG_DIR=logs
ENABLE_WEB_SEARCH=false
```

If using direct OpenAI instead of a gateway, set the model names and base URL according to your environment.

## 3. Add Input Workbook

Copy your workbook into `input/`. The file itself should not be committed to Git.

Required logical fields:

- Name
- Vendor
- Description
- L1
- L2
- L3

The loader supports common aliases such as `App Name`, `Application Name`, and `System Name` for Name.

## 4. Run The Full Portfolio

```powershell
.\.venv\Scripts\python.exe -m src.orchestrator
```

Or:

```powershell
.\scripts\run_ecr.ps1
```

## 5. Run One L3 Cluster

```powershell
.\.venv\Scripts\python.exe -m src.orchestrator "Data Integration"
```

Or:

```powershell
.\scripts\run_ecr.ps1 -L3 "Data Integration"
```

## 6. Review Results

Open the generated workbook in `output/`. Start with the `Summary` sheet, then inspect all `Eliminate` and `Consolidate` rows in `ECR Results`.

Also review `logs/calibration_summary_<timestamp>.log`. It warns if Eliminate count is below 5 or Consolidate count is below 10.

## 7. Resume From A Prior Output

The repository includes `scripts/resume_from_output.py` for recovery workflows. Use it when a run partially completed and you need to rebuild from existing output plus remaining clusters.
