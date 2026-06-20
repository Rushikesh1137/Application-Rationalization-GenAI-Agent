from langgraph.graph import END, START, StateGraph

from src.agents.ecr_recommender import ecr_recommender_node
from src.agents.function_tagger import function_tagger_node
from src.routing import route_after_ecr, route_after_validation
from src.state import ECRState
from src.validator import validator_node


def increment_retry_node(state: ECRState) -> dict:
    """Increment the shared retry counter before routing back to Agent 1."""
    return {
        "retry_count": state["retry_count"] + 1,
        "status": "tagging",
    }


def end_with_flag_node(state: ECRState) -> dict:
    """Mark the cluster for human review after retry budget exhaustion."""
    return {"status": "max_retries_hit"}


def build_graph():
    """Assemble the LangGraph state machine."""
    graph = StateGraph(ECRState)

    graph.add_node("agent_1", function_tagger_node)
    graph.add_node("validator", validator_node)
    graph.add_node("agent_2", ecr_recommender_node)
    graph.add_node("increment_retry", increment_retry_node)
    graph.add_node("end_with_flag", end_with_flag_node)

    graph.add_edge(START, "agent_1")
    graph.add_edge("agent_1", "validator")
    graph.add_conditional_edges(
        "validator",
        route_after_validation,
        {
            "agent_2": "agent_2",
            "agent_1": "increment_retry",
            "end_with_flag": "end_with_flag",
        },
    )
    graph.add_edge("increment_retry", "agent_1")
    graph.add_conditional_edges(
        "agent_2",
        route_after_ecr,
        {
            "agent_1": "increment_retry",
            "end_with_flag": "end_with_flag",
            "end": END,
        },
    )
    graph.add_edge("end_with_flag", END)

    return graph.compile()
