"""No-op web evidence helpers for ECR reasoning.

Web search was tested through the Portkey Responses API, but it added cost and
reduced output quality for this portfolio. The active workflow intentionally
uses only the client inventory, Function tags, prior calibration, and same-
Function cleanup hints.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WebEvidence:
    title: str
    url: str
    snippet: str


def _clean(value: object) -> str:
    return str(value or "").strip()


def build_web_evidence(apps: list[dict], l3_name: str) -> dict[str, list[WebEvidence]]:
    """Return no external evidence.

    The ECR agent still calls this helper, but it is intentionally inert so
    production runs do not spend API calls on web search.
    """
    _ = apps
    _ = l3_name
    return {}


def format_web_evidence(evidence_by_app: dict[str, list[WebEvidence]]) -> str:
    """Format supplied evidence if tests or future manual callers pass any in."""
    if not evidence_by_app:
        return ""

    lines = [
        "External evidence, optional support only:",
        "Use this evidence only to support product capability or lifecycle reasoning.",
        "Do not invent a retained app outside the current cluster.",
        "",
    ]
    for app_name, evidence_items in evidence_by_app.items():
        lines.append(f"- App: {app_name}")
        for item in evidence_items:
            source = f" ({item.url})" if item.url else ""
            lines.append(f"  Source: {item.title}{source}")
            lines.append(f"  Evidence: {item.snippet}")
        lines.append("")
    return "\n".join(lines).strip()
