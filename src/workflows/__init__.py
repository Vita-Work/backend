"""Workflow package exports."""


def build_search_setup_graph(*args, **kwargs):
    """Lazily import and build the search-setup graph."""
    from src.workflows.search_setup.graph import build_search_setup_graph as _build

    return _build(*args, **kwargs)


__all__ = ["build_search_setup_graph"]
