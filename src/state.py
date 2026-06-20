from typing import Literal, NotRequired, Optional, TypedDict


class ECRState(TypedDict):
    """Shared LangGraph state for one L3 cluster."""

    # Inputs
    l3_name: str
    apps: list[dict]
    max_retries: int

    # Function tagging
    function_tags: dict[str, str]
    failed_apps: list[str]
    validator_feedback: dict[str, str]

    # ECR
    ecr_decisions: list[dict]
    capability_loss: dict[str, str]
    function_mismatch: Optional[dict]

    # Loop control
    retry_count: int
    status: Literal[
        "tagging",
        "validating",
        "ecr",
        "done",
        "max_retries_hit",
        "error",
    ]

    # Error and review capture for per-cluster failures or repaired rows.
    error_type: NotRequired[str]
    error_message: NotRequired[str]
    capability_loss_issues: NotRequired[list[dict[str, str]]]
