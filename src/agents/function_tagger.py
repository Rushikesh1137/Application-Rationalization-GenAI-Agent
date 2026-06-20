"""Agent 1 node for Function tagging."""

from __future__ import annotations

import json
import os
import re
from collections import Counter
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from src.prompts import FUNCTION_TAGGER_PROMPT
from src.state import ECRState

JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


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


def canonicalize_returned_tags(
    returned_tags: dict[str, str],
    known_app_names: list[str],
) -> dict[str, str]:
    """Map minor punctuation/case variants back to exact input app names."""
    by_key: dict[str, list[str]] = {}
    for app_name in known_app_names:
        by_key.setdefault(_normalize_name_key(app_name), []).append(app_name)

    canonical_tags: dict[str, str] = {}
    unknown_names: list[str] = []
    ambiguous_names: list[str] = []

    for returned_name, function_label in returned_tags.items():
        if returned_name in known_app_names:
            canonical_tags[returned_name] = function_label
            continue

        matches = by_key.get(_normalize_name_key(returned_name), [])
        if len(matches) == 1:
            canonical_tags[matches[0]] = function_label
        elif len(matches) > 1:
            ambiguous_names.append(returned_name)
        else:
            unknown_names.append(returned_name)

    if unknown_names:
        raise ValueError(f"Function tagger returned unknown app names: {sorted(unknown_names)}")
    if ambiguous_names:
        raise ValueError(f"Function tagger returned ambiguous app names: {sorted(ambiguous_names)}")

    return canonical_tags


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
            raise ValueError("Function tagger response did not contain a JSON object.")
        return json.loads(match.group(0))


def _collect_strings(value: Any) -> set[str]:
    if isinstance(value, str):
        return {_clean(value)} if _clean(value) else set()
    if isinstance(value, dict):
        collected: set[str] = set()
        for child in value.values():
            collected.update(_collect_strings(child))
        return collected
    if isinstance(value, list):
        collected: set[str] = set()
        for child in value:
            collected.update(_collect_strings(child))
        return collected
    return set()


def _target_app_names(state: ECRState) -> list[str]:
    app_names = [_app_name(app) for app in state["apps"]]
    known_names = set(app_names)

    failed_apps = [name for name in state.get("failed_apps", []) if name in known_names]
    if failed_apps:
        return failed_apps

    mismatch = state.get("function_mismatch")
    if mismatch:
        mismatch_names = _collect_strings(mismatch) & known_names
        if mismatch_names:
            return [name for name in app_names if name in mismatch_names]

    return app_names


def build_function_tagger_user_message(state: ECRState) -> str:
    """Build the user message for Agent 1."""
    target_names = set(_target_app_names(state))
    existing_tags = state.get("function_tags", {})
    validator_feedback = state.get("validator_feedback", {})
    function_mismatch = state.get("function_mismatch")

    lines = [
        f"L3: {state['l3_name']}",
        "",
        "Apps in this cluster:",
        "",
    ]

    for app in state["apps"]:
        name = _app_name(app)
        vendor = _clean(app.get("Vendor")) or "(unknown)"
        description = _clean(app.get("Description")) or "(no description)"
        l1 = _clean(app.get("L1"))
        l2 = _clean(app.get("L2"))
        l3 = _clean(app.get("L3"))
        existing_tag = _clean(existing_tags.get(name)) or "(none)"
        action = "RETAG" if name in target_names else "KEEP"

        lines.extend(
            [
                f"- App: {name}",
                f"  Action: {action}",
                f"  Current Function: {existing_tag}",
                f"  Vendor: {vendor}",
                f"  Description: {description}",
                f"  L1/L2/L3: {l1} / {l2} / {l3}",
            ]
        )
        if name in validator_feedback:
            lines.append(f"  Validator feedback: {validator_feedback[name]}")
        lines.append("")

    if function_mismatch:
        lines.extend(
            [
                "Function mismatch feedback from Agent 2:",
                json.dumps(function_mismatch, indent=2, ensure_ascii=False),
                "",
            ]
        )

    lines.extend(
        [
            "Return Function labels only for apps marked RETAG.",
            "Preserve apps marked KEEP by omitting them from the returned function_tags object.",
            "If this is the first pass, all apps are marked RETAG.",
        ]
    )
    return "\n".join(lines)



