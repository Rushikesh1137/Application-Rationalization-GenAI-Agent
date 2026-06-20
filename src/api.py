from __future__ import annotations

import os
import shutil
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from src.orchestrator import DEFAULT_LOG_DIR, DEFAULT_OUTPUT_DIR, run_inventory
from src.schemas import HealthResponse, RunResponse


APP_VERSION = "0.2.0"

app = FastAPI(
    title="Application Rationalization ECR Agent",
    version=APP_VERSION,
    description="LangGraph-based GenAI workflow for application portfolio ECR analysis.",
)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", service="ecr-agent", version=APP_VERSION)


@app.post("/runs", response_model=RunResponse)
async def run_ecr(
    file: UploadFile = File(...),
    input_sheet: str | None = Form(None),
    limit_l3: str | None = Form(None),
) -> RunResponse:
    """Upload an inventory workbook, run ECR analysis, and return the output path."""
    load_dotenv(dotenv_path=Path.cwd() / ".env")
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY is not configured.")

    if not file.filename or not file.filename.lower().endswith((".xlsx", ".xlsm", ".xls")):
        raise HTTPException(status_code=400, detail="Upload an Excel workbook.")

    upload_dir = Path(os.getenv("API_UPLOAD_DIR", "input/uploads"))
    output_dir = Path(os.getenv("OUTPUT_DIR", DEFAULT_OUTPUT_DIR))
    log_dir = Path(os.getenv("LOG_DIR", DEFAULT_LOG_DIR))
    upload_dir.mkdir(parents=True, exist_ok=True)

    safe_name = "".join(char if char.isalnum() or char in ".-_" else "_" for char in file.filename)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    input_path = upload_dir / f"{timestamp}_{safe_name}"

    with input_path.open("wb") as target:
        shutil.copyfileobj(file.file, target)

    try:
        output_path = run_inventory(
            input_file=input_path,
            output_dir=output_dir,
            log_dir=log_dir,
            input_sheet=input_sheet or None,
            limit_l3=limit_l3 or None,
        )
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error)) from error

    return RunResponse(
        status="completed",
        input_file=str(input_path),
        output_file=str(output_path),
        download_url=f"/outputs/{output_path.name}",
    )


@app.get("/outputs/{filename}")
def download_output(filename: str) -> FileResponse:
    """Download a generated Excel output by filename."""
    output_dir = Path(os.getenv("OUTPUT_DIR", DEFAULT_OUTPUT_DIR))
    output_path = output_dir / filename
    if not output_path.exists() or output_path.parent.resolve() != output_dir.resolve():
        raise HTTPException(status_code=404, detail="Output file not found.")
    return FileResponse(
        output_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=output_path.name,
    )
