from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.output_writer import CAPABILITY_LOSS_COLUMN, OUTPUT_COLUMNS
from src.schemas import EvaluationResult, EvaluationSummary


ALLOWED_RECOMMENDATIONS = {"Retain", "Eliminate", "Consolidate"}


def _clean(value: object) -> str:
    return str(value or "").strip()


def evaluate_workbook(workbook: Path) -> EvaluationResult:
    if not workbook.exists():
        raise FileNotFoundError(f"Workbook not found: {workbook}")

    df = pd.read_excel(workbook, sheet_name="ECR Results").fillna("")
    missing_columns = [column for column in OUTPUT_COLUMNS if column not in df.columns]
    if missing_columns:
        raise ValueError(f"Missing output columns: {missing_columns}")

    rows = df.to_dict(orient="records")
    recommendation_counts = Counter(_clean(row["Recommendation"]) for row in rows)
    apps_by_l3: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        apps_by_l3[_clean(row["Final L3"])].add(_clean(row["App Name"]).casefold())

    invalid_recommendations = [
        row for row in rows if _clean(row["Recommendation"]) not in ALLOWED_RECOMMENDATIONS
    ]
    blank_functions = [row for row in rows if not _clean(row["Function"])]
    target_outside_cluster = []
    self_eliminates = []
    capability_warnings = []

    for row in rows:
        recommendation = _clean(row["Recommendation"])
        app_name = _clean(row["App Name"])
        target = _clean(row["App to be Retained"])
        l3_name = _clean(row["Final L3"])
        if recommendation in {"Eliminate", "Consolidate"} and target.casefold() not in apps_by_l3[l3_name]:
            target_outside_cluster.append(row)
        if recommendation == "Eliminate" and target.casefold() == app_name.casefold():
            self_eliminates.append(row)
        if recommendation == "Eliminate" and _clean(row.get(CAPABILITY_LOSS_COLUMN)):
            capability_warnings.append(row)

    warnings: list[str] = []
    if recommendation_counts.get("Eliminate", 0) < 5:
        warnings.append("Eliminate count is below the calibration floor of 5.")
    if recommendation_counts.get("Consolidate", 0) < 10:
        warnings.append("Consolidate count is below the calibration floor of 10.")
    if target_outside_cluster:
        warnings.append("Some Eliminate or Consolidate targets are outside their L3 cluster.")
    if self_eliminates:
        warnings.append("Some Eliminate rows retain themselves, which should be reviewed.")

    summary = EvaluationSummary(
        total_rows=len(rows),
        retain_count=recommendation_counts.get("Retain", 0),
        eliminate_count=recommendation_counts.get("Eliminate", 0),
        consolidate_count=recommendation_counts.get("Consolidate", 0),
        l3_count=len(apps_by_l3),
        invalid_recommendation_count=len(invalid_recommendations),
        blank_function_count=len(blank_functions),
        target_outside_cluster_count=len(target_outside_cluster),
        self_eliminate_count=len(self_eliminates),
        capability_loss_warning_count=len(capability_warnings),
    )
    return EvaluationResult(workbook=workbook, summary=summary, warnings=warnings)


def write_markdown_report(result: EvaluationResult, output_path: Path) -> None:
    summary = result.summary
    lines = [
        "# ECR Evaluation Report",
        "",
        f"Workbook: `{result.workbook}`",
        "",
        "## Summary Metrics",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| Total rows | {summary.total_rows} |",
        f"| L3 clusters | {summary.l3_count} |",
        f"| Retain | {summary.retain_count} |",
        f"| Eliminate | {summary.eliminate_count} |",
        f"| Consolidate | {summary.consolidate_count} |",
        f"| Invalid recommendations | {summary.invalid_recommendation_count} |",
        f"| Blank function tags | {summary.blank_function_count} |",
        f"| Targets outside cluster | {summary.target_outside_cluster_count} |",
        f"| Self-eliminate rows | {summary.self_eliminate_count} |",
        f"| Capability loss warnings | {summary.capability_loss_warning_count} |",
        "",
        "## Calibration Warnings",
        "",
    ]
    if result.warnings:
        lines.extend(f"- {warning}" for warning in result.warnings)
    else:
        lines.append("- None")
    lines.append("")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate an ECR Excel output workbook.")
    parser.add_argument("workbook", type=Path)
    parser.add_argument("--out", type=Path, default=Path("sample_output/evaluation_report.md"))
    parser.add_argument("--json", type=Path, default=None)
    args = parser.parse_args()

    result = evaluate_workbook(args.workbook)
    write_markdown_report(result, args.out)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(result.model_dump_json(indent=2), encoding="utf-8")

    print(result.summary.model_dump())
    if result.warnings:
        print("Warnings:")
        for warning in result.warnings:
            print(f"- {warning}")
    print(f"Wrote evaluation report: {args.out}")


if __name__ == "__main__":
    main()
