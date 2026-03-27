from __future__ import annotations

from src.config import get_settings
from src.extensions.gemini import get_gemini_embeddings_service
from src.logger import get_logger
from src.workflows.search_job.dedupe import (
    canonical_job_url,
    cosine_similarity,
    locations_compatible,
    text_similarity,
)
from src.workflows.search_job.history import build_job_fingerprint
from src.workflows.search_job.schemas import DetailFetchCandidate, ListingCandidate
from src.workflows.search_job.state import SearchJobState

logger = get_logger("workflows.search_job.listing_dedupe")


async def listing_dedupe_node(state: SearchJobState) -> dict[str, object]:
    """Deduplicate and pre-rank listing candidates before detail fetch."""
    plan = state["execution_plan"]
    listings = state.get("listing_candidates", [])
    log = logger.bind(
        user_id=state["user_id"],
        onboarding_session_id=state["onboarding_session_id"],
    )
    log.info("search_job_listing_dedupe_started", listing_candidates_count=len(listings))

    exact_seen: dict[str, DetailFetchCandidate] = {}
    fingerprint_seen: dict[str, DetailFetchCandidate] = {}
    notes: list[str] = []
    seen_job_urls = set(state.get("seen_job_urls", []))
    seen_job_fingerprints = set(state.get("seen_job_fingerprints", []))

    for candidate in listings:
        if _should_reject_listing(
            candidate=candidate,
            plan=plan,
            monitoring_mode=state.get("monitoring_mode", False),
            seen_job_urls=seen_job_urls,
            seen_job_fingerprints=seen_job_fingerprints,
        ):
            continue

        detail_candidate = DetailFetchCandidate(
            site=candidate.site,
            job_url=canonical_job_url(candidate.job_url),
            title=candidate.title,
            company_name=candidate.company_name,
            location=candidate.location,
            salary_text=candidate.salary_text,
            published_at=candidate.published_at,
            company_url=candidate.company_url,
            source_queries=[candidate.query],
        )

        url_key = detail_candidate.job_url
        existing_exact = exact_seen.get(url_key)
        if existing_exact is not None:
            exact_seen[url_key] = _merge_detail_candidates(existing_exact, detail_candidate, plan)
            continue

        fingerprint_key = _listing_fingerprint(detail_candidate)
        if fingerprint_key:
            existing_fingerprint = fingerprint_seen.get(fingerprint_key)
            if existing_fingerprint is not None:
                fingerprint_seen[fingerprint_key] = _merge_detail_candidates(
                    existing_fingerprint,
                    detail_candidate,
                    plan,
                )
                continue
            fingerprint_seen[fingerprint_key] = detail_candidate
            exact_seen[url_key] = detail_candidate
            continue

        exact_seen[url_key] = detail_candidate

    settings = get_settings()
    ranked_candidates = sorted(
        exact_seen.values(),
        key=lambda candidate: (
            -_listing_priority_score(candidate=candidate, plan=plan),
            (candidate.title or "").lower(),
            (candidate.company_name or "").lower(),
        ),
    )
    deduped_listings = await _apply_embedding_dedupe(
        candidates=ranked_candidates[: settings.search_job_unified_max_jobs],
        plan=plan,
        similarity_threshold=settings.search_job_listing_embedding_similarity_threshold,
        top_k=settings.search_job_embedding_top_k,
        log=log,
    )
    deduped_listings = deduped_listings[: settings.search_job_detail_max_jobs]
    notes.append(
        "listing_dedupe: kept "
        f"{len(deduped_listings)} of {len(listings)} listing candidates for detail fetch"
    )
    log.info(
        "search_job_listing_dedupe_completed",
        deduped_listings_count=len(deduped_listings),
    )
    return {
        "status": "deduping",
        "deduped_listings": deduped_listings,
        "batch_notes": notes,
    }


def _should_reject_listing(
    *,
    candidate: ListingCandidate,
    plan,
    monitoring_mode: bool,
    seen_job_urls: set[str],
    seen_job_fingerprints: set[str],
) -> bool:
    if monitoring_mode:
        canonical_url = canonical_job_url(candidate.job_url)
        fingerprint = build_job_fingerprint(
            title=candidate.title,
            company_name=candidate.company_name,
            location=candidate.location,
        )
        if canonical_url in seen_job_urls:
            return True
        if fingerprint is not None and fingerprint in seen_job_fingerprints:
            return True

    haystack = " ".join(
        filter(
            None,
            [
                candidate.title,
                candidate.company_name,
                candidate.location,
                candidate.salary_text,
            ],
        )
    ).lower()
    for keyword in plan.exclude_keywords:
        if keyword.lower() in haystack:
            return True
    return False


