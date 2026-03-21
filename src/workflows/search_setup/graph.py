from langgraph.graph import END, START, StateGraph

from src.workflows.search_setup.nodes.extraction import extraction_node
from src.workflows.search_setup.state import SearchSetupState


def build_search_setup_graph():
    """Build the search-setup workflow graph."""
    graph = StateGraph(SearchSetupState)
    graph.add_node("extraction", extraction_node)
    graph.add_edge(START, "extraction")
    graph.add_edge("extraction", END)
    return graph.compile()
