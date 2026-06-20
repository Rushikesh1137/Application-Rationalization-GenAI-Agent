"""Agent 2 node for ECR recommendations."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from src.prompts import ECR_RECOMMENDER_PROMPT
from src.state import ECRState

ALLOWED_RECOMMENDATIONS = {"Retain", "Eliminate", "Consolidate"}
CAPABILITY_LOSS_COLUMN = "Capability Loss if Eliminated"
OUTPUT_COLUMNS = [
    "App Name",
    "Final L3",
    "Function",
    "Recommendation",
    "Rationale",
    "App to be Retained",
    CAPABILITY_LOSS_COLUMN,
]
CAPABILITY_LOSS_ALIASES = {
    CAPABILITY_LOSS_COLUMN,
    "Capability Loss",
    "Capability loss",
    "capability_loss",
    "Capability Loss If Eliminated",
}
JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)
LEGACY_TERMS = {
    "legacy",
    "old",
    "deprecated",
    "predecessor",
    "older",
    "retired",
    "retirement",
    "sunset",
    "end of life",
    "end-of-life",
    "eol",
    "unsupported",
    "no longer supported",
    "will be retired",
    "scheduled for retirement",
    "transitioning to",
    "migrating to",
}
MODERN_TERMS = {
    "modern",
    "strategic",
    "successor",
    "replacement",
    "new",
    "cloud",
    "target platform",
    "future state",
    "modernization",
}
DUPLICATE_NAME_TERMS = {
    "dup",
    "duplicate",
    "v1",
    "v2",
    "classic",
    "original",
    "copy",
    "copied",
    "clone",
    "on-prem",
    "onprem",
    "cloud",
    "prod",
    "production",
    "dev",
    "test",
    "qa",
    "uat",
}
ANCHOR_CUES = {
    "enterprise",
    "global",
    "platform",
    "coe",
    "center",
    "central",
    "shared",
    "m365",
    "cloud",
    "azure",
    "s4hana",
    "s/4hana",
    "rise",
    "solventum",
}
LOCAL_INSTANCE_CUES = {
    "kci",
    "china",
    "state",
    "stateramp",
    "fedramp",
    "regional",
    "region",
    "site",
    "local",
    "onprem",
    "on-prem",
    "legacy",
    "old",
    "dev",
    "test",
    "qa",
    "uat",
    "us",
    "ous",
}
GENERIC_NAME_TOKENS = {
    "app",
    "application",
    "system",
    "platform",
    "service",
    "services",
    "tool",
    "tools",
    "the",
    "and",
    "for",
    "with",
    "of",
}

def configure_system_trust_store() -> None:
    """Use the OS certificate store for corporate TLS certificates when available."""
    try:
        import truststore
    except ImportError:
        return
    truststore.inject_into_ssl()


configure_system_trust_store()
load_dotenv(dotenv_path=Path.cwd() / ".env")


def _clean(value: object) -> str:
    return str(value or "").strip()


def _app_name(app: dict) -> str:
    return _clean(app.get("Name"))


def _normalize_name_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", _clean(name).casefold())


def _normalize_field_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", _clean(name).casefold())


def _field_value(raw: dict, field_name: str, aliases: set[str] | None = None) -> object:
    if field_name in raw:
        return raw.get(field_name)
    normalized_names = {_normalize_field_key(field_name)}
    if aliases:
        normalized_names.update(_normalize_field_key(alias) for alias in aliases)
    for key, value in raw.items():
        if _normalize_field_key(str(key)) in normalized_names:
            return value
    return ""


def _response_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                parts.append(str(item.get("text") or item.get("content") or ""))
            else:
                parts.append(str(item))
        return "".join(parts)
    return str(content)


def _extract_json_object(text: str) -> dict:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`").strip()
        if stripped.startswith("json"):
            stripped = stripped[4:].strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        match = JSON_OBJECT_RE.search(stripped)
        if not match:
            raise ValueError("ECR recommender response did not contain a JSON object.")
        return json.loads(match.group(0))


def _canonical_name(name: str, known_app_names: list[str]) -> str:
    cleaned_name = _clean(name)
    if cleaned_name in known_app_names:
        return cleaned_name

    by_key: dict[str, list[str]] = {}
    for app_name in known_app_names:
        by_key.setdefault(_normalize_name_key(app_name), []).append(app_name)

    matches = by_key.get(_normalize_name_key(cleaned_name), [])
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise ValueError(f"Ambiguous app name returned by ECR recommender: {name}")
    raise ValueError(f"Unknown app name returned by ECR recommender: {name}")


def _try_canonical_name(name: str, known_app_names: list[str]) -> tuple[str | None, str | None]:
    try:
        return _canonical_name(name, known_app_names), None
    except ValueError as error:
        return None, str(error)


def create_llm() -> ChatOpenAI:
    """Create the LangChain OpenAI-compatible chat model."""
    model = os.getenv("OPENAI_MODEL", "gpt-5.1")
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set.")

    return ChatOpenAI(
        model=model,
        api_key=api_key,
        base_url=base_url,
        temperature=0,
    )



def _hint_tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", _clean(value).casefold())
        if len(token) >= 3 and token not in GENERIC_NAME_TOKENS
    }


def _hint_anchor_score(app: dict) -> int:
    name = _app_name(app).casefold()
    description = _clean(app.get("Description")).casefold()
    text = f"{name} {description}"
    score = sum(3 for cue in ANCHOR_CUES if cue in text)
    score -= sum(2 for cue in LOCAL_INSTANCE_CUES if cue in name)
    score += min(len(description) // 120, 3)
    return score


def _portfolio_cleanup_hints(state: ECRState) -> str:
    """Build same-Function overlap hints for Agent 2."""
    function_tags = state.get("function_tags", {})
    by_function: dict[str, list[dict]] = {}
    for app in state["apps"]:
        app_name = _app_name(app)
        function = _clean(function_tags.get(app_name))
        if function:
            by_function.setdefault(function, []).append(app)

    lines: list[str] = []
    for function, apps in sorted(by_function.items(), key=lambda item: (-len(item[1]), item[0])):
        if len(apps) < 2:
            continue

        names = [_app_name(app) for app in apps]
        scored_apps = sorted(
            ((_hint_anchor_score(app), app) for app in apps),
            key=lambda item: item[0],
            reverse=True,
        )
        anchor_score, anchor = scored_apps[0]
        runner_up_score = scored_apps[1][0] if len(scored_apps) > 1 else anchor_score
        anchor_name = _app_name(anchor)
        signals: list[str] = []

        lowered_names = " ".join(names).casefold()
        if any(cue in lowered_names for cue in LOCAL_INSTANCE_CUES):
            signals.append("local, regional, compliance, tenant, or acquired-company naming")
        if any(cue in lowered_names for cue in ANCHOR_CUES):
            signals.append("possible enterprise or cloud retained anchor")
        if len(apps) >= 3:
            signals.append("three or more apps share the same Function")
        if len(apps) >= 2 and abs(anchor_score - runner_up_score) <= 1:
            signals.append("ambiguous retained anchor, use web evidence or explain why the chosen anchor is better")

        descriptions = [(_app_name(app), _clean(app.get("Description")).casefold()) for app in apps]
        for index, (left_name, left_description) in enumerate(descriptions):
            for right_name, right_description in descriptions[index + 1:]:
                if left_description and right_description:
                    if left_description == right_description:
                        signals.append(f"identical descriptions: {left_name} / {right_name}")
                    elif SequenceMatcher(None, left_description, right_description).ratio() >= 0.50:
                        signals.append(f"similar descriptions: {left_name} / {right_name}")
                shared_tokens = _hint_tokens(left_name) & _hint_tokens(right_name)
                if len(shared_tokens) >= 2:
                    joined = ", ".join(sorted(shared_tokens)[:3])
                    signals.append(f"similar product naming: {left_name} / {right_name} ({joined})")

        if not signals:
            signals.append("same Function peer group, review for standardization or overlap")

        lines.append(f"- Function: {function}")
        lines.append(f"  Apps: {'; '.join(names)}")
        lines.append(f"  Potential retained anchor to test: {anchor_name}")
        lines.append(f"  Cleanup signals: {'; '.join(dict.fromkeys(signals[:8]))}")

    if not lines:
        return ""
    return "\n".join(lines)


def build_ecr_user_message(state: ECRState, web_evidence: str = "") -> str:
    """Build the user message for Agent 2."""
    function_tags = state.get("function_tags", {})
    cleanup_hints = _portfolio_cleanup_hints(state)
    lines = [
        f"L3: {state['l3_name']}",
        "",
        "Validated Function tags:",
        json.dumps(function_tags, indent=2, ensure_ascii=False),
        "",
        "Apps in this cluster:",
        "",
    ]

    for app in state["apps"]:
        name = _app_name(app)
        vendor = _clean(app.get("Vendor")) or "(unknown)"
        description = _clean(app.get("Description")) or "(no description)"
        function = _clean(function_tags.get(name)) or "(missing)"
        l1 = _clean(app.get("L1"))
        l2 = _clean(app.get("L2"))
        l3 = _clean(app.get("L3"))

        lines.extend(
            [
                f"- App: {name}",
                f"  Function: {function}",
                f"  Vendor: {vendor}",
                f"  Description: {description}",
                f"  L1/L2/L3: {l1} / {l2} / {l3}",
                "",
            ]
        )

    if cleanup_hints:
        lines.extend(["Portfolio cleanup hints:", cleanup_hints, ""])

    if web_evidence:
        lines.extend([web_evidence, ""])

    lines.extend(
        [
            "Use the exact app names from the input.",
            "Use the validated Function label provided for each app.",
            "Return one ecr_decisions row per app, no omissions.",
            "Capability Loss if Eliminated may be blank. Fill it only for Eliminate rows with a real uncovered capability gap.",
            "If you find a function mismatch in an Eliminate or Consolidate group, report it in function_mismatch and do not change Function labels.",
        ]
    )
    return "\n".join(lines)


def build_ecr_repair_message(state: ECRState, app_name: str, issue: str, raw_decision: dict | None) -> str:
    """Build a targeted repair prompt for one malformed ECR row."""
    raw_text = json.dumps(raw_decision or {}, indent=2, ensure_ascii=False)
    lines = [
        build_ecr_user_message(state),
        "",
        "Repair request:",
        f"The decision row for this app was malformed: {issue}",
        f"App to repair: {app_name}",
        "Previous malformed row:",
        raw_text,
        "",
        "Return exactly one ecr_decisions row for the app named above.",
        "The row must include App Name, Final L3, Function, Recommendation, Rationale, App to be Retained, and Capability Loss if Eliminated. Capability Loss may be blank.",
        "Return only JSON with ecr_decisions as a one-row list and function_mismatch as null unless the repaired row has a real mismatch.",
    ]
    return "\n".join(lines)


def parse_ecr_response(text: str) -> tuple[list[dict], dict | None]:
    """Parse Agent 2 JSON response."""
    parsed = _extract_json_object(text)
    decisions = parsed.get("ecr_decisions")
    if not isinstance(decisions, list):
        raise ValueError("ECR recommender JSON must contain an ecr_decisions list.")

    mismatch = parsed.get("function_mismatch")
    if mismatch in ({}, [], "", "null"):
        mismatch = None
    if mismatch is not None and not isinstance(mismatch, dict):
        raise ValueError("function_mismatch must be null or an object.")

    return decisions, mismatch


def _description_by_app(state: ECRState) -> dict[str, str]:
    return {
        _app_name(app): re.sub(r"\s+", " ", _clean(app.get("Description")).casefold())
        for app in state["apps"]
    }


def _vendor_by_app(state: ECRState) -> dict[str, str]:
    return {_app_name(app): _clean(app.get("Vendor")).casefold() for app in state["apps"]}


def _normalize_variant_key(name: str) -> str:
    normalized = _clean(name).casefold()
    normalized = re.sub(r"\((dup|duplicate|copy|clone|cloud|on-prem|onprem|prod|production|dev|test|qa|uat|legacy|old|new|classic|original)\)", "", normalized)
    normalized = re.sub(r"\b(dup|duplicate|copy|clone|cloud|on[- ]?prem|prod|production|dev|test|qa|uat|legacy|old|new|classic|original|v\d+|\d+\.\d+)\b", "", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip(" -_()")


def _text_has_any(text: str, terms: set[str]) -> bool:
    lowered = _clean(text).casefold()
    return any(term in lowered for term in terms)


def _description_similarity(left: str, right: str) -> float:
    left = _clean(left)
    right = _clean(right)
    if not left or not right:
        return 0.0
    return SequenceMatcher(None, left, right).ratio()


def _same_function(app_name: str, retained_app: str, function_tags: dict[str, str]) -> bool:
    return bool(
        _clean(function_tags.get(app_name))
        and _clean(function_tags.get(app_name)) == _clean(function_tags.get(retained_app))
    )


def _has_duplicate_evidence(
    app_name: str,
    retained_app: str,
    descriptions: dict[str, str],
    vendors: dict[str, str],
    function_tags: dict[str, str],
) -> bool:
    if app_name == retained_app:
        return False

    app_key = _normalize_variant_key(app_name)
    retained_key = _normalize_variant_key(retained_app)
    app_name_text = app_name.casefold()
    retained_name_text = retained_app.casefold()

    if _text_has_any(app_name_text, DUPLICATE_NAME_TERMS) or _text_has_any(vendors.get(app_name, ""), {"duplicate", "dup", "copy", "copied", "clone"}):
        if app_key == retained_key or _same_function(app_name, retained_app, function_tags):
            return True
    if app_key and app_key == retained_key:
        return True

    app_description = descriptions.get(app_name, "")
    retained_description = descriptions.get(retained_app, "")
    if app_description and retained_description:
        if app_description == retained_description:
            return True
        if _description_similarity(app_description, retained_description) >= 0.60:
            return True
        cross_reference_text = f"{app_description} {retained_description}"
        if (
            app_name.casefold() in retained_description
            or retained_app.casefold() in app_description
        ) and _text_has_any(cross_reference_text, {"same product", "same app", "duplicate", "instance", "version"}):
            return True

    same_vendor = bool(vendors.get(app_name) and vendors.get(app_name) == vendors.get(retained_app))
    if same_vendor and _same_function(app_name, retained_app, function_tags):
        return True

    return False


def _has_replacement_evidence(
    app_name: str,
    retained_app: str,
    descriptions: dict[str, str],
    function_tags: dict[str, str],
) -> bool:
    if app_name == retained_app or not _same_function(app_name, retained_app, function_tags):
        return False

    app_description = descriptions.get(app_name, "")
    retained_description = descriptions.get(retained_app, "")
    app_text = f"{app_name} {app_description}".casefold()
    retained_text = f"{retained_app} {retained_description}".casefold()

    if retained_app.casefold() in app_description or app_name.casefold() in retained_description:
        return True
    if _text_has_any(app_text, LEGACY_TERMS):
        return True
    if _text_has_any(app_text, LEGACY_TERMS) and _text_has_any(retained_text, MODERN_TERMS):
        return True
    if _text_has_any(retained_text, MODERN_TERMS) and _text_has_any(app_text, {"legacy", "old", "deprecated"}):
        return True
    return False


def _safe_l3_filename(l3_name: str) -> str:
    return "".join(char if char.isalnum() else "_" for char in l3_name).strip("_") or "unknown_l3"


def _log_validation_issue(state: ECRState, app_name: str, issue: str, raw_decision: dict | None = None) -> None:
    log_dir = Path(os.getenv("LOG_DIR", "logs"))
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"malformed_ecr_{_safe_l3_filename(state['l3_name'])}.log"
    payload = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "l3": state["l3_name"],
        "app_name": app_name,
        "issue": issue,
        "raw_decision": raw_decision or {},
    }
    with log_path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _basic_validation_issue(raw: object, known_app_names: list[str]) -> tuple[str | None, str | None]:
    if not isinstance(raw, dict):
        return None, "Decision row must be a JSON object."

    raw_app_name = _clean(_field_value(raw, "App Name"))
    if not raw_app_name:
        return None, "app_name must be a non-empty string."
    app_name, name_error = _try_canonical_name(raw_app_name, known_app_names)
    if not app_name:
        return None, name_error or "app_name must match one of the input apps."

    recommendation = _clean(_field_value(raw, "Recommendation"))
    if recommendation not in ALLOWED_RECOMMENDATIONS:
        return app_name, "recommendation must be exactly Retain, Eliminate, or Consolidate."

    retained_app = _clean(_field_value(raw, "App to be Retained"))
    if not retained_app:
        return app_name, "app_to_retain must be a non-empty string."


    return app_name, None


def _collect_raw_decisions(
    state: ECRState,
    raw_decisions: list[dict],
) -> tuple[dict[str, dict], dict[str, str], list[dict[str, str]]]:
    known_app_names = [_app_name(app) for app in state["apps"]]
    raw_by_app: dict[str, dict] = {}
    issues_by_app: dict[str, str] = {}
    unassigned_issues: list[dict[str, str]] = []

    for raw in raw_decisions:
        app_name, issue = _basic_validation_issue(raw, known_app_names)
        if app_name is None:
            unassigned_issues.append({"app_name": "", "issue": issue or "Malformed row could not be assigned."})
            _log_validation_issue(state, "", issue or "Malformed row could not be assigned.", raw if isinstance(raw, dict) else None)
            continue
        if app_name in raw_by_app:
            issues_by_app[app_name] = "Duplicate decision row returned for this app."
            _log_validation_issue(state, app_name, issues_by_app[app_name], raw)
            continue
        raw_by_app[app_name] = raw
        if issue:
            issues_by_app[app_name] = issue
            _log_validation_issue(state, app_name, issue, raw)

    for app_name in known_app_names:
        if app_name not in raw_by_app:
            issues_by_app[app_name] = "Missing decision row for this app."
            _log_validation_issue(state, app_name, issues_by_app[app_name])

    return raw_by_app, issues_by_app, unassigned_issues


def _repair_raw_decision(
    state: ECRState,
    app_name: str,
    issue: str,
    raw_decision: dict | None,
    llm: ChatOpenAI | None,
) -> tuple[dict | None, str | None]:
    if llm is None:
        return None, issue
    try:
        response = llm.invoke(
            [
                SystemMessage(content=ECR_RECOMMENDER_PROMPT),
                HumanMessage(content=build_ecr_repair_message(state, app_name, issue, raw_decision)),
            ]
        )
        repaired_decisions, _ = parse_ecr_response(_response_text(response.content))
    except Exception as error:
        return None, f"Repair prompt failed: {type(error).__name__}: {error}"

    known_app_names = [_app_name(app) for app in state["apps"]]
    candidates: list[dict] = []
    repair_issues: list[str] = []
    for repaired in repaired_decisions:
        repaired_app, repaired_issue = _basic_validation_issue(repaired, known_app_names)
        if repaired_app == app_name and repaired_issue is None:
            candidates.append(repaired)
        elif repaired_app == app_name and repaired_issue:
            repair_issues.append(repaired_issue)

    if len(candidates) == 1:
        return candidates[0], None
    if repair_issues:
        return None, f"Repair row still malformed: {repair_issues[0]}"
    return None, "Repair prompt did not return one valid row for the requested app."


def _review_decision(state: ECRState, app_name: str, issue: str) -> tuple[dict, dict[str, str]]:
    function = _clean(state.get("function_tags", {}).get(app_name)) or "Needs Review"
    issue_text = issue.rstrip(".")
    row = {
        "App Name": app_name,
        "Final L3": state["l3_name"],
        "Function": function,
        "Recommendation": "Retain",
        "Rationale": f"Agent output was malformed after one repair attempt: {issue_text}. Needs human review.",
        "App to be Retained": app_name,
        CAPABILITY_LOSS_COLUMN: "",
        "_needs_human_review": "true",
        "_capability_loss_issue": issue,
    }
    issue_row = {
        "l3_name": state["l3_name"],
        "app_name": app_name,
        "issue": issue,
        "action": "needs_human_review",
    }
    return row, issue_row


def _normalize_one_decision(
    state: ECRState,
    raw: dict,
    app_name: str,
) -> tuple[dict, list[dict[str, str]]]:
    known_app_names = [_app_name(app) for app in state["apps"]]
    function_tags = state.get("function_tags", {})
    issues: list[dict[str, str]] = []

    recommendation = _clean(_field_value(raw, "Recommendation"))
    function = _clean(function_tags.get(app_name))
    if not function:
        raise ValueError(f"Missing validated Function tag for {app_name}.")

    retained_app_raw = _clean(_field_value(raw, "App to be Retained"))
    retained_app = app_name if recommendation == "Retain" else retained_app_raw
    retained_error: str | None = None
    if recommendation != "Retain":
        retained_app, retained_error = _try_canonical_name(retained_app_raw, known_app_names)

    capability_loss = _clean(_field_value(raw, CAPABILITY_LOSS_COLUMN, CAPABILITY_LOSS_ALIASES))
    if capability_loss.casefold() in {"not applicable", "n/a", "na", "none"}:
        capability_loss = ""

    rationale = _clean(_field_value(raw, "Rationale")).replace("\u2014", ",")
    if not rationale:
        rationale = "The recommendation needs human review because the agent did not provide a rationale."

    if recommendation == "Retain":
        retained_app = app_name
        capability_loss = ""
    elif retained_error:
        recommendation = "Retain"
        retained_app = app_name
        rationale = (
            f"The named retained app '{retained_app_raw}' was not found in this L3 cluster, "
            "so this app defaults to Retain."
        )
        capability_loss = ""
        issues.append(
            {
                "l3_name": state["l3_name"],
                "app_name": app_name,
                "issue": "Retained target was not found in the cluster.",
                "action": "auto_corrected_to_retain",
            }
        )
    elif recommendation == "Eliminate" and retained_app == app_name:
        recommendation = "Retain"
        retained_app = app_name
        rationale = "The app cannot be eliminated into itself, so this app defaults to Retain."
        capability_loss = ""
        issues.append(
            {
                "l3_name": state["l3_name"],
                "app_name": app_name,
                "issue": "Eliminate target was the same as the eliminated app.",
                "action": "auto_corrected_to_retain",
            }
        )
    elif recommendation == "Consolidate":
        # A self-targeted Consolidate row is valid for the retained anchor of a
        # consolidation group. Other rows point to this same retained app.
        retained_app = retained_app or app_name
        capability_loss = ""

    row = {
        "App Name": app_name,
        "Final L3": state["l3_name"],
        "Function": function,
        "Recommendation": recommendation,
        "Rationale": rationale,
        "App to be Retained": retained_app or app_name,
        CAPABILITY_LOSS_COLUMN: capability_loss,
    }
    if any(issue.get("action") == "needs_human_review" for issue in issues):
        row["_needs_human_review"] = "true"
    if issues:
        row["_capability_loss_issue"] = "; ".join(issue["issue"] for issue in issues)
    return row, issues

def normalize_decisions_with_issues(
    state: ECRState,
    raw_decisions: list[dict],
    llm: ChatOpenAI | None = None,
) -> tuple[list[dict], list[dict[str, str]]]:
    """Validate, repair, and normalize Agent 2 decisions."""
    known_app_names = [_app_name(app) for app in state["apps"]]
    raw_by_app, issues_by_app, unassigned_issues = _collect_raw_decisions(state, raw_decisions)
    capability_issues: list[dict[str, str]] = list(unassigned_issues)
    by_app: dict[str, dict] = {}

    for app_name in known_app_names:
        raw = raw_by_app.get(app_name)
        issue = issues_by_app.get(app_name)
        if issue:
            repaired, repair_issue = _repair_raw_decision(state, app_name, issue, raw, llm)
            if repaired is None:
                row, issue_row = _review_decision(state, app_name, repair_issue or issue)
                by_app[app_name] = row
                capability_issues.append(issue_row)
                continue
            raw = repaired

        if raw is None:
            row, issue_row = _review_decision(state, app_name, "Missing decision row for this app.")
            by_app[app_name] = row
            capability_issues.append(issue_row)
            continue

        row, row_issues = _normalize_one_decision(state, raw, app_name)
        by_app[app_name] = row
        capability_issues.extend(row_issues)

    return [by_app[app_name] for app_name in known_app_names], capability_issues


def normalize_decisions(state: ECRState, raw_decisions: list[dict]) -> list[dict]:
    """Validate and normalize Agent 2 decisions to output columns."""
    decisions, _ = normalize_decisions_with_issues(state, raw_decisions, llm=None)
    return decisions


def mark_consolidation_anchors(decisions: list[dict]) -> list[dict]:
    """Mark retained anchors as Consolidate when other rows consolidate to them."""
    consolidate_targets = {
        _clean(decision.get("App to be Retained"))
        for decision in decisions
        if decision.get("Recommendation") == "Consolidate"
        and _clean(decision.get("App Name")) != _clean(decision.get("App to be Retained"))
    }
    consolidate_targets.discard("")
    if not consolidate_targets:
        return decisions

    updated: list[dict] = []
    for decision in decisions:
        row = dict(decision)
        app_name = _clean(row.get("App Name"))
        if app_name in consolidate_targets and row.get("Recommendation") == "Retain":
            row["Recommendation"] = "Consolidate"
            row["App to be Retained"] = app_name
            row[CAPABILITY_LOSS_COLUMN] = ""
            row["Rationale"] = (
                "This is the surviving app for a consolidation group. Related entries roll into this app, "
                "so it is tagged Consolidate for group reporting while remaining the retained record."
            )
        updated.append(row)
    return updated

def detect_function_mismatch(
    decisions: list[dict],
    function_tags: dict[str, str],
) -> dict | None:
    """Find Function mismatches in Eliminate or Consolidate groups."""
    mismatches = []
    for decision in decisions:
        recommendation = decision["Recommendation"]
        if recommendation not in {"Eliminate", "Consolidate"}:
            continue

        app_name = decision["App Name"]
        retained_app = decision["App to be Retained"]
        app_function = _clean(function_tags.get(app_name))
        retained_function = _clean(function_tags.get(retained_app))
        if app_name == retained_app:
            continue
        if app_function and retained_function and app_function != retained_function:
            mismatches.append(
                {
                    "apps": [app_name, retained_app],
                    "recommendation": recommendation,
                    "functions": {
                        app_name: app_function,
                        retained_app: retained_function,
                    },
                    "reason": "Apps in the same ECR group must share the same Function label.",
                }
            )

    if not mismatches:
        return None
    return {"mismatches": mismatches}


def ecr_recommender_node(state: ECRState) -> dict:
    """Agent 2 node: produce ECR decisions and detect function mismatches."""
    llm = create_llm()
    web_evidence = ""
    response = llm.invoke(
        [
            SystemMessage(content=ECR_RECOMMENDER_PROMPT),
            HumanMessage(content=build_ecr_user_message(state, web_evidence=web_evidence)),
        ]
    )
    raw_decisions, model_mismatch = parse_ecr_response(_response_text(response.content))
    decisions, capability_issues = normalize_decisions_with_issues(state, raw_decisions, llm=llm)
    decisions = mark_consolidation_anchors(decisions)
    deterministic_mismatch = detect_function_mismatch(decisions, state.get("function_tags", {}))
    # The model may report mismatch details, but routing must use the deterministic
    # check so matching Function labels are never treated as a mismatch.
    function_mismatch = deterministic_mismatch
    _ = model_mismatch

    return {
        "ecr_decisions": decisions,
        "capability_loss": {
            decision["App Name"]: _clean(decision.get(CAPABILITY_LOSS_COLUMN))
            for decision in decisions
        },
        "capability_loss_issues": capability_issues,
        "function_mismatch": function_mismatch,
        "status": "tagging" if function_mismatch else "done",
    }










