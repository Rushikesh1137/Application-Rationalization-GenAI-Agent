from src.state import ECRState


def _all_apps_have_function_tags(state: ECRState) -> bool:
    function_tags = state.get("function_tags", {})
    for app in state["apps"]:
        app_name = str(app.get("Name") or "").strip()
        if app_name and not str(function_tags.get(app_name) or "").strip():
            return False
    return True


def route_after_validation(state: ECRState) -> str:
    """Route after validator."""
    if not state["failed_apps"]:
        return "agent_2"
    if state["retry_count"] >= state["max_retries"]:
        # For large portfolio runs, a strict Function-label validator should not
        # block ECR forever if Agent 1 has supplied a tag for every app. Agent 2
        # can still produce a useful recommendation, and the retry count remains
        # visible in the run log.
        return "agent_2" if _all_apps_have_function_tags(state) else "end_with_flag"
    return "agent_1"


def route_after_ecr(state: ECRState) -> str:
    """Route after ECR recommender."""
    if state.get("function_mismatch"):
        if state["retry_count"] >= state["max_retries"]:
            return "end_with_flag"
        return "agent_1"
    return "end"
