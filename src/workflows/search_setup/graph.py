from langgraph.graph import END, START, StateGraph

from src.workflows.search_setup.nodes.clarification import (
    clarification_node,
    need_more_context_node,
)
from src.workflows.search_setup.nodes.confirm import confirm_node
from src.workflows.search_setup.nodes.extraction import extraction_node
from src.workflows.search_setup.nodes.search_plan import search_plan_node
from src.workflows.search_setup.nodes.verify import verify_node
from src.workflows.search_setup.state import SearchSetupState


def build_search_setup_graph(*, checkpointer=None):
    """Build the unified search-setup onboarding workflow graph."""
    graph = StateGraph(SearchSetupState)
    graph.add_node("extraction", extraction_node)
    graph.add_node("clarification", clarification_node)
    graph.add_node("need_more_context", need_more_context_node)
    graph.add_node("verify", verify_node)
    graph.add_node("search_plan", search_plan_node)
    graph.add_node("confirm", confirm_node)
    graph.add_edge(START, "extraction")
    graph.add_edge("extraction", "clarification")
    graph.add_conditional_edges(
        "clarification",
        _route_after_clarification,
        {
            "need_more_context": "need_more_context",
            "verify": "verify",
        },
    )
    graph.add_edge("need_more_context", "clarification")
    graph.add_conditional_edges(
        "verify",
        _route_after_verify,
        {
            "clarification": "clarification",
            "search_plan": "search_plan",
        },
    )
    graph.add_edge("search_plan", "confirm")
    graph.add_conditional_edges(
        "confirm",
        _route_after_confirm,
        {
            "clarification": "clarification",
            END: END,
        },
    )
    return graph.compile(checkpointer=checkpointer)


def _route_after_clarification(state: SearchSetupState):
    return "need_more_context" if state.get("pending_user_prompt") else "verify"


def _route_after_verify(state: SearchSetupState):
    return "search_plan" if state.get("profile_verified") else "clarification"


def _route_after_confirm(state: SearchSetupState):
    return END if state.get("confirmed") else "clarification"
