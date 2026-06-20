from collections import Counter
from datetime import datetime
from pathlib import Path
import os
import sys
import traceback

import pandas as pd
from dotenv import load_dotenv

from src.graph import build_graph
from src.output_writer import rows_for_states, write_excel
from src.state import ECRState


REQUIRED_COLUMNS = ["Name", "Vendor", "Description", "L1", "L2", "L3"]
COLUMN_ALIASES = {
    "Name": ["Name", "App Name", "App Label", "Application Name", "Apps", "application name", "System Name"],
    "Vendor": ["Vendor", "Vendor Name"],
    "Description": ["Description", "App Description", "Application Description"],
    "L1": ["L1"],
    "L2": ["L2"],
    "L3": ["L3"],
}
DEFAULT_INPUT_FILE = "input/app_inventory.xlsx"
DEFAULT_OUTPUT_DIR = "output"
DEFAULT_LOG_DIR = "logs"
DEFAULT_INPUT_SHEET = None
DEFAULT_MAX_RETRIES = 5
CALIBRATION_MIN_ELIMINATE = 5
CALIBRATION_MIN_CONSOLIDATE = 10


def _clean_column_name(value: object) -> str:
    return str(value or "").strip()


def normalize_inventory_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize supported workbook column names to the internal schema."""
    renamed = df.copy()
    renamed.columns = [_clean_column_name(column) for column in renamed.columns]
    renamed = renamed.loc[:, [bool(column) for column in renamed.columns]]
    source_columns = {_clean_column_name(column).casefold(): column for column in renamed.columns}
    rename_map = {}

    for canonical, aliases in COLUMN_ALIASES.items():
        if canonical in renamed.columns:
            continue
        for alias in aliases:
            source_column = source_columns.get(_clean_column_name(alias).casefold())
            if source_column:
                rename_map[source_column] = canonical
                break

    if rename_map:
        renamed = renamed.rename(columns=rename_map)

    if "Vendor" not in renamed.columns:
        renamed["Vendor"] = ""

    return renamed


def validate_inventory(df: pd.DataFrame) -> None:
    """Validate required workbook columns after normalization."""
    missing = [column for column in REQUIRED_COLUMNS if column not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns after normalization: {missing}")


def _candidate_inventory_frames(input_file: Path, sheet_name: str | int | None) -> list[pd.DataFrame]:
    """Return possible workbook frames, including shifted header rows."""
    frames: list[pd.DataFrame] = []
    frames.append(pd.read_excel(input_file, sheet_name=sheet_name or 0).fillna(""))

    raw = pd.read_excel(input_file, sheet_name=sheet_name or 0, header=None).fillna("")
    for header_row in range(min(10, len(raw))):
        candidate = raw.iloc[header_row + 1 :].copy()
        candidate.columns = [_clean_column_name(value) for value in raw.iloc[header_row].tolist()]
        frames.append(candidate.fillna(""))
    return frames


def load_inventory(input_file: Path, sheet_name: str | int | None = DEFAULT_INPUT_SHEET) -> pd.DataFrame:
    """Load and normalize the requested input workbook sheet."""
    if not input_file.exists():
        raise FileNotFoundError(f"Input file not found: {input_file}")

    last_error: Exception | None = None
    for candidate in _candidate_inventory_frames(input_file, sheet_name):
        try:
            df = normalize_inventory_columns(candidate)
            validate_inventory(df)
        except Exception as error:
            last_error = error
            continue

        for column in REQUIRED_COLUMNS:
            df[column] = df[column].astype(str).str.strip()
        df = df[df["Name"].astype(bool) & df["L3"].astype(bool)].copy()
        if not df.empty:
            return df

    if last_error:
        raise last_error
    raise ValueError("No usable inventory rows found in workbook.")


def select_l3_groups(
    df: pd.DataFrame,
    limit_l3: str | None = None,
) -> list[tuple[str, pd.DataFrame]]:
    """Return L3 groups, optionally limited to one requested L3."""
    if limit_l3:
        requested_l3 = limit_l3.strip()
        mask = df["L3"].str.casefold() == requested_l3.casefold()
        filtered = df[mask]
        if filtered.empty:
            available = sorted(value for value in df["L3"].unique() if value)
            raise ValueError(
                f"L3 '{limit_l3}' not found. Available L3s: {', '.join(available)}"
            )
        return [(str(filtered["L3"].iloc[0]), filtered)]

    return [(str(l3_name), group) for l3_name, group in df.groupby("L3", sort=False)]


def initial_state_for_l3(l3_name: str, group: pd.DataFrame) -> ECRState:
    """Build the initial graph state for one L3 cluster."""
    return {
        "l3_name": l3_name,
        "apps": group.to_dict(orient="records"),
        "max_retries": DEFAULT_MAX_RETRIES,
        "function_tags": {},
        "failed_apps": [],
        "validator_feedback": {},
        "ecr_decisions": [],
        "capability_loss": {},
        "function_mismatch": None,
        "retry_count": 0,
        "status": "tagging",
    }


def error_state_for_l3(l3_name: str, group: pd.DataFrame, error: Exception) -> ECRState:
    """Build an error state so one failed L3 does not stop the whole run."""
    return {
        "l3_name": l3_name,
        "apps": group.to_dict(orient="records"),
        "max_retries": DEFAULT_MAX_RETRIES,
        "function_tags": {},
        "failed_apps": [],
        "validator_feedback": {},
        "ecr_decisions": [],
        "capability_loss": {},
        "function_mismatch": None,
        "retry_count": 0,
        "status": "error",
        "error_type": type(error).__name__,
        "error_message": str(error),
    }


def write_error_log(log_dir: Path, l3_name: str, error: Exception) -> Path:
    """Write a per-cluster error log for debugging larger runs."""
    safe_l3 = "".join(char if char.isalnum() else "_" for char in l3_name).strip("_") or "unknown_l3"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = log_dir / f"error_{safe_l3}_{timestamp}.log"
    log_path.write_text(
        "".join(traceback.format_exception(type(error), error, error.__traceback__)),
        encoding="utf-8",
    )
    return log_path





def _safe_output_stem(input_file: Path) -> str:
    """Create a readable output stem from the input workbook name."""
    stem = "".join(char if char.isalnum() else "_" for char in input_file.stem).strip("_")
    return stem or "ecr_results"


def write_calibration_summary(log_dir: Path, timestamp: str, final_states: list[ECRState]) -> Path:
    """Write and print final ECR calibration counts for the full run."""
    rows = rows_for_states(final_states)
    counts = Counter(row["Recommendation"] for row in rows)
    eliminate_count = counts.get("Eliminate", 0)
    consolidate_count = counts.get("Consolidate", 0)
    warnings: list[str] = []
    if eliminate_count < CALIBRATION_MIN_ELIMINATE:
        warnings.append(
            f"Eliminate count is below {CALIBRATION_MIN_ELIMINATE}; Agent 2 may still be too conservative."
        )
    if consolidate_count < CALIBRATION_MIN_CONSOLIDATE:
        warnings.append(
            f"Consolidate count is below {CALIBRATION_MIN_CONSOLIDATE}; Agent 2 may still be too conservative."
        )

    lines = [
        "Calibration summary",
        f"Total rows: {len(rows)}",
        f"Eliminate count: {eliminate_count}",
        f"Consolidate count: {consolidate_count}",
    ]
    if warnings:
        lines.append("Warnings:")
        lines.extend(f"- {warning}" for warning in warnings)
    else:
        lines.append("Warnings: none")

    log_path = log_dir / f"calibration_summary_{timestamp}.log"
    log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    for line in lines:
        print(line)
    print(f"Calibration log: {log_path}")
    return log_path

def run_inventory(
    input_file: Path,
    output_dir: Path,
    log_dir: Path,
    input_sheet: str | int | None = DEFAULT_INPUT_SHEET,
    limit_l3: str | None = None,
) -> Path:
    """Run the full ECR workflow for an input workbook."""
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not set in .env.")

    input_file = Path(input_file)
    output_dir = Path(output_dir)
    log_dir = Path(log_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)

    inventory = load_inventory(input_file, input_sheet)
    groups = select_l3_groups(inventory, limit_l3)
    graph = build_graph()

    print(f"Input: {input_file}")
    print(f"Input sheet: {input_sheet or 0}")
    print(f"Inventory rows: {len(inventory)}")
    print(f"Processing {len(groups)} L3 cluster(s).")
    final_states: list[ECRState] = []
    for l3_name, group in groups:
        print(f"L3: {l3_name} ({len(group)} apps)")
        state = initial_state_for_l3(l3_name, group)
        try:
            final_state = graph.invoke(
                state,
                config={"recursion_limit": state["max_retries"] * 6 + 10},
            )
        except Exception as error:
            log_path = write_error_log(log_dir, l3_name, error)
            final_state = error_state_for_l3(l3_name, group, error)
            print(f"  Status: error; Log: {log_path}")
        else:
            print(
                f"  Status: {final_state['status']}; "
                f"Retries: {final_state['retry_count']}; "
                f"Rows: {len(final_state.get('ecr_decisions', []))}"
            )
        final_states.append(final_state)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = output_dir / f"{_safe_output_stem(input_file)}_ecr_results_{timestamp}.xlsx"
    write_excel(final_states, output_path)
    write_calibration_summary(log_dir, timestamp, final_states)
    print(f"Done. Excel results in: {output_path}")
    return output_path


def main(limit_l3: str | None = None) -> Path:
    """Load env configuration and run ECR from the command line."""
    load_dotenv(dotenv_path=Path.cwd() / ".env")

    input_file = Path(os.getenv("INPUT_FILE", DEFAULT_INPUT_FILE))
    output_dir = Path(os.getenv("OUTPUT_DIR", DEFAULT_OUTPUT_DIR))
    log_dir = Path(os.getenv("LOG_DIR", DEFAULT_LOG_DIR))
    input_sheet = os.getenv("INPUT_SHEET") or DEFAULT_INPUT_SHEET

    return run_inventory(
        input_file=input_file,
        output_dir=output_dir,
        log_dir=log_dir,
        input_sheet=input_sheet,
        limit_l3=limit_l3,
    )


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    try:
        main(limit_l3=arg)
    except Exception as error:
        sys.exit(str(error))









