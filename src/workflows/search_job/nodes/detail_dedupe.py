from __future__ import annotations

from src.config import get_settings
from src.extensions.gemini import get_gemini_embeddings_service
from src.logger import get_logger
from src.workflows.search_job.dedupe import (
    canonical_job_url,
    cosine_similarity,
    locations_compatible,
    normalize_text,
    text_similarity,
)
from src.workflows.search_job.schemas import SiteJobDetail
from src.workflows.search_job.state import SearchJobState

logger = get_logger("workflows.search_job.detail_dedupe")


async def detail_dedupe_node(state: SearchJobState) -> dict[str, object]:
    """Deduplicate detailed jobs before LLM ranking."""
    plan = state["execution_plan"]
    details = state.get("detailed_jobs", [])
    log = logger.bind(
        user_id=state["user_id"],
        onboarding_session_id=state["onboarding_session_id"],
    )
    log.info("search_job_detail_dedupe_started", detailed_jobs_count=len(details))

    deduped_by_url: dict[str, SiteJobDetail] = {}
    deduped_by_fingerprint: dict[str, SiteJobDetail] = {}
    for detail in details:
        if _should_reject_detail(detail=detail, plan=plan):
            continue

        canonical_url = canonical_job_url(detail.job_url)
        existing = deduped_by_url.get(canonical_url)
        if existing is not None:
            deduped_by_url[canonical_url] = _prefer_detail(existing, detail)
            continue

        fingerprint = _detail_fingerprint(detail)
        if fingerprint:
            existing_fingerprint = deduped_by_fingerprint.get(fingerprint)
            if existing_fingerprint is not None:
                preferred = _prefer_detail(existing_fingerprint, detail)
                deduped_by_fingerprint[fingerprint] = preferred
                continue
            deduped_by_fingerprint[fingerprint] = detail
            continue

        deduped_by_url[canonical_url] = detail

    settings = get_settings()
    deduped_values = list(deduped_by_fingerprint.values()) + list(deduped_by_url.values())
    ranked_details = sorted(
        deduped_values,
        key=lambda job: (
            -(1 if job.description else 0),
            -(len(job.skills)),
            (job.title or "").lower(),
            (job.company_name or "").lower(),
        ),
    )[: settings.search_job_unified_max_jobs]
    deduped_details = await _apply_embedding_dedupe(
        details=ranked_details,
        similarity_threshold=settings.search_job_detail_embedding_similarity_threshold,
        top_k=settings.search_job_embedding_top_k,
        log=log,
    )
    note = f"detail_dedupe: kept {len(deduped_details)} of {len(details)} detailed jobs"
    log.info("search_job_detail_dedupe_completed", deduped_details_count=len(deduped_details))
    return {
        "deduped_details": deduped_details,
        "batch_notes": [note],
    }


def _should_reject_detail(*, detail: SiteJobDetail, plan) -> bool:
    haystack = " ".join(
        filter(
            None,
            [
                detail.title,
                detail.company_name,
                detail.location,
                detail.description,
                " ".join(detail.skills),
            ],
        )
    ).lower()
    for keyword in plan.exclude_keywords:
        if keyword.lower() in haystack:
            return True
    if plan.include_keywords:
        return not any(keyword.lower() in haystack for keyword in plan.include_keywords)
    return False


def _prefer_detail(current: SiteJobDetail, incoming: SiteJobDetail) -> SiteJobDetail:
    current_score = _detail_completeness_score(current)
    incoming_score = _detail_completeness_score(incoming)
    preferred = incoming if incoming_score > current_score else current

    merged_queries = list(
        dict.fromkeys(
            list(current.raw_meta.get("source_queries", []))
            + list(incoming.raw_meta.get("source_queries", []))
        )
    )
    raw_meta = dict(preferred.raw_meta)
    raw_meta["source_queries"] = merged_queries
    return preferred.model_copy(update={"raw_meta": raw_meta})


def _detail_completeness_score(detail: SiteJobDetail) -> int:
    return sum(
        1
        for value in (
            detail.title,
            detail.company_name,
            detail.location,
            detail.description,
            detail.salary_text,
            detail.apply_url,
        )
        if value
    ) + len(detail.skills)


def _detail_fingerprint(detail: SiteJobDetail) -> str | None:
    title = normalize_text(detail.title)
    company = normalize_text(detail.company_name)
    location = normalize_text(detail.location)
    if not title or not company:
        return None
    return "|".join([title, company, location])


async def _apply_embedding_dedupe(
    *,
    details: list[SiteJobDetail],
    similarity_threshold: float,
    top_k: int,
    log,
) -> list[SiteJobDetail]:
    if len(details) < 2:
        return details

    embedding_texts = [_detail_embedding_text(detail) for detail in details]
    try:
        embeddings = await get_gemini_embeddings_service().embed_texts(texts=embedding_texts)
    except Exception as exc:
        log.warning(
            "search_job_detail_embedding_dedupe_failed",
            details_count=len(details),
            error=str(exc),
        )
        return details

    survivors: list[SiteJobDetail] = []
    survivor_embeddings: list[list[float]] = []
    for index, detail in enumerate(details):
        duplicate_index = _find_embedding_duplicate_index(
            detail=detail,
            detail_embedding=embeddings[index],
            existing_details=survivors,
            existing_embeddings=survivor_embeddings,
            similarity_threshold=similarity_threshold,
            top_k=top_k,
        )
        if duplicate_index is None:
            survivors.append(detail)
            survivor_embeddings.append(embeddings[index])
            continue

        preferred = _prefer_detail(survivors[duplicate_index], detail)
        if preferred != survivors[duplicate_index]:
            survivors[duplicate_index] = preferred
            survivor_embeddings[duplicate_index] = embeddings[index]

    log.info(
        "search_job_detail_embedding_dedupe_completed",
        details_count=len(details),
        survivors_count=len(survivors),
    )
    return survivors


def _find_embedding_duplicate_index(
    *,
    detail: SiteJobDetail,
    detail_embedding: list[float],
    existing_details: list[SiteJobDetail],
    existing_embeddings: list[list[float]],
    similarity_threshold: float,
    top_k: int,
) -> int | None:
    if not existing_details:
        return None

    scored_matches = sorted(
        (
            (
                cosine_similarity(detail_embedding, existing_embedding),
                existing_index,
                existing_details[existing_index],
            )
            for existing_index, existing_embedding in enumerate(existing_embeddings)
        ),
        key=lambda item: item[0],
        reverse=True,
    )[:top_k]

    for similarity, existing_index, existing_detail in scored_matches:
        if similarity < similarity_threshold:
            continue
        if _is_embedding_duplicate(
            left=detail,
            right=existing_detail,
            similarity=similarity,
        ):
            return existing_index
    return None


def _is_embedding_duplicate(
    *,
    left: SiteJobDetail,
    right: SiteJobDetail,
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


def _detail_embedding_text(detail: SiteJobDetail) -> str:
    description_excerpt = (detail.description or "")[:1200]
    skills = ", ".join(detail.skills[:12])
    return " | ".join(
        part
        for part in (
            detail.title,
            detail.company_name,
            detail.location,
            detail.salary_text,
            skills,
            description_excerpt,
        )
        if part
    )
