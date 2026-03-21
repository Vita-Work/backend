from __future__ import annotations

from src.services.job_parsers.schemas import SearchIntent


def _normalize_term(term: str) -> str:
    return " ".join(term.lower().strip().split())


def build_query_terms(intent: SearchIntent) -> list[str]:
    search_text = intent.search_text if intent.search_text is not None else intent.role
    normalized = _normalize_term(search_text)
    return [normalized] if normalized else []
