# REST API

The project includes a small FastAPI wrapper so the ECR workflow can be used as a service.

## Start The API

```powershell
.\.venv\Scripts\uvicorn.exe src.api:app --reload
```

Open:

```text
http://127.0.0.1:8000/docs
```

## Endpoints

### `GET /health`

Returns service health and version.

### `POST /runs`

Upload an Excel inventory workbook and run ECR analysis.

Form fields:

- `file`: Excel workbook
- `input_sheet`: optional sheet name
- `limit_l3`: optional single L3 cluster for a smaller test

The response includes the generated output filename and a download URL.

### `GET /outputs/{filename}`

Downloads a generated Excel output from the configured output folder.

## Notes

The API uses the same LangGraph workflow and `.env` settings as the command-line orchestrator. It does not bypass validation or guardrails.
