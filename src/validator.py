"""Deterministic Function tag validator.

This module intentionally implements only the pure-Python checks first.
The LLM-backed semantic validator comes later in the build order.
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Iterable

from src.state import ECRState


TOO_BROAD_LABELS = {
    "app",
    "application",
    "applications",
    "general",
    "misc",
    "miscellaneous",
    "other",
    "platform",
    "service",
    "services",
    "software",
    "system",
    "systems",
    "technology",
    "tool",
    "tools",
}

GENERIC_VENDOR_TOKENS = {
    "app",
    "apps",
    "corp",
    "corporation",
    "inc",
    "llc",
    "ltd",
    "software",
    "system",
    "systems",
    "technologies",
    "technology",
    "vendor",
}

ENVIRONMENT_TERMS = {
    "cloud",
    "dev",
    "development",
    "instance",
    "on-prem",
    "onprem",
    "prod",
    "production",
    "qa",
    "test",
    "uat",
    "v1",
    "v2",
    "version",
}

PLATFORM_TERMS = {"android", "ios", "web"}
TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9&/+.-]*")


def _clean(value: object) -> str:
    return str(value or "").strip()


def _tokens(value: str) -> list[str]:
    return [token.lower() for token in TOKEN_RE.findall(value)]


def _meaningful_vendor_tokens(vendor: str) -> set[str]:
    return {
        token
        for token in _tokens(vendor)
        if len(token) >= 3 and token not in GENERIC_VENDOR_TOKENS
    }


def _normalize_description(description: str) -> str:
    return re.sub(r"\s+", " ", _clean(description).casefold())


def _normalize_duplicate_name(name: str) -> str:
    normalized = _clean(name).casefold()
    normalized = normalized.replace("(dup)", "")
    normalized = normalized.replace("duplicate entry", "")
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip(" -_()")


def _normalize_env_variant_name(name: str) -> str:
    normalized = _clean(name).casefold()
    normalized = re.sub(r"\((cloud|on-prem|onprem|prod|production|dev|test|qa|uat)\)", "", normalized)
    normalized = re.sub(r"\bv\d+\b", "", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip(" -_()")


def _looks_like_platform_variant(name: str) -> bool:
    name_tokens = set(_tokens(name))
    return bool(name_tokens & PLATFORM_TERMS)


def _is_duplicate_vendor(vendor: str) -> bool:
    return "duplicate" in _clean(vendor).casefold()


def _ordered_failed_apps(apps: list[dict], feedback: dict[str, str]) -> list[str]:
    app_order = [_clean(app.get("Name")) for app in apps]
    return [app_name for app_name in app_order if app_name in feedback]


def _add_feedback(feedback: dict[str, list[str]], app_name: str, reason: str) -> None:
    if not app_name:
        return
    feedback[app_name].append(reason)


def _add_group_feedback(
    feedback: dict[str, list[str]],
    app_names: Iterable[str],
    reason: str,
) -> None:
    for app_name in app_names:
        _add_feedback(feedback, app_name, reason)


def _validate_single_label(
    app: dict,
    label: str,
    feedback: dict[str, list[str]],
) -> None:
    app_name = _clean(app.get("Name"))
    final_l3 = _clean(app.get("L3"))
    vendor = _clean(app.get("Vendor"))
    stripped_label = _clean(label)
    lower_label = stripped_label.casefold()
    label_tokens = _tokens(stripped_label)

    if not stripped_label:
        _add_feedback(feedback, app_name, "Function is missing.")
        return

    if stripped_label != str(label):
        _add_feedback(feedback, app_name, "Function has leading or trailing whitespace.")

    if "\n" in stripped_label or "\t" in stripped_label:
        _add_feedback(feedback, app_name, "Function must be a single-line label.")

    if stripped_label.endswith((".", ":", ";")):
        _add_feedback(feedback, app_name, "Function looks like a sentence, not a category.")

    if len(label_tokens) < 2:
        _add_feedback(feedback, app_name, "Function is too broad. Use a 2 to 5 word category.")

    if len(label_tokens) > 5:
        _add_feedback(feedback, app_name, "Function is too long. Use a short reusable category.")

    if lower_label in TOO_BROAD_LABELS:
        _add_feedback(feedback, app_name, "Function is too broad to support comparison.")

    if final_l3 and lower_label == final_l3.casefold():
        _add_feedback(feedback, app_name, "Function must be more specific than Final L3.")

    if app_name and lower_label == app_name.casefold():
        _add_feedback(feedback, app_name, "Function should describe purpose, not repeat app name.")

    vendor_tokens = _meaningful_vendor_tokens(vendor)
    branded_tokens = vendor_tokens & set(label_tokens)
    if branded_tokens:
        joined = ", ".join(sorted(branded_tokens))
        _add_feedback(feedback, app_name, f"Function appears vendor-branded: {joined}.")

    environment_tokens = ENVIRONMENT_TERMS & set(label_tokens)
    if environment_tokens:
        joined = ", ".join(sorted(environment_tokens))
        _add_feedback(
            feedback,
            app_name,
            f"Function should not include environment or version wording: {joined}.",
        )


def _validate_duplicate_descriptions(
    apps: list[dict],
    function_tags: dict[str, str],
    feedback: dict[str, list[str]],
) -> None:
    groups: dict[str, list[str]] = defaultdict(list)
    for app in apps:
        app_name = _clean(app.get("Name"))
        description = _normalize_description(_clean(app.get("Description")))
        if description:
            groups[description].append(app_name)

    for app_names in groups.values():
        if len(app_names) < 2:
            continue
        labels = {_clean(function_tags.get(app_name)) for app_name in app_names}
        if len(labels) > 1:
            _add_group_feedback(
                feedback,
                app_names,
                "Apps with duplicate descriptions must use the same Function label.",
            )


def _validate_duplicate_vendor_flags(
    apps: list[dict],
    function_tags: dict[str, str],
    feedback: dict[str, list[str]],
) -> None:
    by_normalized_name: dict[str, list[dict]] = defaultdict(list)
    for app in apps:
        by_normalized_name[_normalize_duplicate_name(_clean(app.get("Name")))].append(app)

    for group in by_normalized_name.values():
        if len(group) < 2:
            continue
        if not any(_is_duplicate_vendor(_clean(app.get("Vendor"))) for app in group):
            continue

        app_names = [_clean(app.get("Name")) for app in group]
        labels = {_clean(function_tags.get(app_name)) for app_name in app_names}
        if len(labels) > 1:
            _add_group_feedback(
                feedback,
                app_names,
                "Duplicate-entry apps must use the same Function label as the retained entry.",
            )


def _validate_environment_variants(
    apps: list[dict],
    function_tags: dict[str, str],
    feedback: dict[str, list[str]],
) -> None:
    groups: dict[str, list[dict]] = defaultdict(list)
    for app in apps:
        name = _clean(app.get("Name"))
        normalized = _normalize_env_variant_name(name)
        groups[normalized].append(app)

    for group in groups.values():
        if len(group) < 2:
            continue
        if any(_looks_like_platform_variant(_clean(app.get("Name"))) for app in group):
            continue

        app_names = [_clean(app.get("Name")) for app in group]
        labels = {_clean(function_tags.get(app_name)) for app_name in app_names}
        if len(labels) > 1:
            _add_group_feedback(
                feedback,
                app_names,
                "Environment or version variants of the same app must share the same Function.",
            )


def validator_node(state: ECRState) -> dict:
    """Run deterministic Function tag checks and return validation feedback."""
    apps = state["apps"]
    function_tags = state.get("function_tags", {})
    feedback: dict[str, list[str]] = defaultdict(list)

    for app in apps:
        app_name = _clean(app.get("Name"))
        if app_name not in function_tags:
            _add_feedback(feedback, app_name, "Function tag is missing for this app.")
            continue
        _validate_single_label(app, function_tags.get(app_name, ""), feedback)

    _validate_duplicate_descriptions(apps, function_tags, feedback)
    _validate_duplicate_vendor_flags(apps, function_tags, feedback)
    _validate_environment_variants(apps, function_tags, feedback)

    validator_feedback = {
        app_name: " ".join(dict.fromkeys(reasons))
        for app_name, reasons in feedback.items()
    }
    failed_apps = _ordered_failed_apps(apps, validator_feedback)

    return {
        "failed_apps": failed_apps,
        "validator_feedback": validator_feedback,
        "status": "ecr" if not failed_apps else "tagging",
    }