def _merge_detail_candidates(
    current: DetailFetchCandidate,
    incoming: DetailFetchCandidate,
    plan,
) -> DetailFetchCandidate:
    best = current
    if _listing_priority_score(candidate=incoming, plan=plan) > _listing_priority_score(
        candidate=current,
        plan=plan,
    ):
        best = incoming
    return best.model_copy(
        update={
            "source_queries": list(dict.fromkeys(current.source_queries + incoming.source_queries)),
            "company_url": best.company_url or current.company_url or incoming.company_url,
        }
    )


def _listing_priority_score(*, candidate: DetailFetchCandidate, plan) -> int:
    haystack = " ".join(
        filter(
            None,
            [
                candidate.title,
                candidate.company_name,
                candidate.location,
                candidate.salary_text,
            ],
        )
    ).lower()
    score = 0
    for query in candidate.source_queries:
        if query.lower() in haystack:
            score += 4
    for keyword in plan.include_keywords:
        if keyword.lower() in haystack:
            score += 2
    if candidate.title:
        score += 2
    if candidate.company_name:
        score += 1
    if candidate.published_at:
        score += 1
    if plan.remote_only and "remote" in (candidate.location or "").lower():
        score += 2
    return score


def _listing_fingerprint(candidate: DetailFetchCandidate) -> str | None:
    return build_job_fingerprint(
        title=candidate.title,
        company_name=candidate.company_name,
        location=candidate.location,
    )


async def _apply_embedding_dedupe(
    *,
    candidates: list[DetailFetchCandidate],
    plan,
    similarity_threshold: float,
    top_k: int,
    log,
) -> list[DetailFetchCandidate]:
    if len(candidates) < 2:
        return candidates

    embedding_texts = [_listing_embedding_text(candidate) for candidate in candidates]
    try:
        embeddings = await get_gemini_embeddings_service().embed_texts(texts=embedding_texts)
    except Exception as exc:
        log.warning(
            "search_job_listing_embedding_dedupe_failed",
            candidates_count=len(candidates),
            error=str(exc),
        )
        return candidates

    survivors: list[DetailFetchCandidate] = []
    survivor_embeddings: list[list[float]] = []
    for index, candidate in enumerate(candidates):
        duplicate_index = _find_embedding_duplicate_index(
            candidate=candidate,
            candidate_embedding=embeddings[index],
            existing_candidates=survivors,
            existing_embeddings=survivor_embeddings,
            similarity_threshold=similarity_threshold,
            top_k=top_k,
        )
        if duplicate_index is None:
            survivors.append(candidate)
            survivor_embeddings.append(embeddings[index])
            continue

        merged = _merge_detail_candidates(survivors[duplicate_index], candidate, plan)
        if merged != survivors[duplicate_index]:
            survivors[duplicate_index] = merged
            survivor_embeddings[duplicate_index] = embeddings[index]

    log.info(
        "search_job_listing_embedding_dedupe_completed",
        candidates_count=len(candidates),
        survivors_count=len(survivors),
    )
    return survivors


def _find_embedding_duplicate_index(
    *,
    candidate: DetailFetchCandidate,
    candidate_embedding: list[float],
    existing_candidates: list[DetailFetchCandidate],
    existing_embeddings: list[list[float]],
    similarity_threshold: float,
    top_k: int,
) -> int | None:
    if not existing_candidates:
        return None

    scored_matches = sorted(
        (
            (
                cosine_similarity(candidate_embedding, existing_embedding),
                existing_index,
                existing_candidates[existing_index],
            )
            for existing_index, existing_embedding in enumerate(existing_embeddings)
        ),
        key=lambda item: item[0],
        reverse=True,
    )[:top_k]

    for similarity, existing_index, existing_candidate in scored_matches:
        if similarity < similarity_threshold:
            continue
        if _is_embedding_duplicate(
            left=candidate,
            right=existing_candidate,
            similarity=similarity,
        ):
            return existing_index
    return None


def _is_embedding_duplicate(
    *,
    left: DetailFetchCandidate,
    right: DetailFetchCandidate,
    similarity: float,
) -> bool:
    company_similarity = text_similarity(left.company_name, right.company_name)
    title_similarity = text_similarity(left.title, right.title)
    if similarity >= 0.98 and company_similarity >= 0.85:
        return True
    if company_similarity < 0.88 or title_similarity < 0.7:
        return False
    if not locations_compatible(left.location, right.location):
        return False
    return True


def _listing_embedding_text(candidate: DetailFetchCandidate) -> str:
    return " | ".join(
        part
        for part in (
            candidate.title,
            candidate.company_name,
            candidate.location,
            candidate.salary_text,
            ", ".join(candidate.source_queries[:3]),
        )
        if part
    )