def _fallback_function_label(
    app_name: str,
    state: ECRState,
    returned_tags: dict[str, str],
) -> str:
    """Create a safe deterministic Function label when Agent 1 omits an app."""
    existing_tag = _clean(state.get("function_tags", {}).get(app_name))
    if existing_tag:
        return existing_tag

    peer_labels = [_clean(label) for label in returned_tags.values() if _clean(label)]
    if peer_labels:
        return Counter(peer_labels).most_common(1)[0][0]

    stop_words = {"and", "or", "of", "the", "to", "for", "with"}
    l3_terms = [
        token
        for token in re.findall(r"[A-Za-z0-9]+", _clean(state.get("l3_name", "")))
        if token.casefold() not in stop_words
    ][:3]
    if not l3_terms:
        l3_terms = ["Application", "Portfolio"]

    label = " ".join(l3_terms + ["Management"])
    if label.casefold() == _clean(state.get("l3_name", "")).casefold():
        label = f"{label} Support"
    return label


def _repair_missing_function_tags(
    state: ECRState,
    missing_targets: set[str],
    llm: ChatOpenAI,
) -> dict[str, str]:
    """Ask Agent 1 once more for omitted apps only."""
    if not missing_targets:
        return {}

    known_app_names = [_app_name(app) for app in state["apps"]]
    repair_state = dict(state)
    repair_state["failed_apps"] = [name for name in known_app_names if name in missing_targets]
    repair_state["validator_feedback"] = {
        name: "The previous response omitted this app. Return a Function label for this exact app name."
        for name in missing_targets
    }

    response = llm.invoke(
        [
            SystemMessage(content=FUNCTION_TAGGER_PROMPT),
            HumanMessage(content=build_function_tagger_user_message(repair_state)),
        ]
    )
    repair_tags = parse_function_tagger_response(_response_text(response.content))
    repair_tags = canonicalize_returned_tags(repair_tags, known_app_names)
    return {name: label for name, label in repair_tags.items() if name in missing_targets}

def parse_function_tagger_response(text: str) -> dict[str, str]:
    """Parse Agent 1 JSON response into app_name -> Function label."""
    parsed = _extract_json_object(text)
    tags = parsed.get("function_tags")
    if not isinstance(tags, dict):
        raise ValueError("Function tagger JSON must contain a function_tags object.")

    cleaned_tags: dict[str, str] = {}
    for app_name, function_label in tags.items():
        cleaned_name = _clean(app_name)
        cleaned_label = _clean(function_label)
        if cleaned_name and cleaned_label:
            cleaned_tags[cleaned_name] = cleaned_label
    return cleaned_tags


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


def function_tagger_node(state: ECRState) -> dict:
    """Agent 1 node: assign or repair Function tags for an L3 cluster."""
    target_names = set(_target_app_names(state))
    llm = create_llm()
    response = llm.invoke(
        [
            SystemMessage(content=FUNCTION_TAGGER_PROMPT),
            HumanMessage(content=build_function_tagger_user_message(state)),
        ]
    )
    returned_tags = parse_function_tagger_response(_response_text(response.content))
    known_app_names = [_app_name(app) for app in state["apps"]]
    returned_tags = canonicalize_returned_tags(returned_tags, known_app_names)

    unexpected_names = set(returned_tags) - target_names
    if unexpected_names:
        raise ValueError(
            "Function tagger returned tags for apps that were not marked RETAG: "
            f"{sorted(unexpected_names)}"
        )

    missing_targets = target_names - set(returned_tags)
    if missing_targets:
        repair_tags = _repair_missing_function_tags(state, missing_targets, llm)
        returned_tags.update(repair_tags)
        missing_targets = target_names - set(returned_tags)

    if missing_targets:
        for app_name in sorted(missing_targets):
            returned_tags[app_name] = _fallback_function_label(app_name, state, returned_tags)

    merged_tags = dict(state.get("function_tags", {}))
    merged_tags.update(returned_tags)

    return {
        "function_tags": merged_tags,
        "failed_apps": [],
        "validator_feedback": {},
        "function_mismatch": None,
        "status": "validating",
    }

