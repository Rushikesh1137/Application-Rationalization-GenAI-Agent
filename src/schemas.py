from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field


class Recommendation(str, Enum):
    retain = "Retain"
    eliminate = "Eliminate"
    consolidate = "Consolidate"


class ECRRow(BaseModel):
    app_name: str = Field(min_length=1)
    final_l3: str = Field(min_length=1)
    function: str = Field(min_length=1)
    recommendation: Recommendation
    rationale: str = Field(min_length=1)
    app_to_be_retained: str = Field(min_length=1)
    capability_loss_if_eliminated: str = ""


class RunResponse(BaseModel):
    status: str
    input_file: str
    output_file: str
    download_url: str


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


class EvaluationSummary(BaseModel):
    total_rows: int
    retain_count: int
    eliminate_count: int
    consolidate_count: int
    l3_count: int
    invalid_recommendation_count: int
    blank_function_count: int
    target_outside_cluster_count: int
    self_eliminate_count: int
    capability_loss_warning_count: int


class EvaluationResult(BaseModel):
    workbook: Path
    summary: EvaluationSummary
    warnings: list[str]
