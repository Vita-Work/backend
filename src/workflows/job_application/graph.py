from __future__ import annotations

import json
from functools import lru_cache

from langgraph.graph import END, START, StateGraph

from src.extensions.dspy import get_dspy_search_setup_service
from src.extensions.gemini import get_gemini_job_application_service
from src.workflows.job_application.state import JobApplicationState


async def load_application_context_node(state: JobApplicationState) -> dict[str, object]:
    context = state.get("context")
    if not isinstance(context, dict) or not context.get("job_title"):
        raise ValueError("Tracked job application context is missing or incomplete.")
    return {"status": "context_loaded"}


async def check_cached_outputs_node(state: JobApplicationState) -> dict[str, object]:
    run_type = state["run_type"]
    cached_completed_payload = state.get("cached_completed_payload")
    cached_match_gap_report = state.get("cached_match_gap_report")

    if run_type == "match_gap" and isinstance(cached_completed_payload, dict):
        return {
            "status": "completed",
            "match_gap_report": dict(cached_completed_payload),
            "final_payload": dict(cached_completed_payload),
        }

    if run_type == "job_pack" and isinstance(cached_match_gap_report, dict):
        return {
            "status": "match_gap_cached",
            "match_gap_report": dict(cached_match_gap_report),
        }

    return {"status": "cache_miss"}


async def build_match_gap_report_node(state: JobApplicationState) -> dict[str, object]:
    context = dict(state["context"])
    service = get_dspy_search_setup_service()
    result = await service.build_match_gap_report(
        user_profile=str(context.get("user_profile") or ""),
        verification_summary=str(context.get("verification_summary") or ""),
        search_strategy_summary=str(context.get("search_strategy_summary") or ""),
        hard_preferences=list(context.get("hard_preferences") or []),
        soft_preferences=list(context.get("soft_preferences") or []),
        job_title=str(context.get("job_title") or ""),
        company_name=str(context.get("company_name") or ""),
        job_description=str(context.get("job_description") or ""),
        job_skills=list(context.get("job_skills") or []),
        why_apply_snapshot=str(context.get("why_apply_snapshot") or ""),
        fit_level=str(context.get("fit_level") or ""),
    )
    payload = result.model_dump(mode="json")
    if state["run_type"] == "match_gap":
        return {
            "status": "completed",
            "match_gap_report": payload,
            "final_payload": payload,
        }
    return {"status": "match_gap_built", "match_gap_report": payload}


async def build_tailoring_plan_node(state: JobApplicationState) -> dict[str, object]:
    context = dict(state["context"])
    match_gap_report = dict(state["match_gap_report"])
    service = get_dspy_search_setup_service()
    result = await service.build_tailor_resume_plan(
        user_profile=str(context.get("user_profile") or ""),
        verification_summary=str(context.get("verification_summary") or ""),
        search_strategy_summary=str(context.get("search_strategy_summary") or ""),
        hard_preferences=list(context.get("hard_preferences") or []),
        soft_preferences=list(context.get("soft_preferences") or []),
        job_title=str(context.get("job_title") or ""),
        company_name=str(context.get("company_name") or ""),
        job_description=str(context.get("job_description") or ""),
        job_skills=list(context.get("job_skills") or []),
        why_apply_snapshot=str(context.get("why_apply_snapshot") or ""),
        fit_level=str(context.get("fit_level") or ""),
        match_gap_report=json.dumps(match_gap_report, ensure_ascii=False),
    )
    return {"status": "tailoring_planned", "tailoring_plan": result.model_dump(mode="json")}


async def generate_tailored_resume_node(state: JobApplicationState) -> dict[str, object]:
    service = get_gemini_job_application_service()
    result = await service.generate_tailored_resume(
        application_context=dict(state["context"]),
        tailoring_plan=dict(state["tailoring_plan"]),
        match_gap_report=dict(state["match_gap_report"]),
    )
    return {"status": "resume_generated", "tailored_resume": result.model_dump(mode="json")}


async def generate_application_packet_node(state: JobApplicationState) -> dict[str, object]:
    service = get_gemini_job_application_service()
    result = await service.generate_application_packet(
        application_context=dict(state["context"]),
        tailoring_plan=dict(state["tailoring_plan"]),
        match_gap_report=dict(state["match_gap_report"]),
        tailored_resume=dict(state["tailored_resume"]),
    )
    return {
        "status": "completed",
        "application_packet": result.model_dump(mode="json"),
    }


async def finalize_ai_run_node(state: JobApplicationState) -> dict[str, object]:
    if state["run_type"] == "match_gap":
        payload = dict(state.get("final_payload") or state.get("match_gap_report") or {})
        return {"status": "completed", "final_payload": payload}

    payload = {
        "match_gap_report": dict(state.get("match_gap_report") or {}),
        "tailoring_plan": dict(state.get("tailoring_plan") or {}),
        "tailored_resume": dict(state.get("tailored_resume") or {}),
        "application_packet": dict(state.get("application_packet") or {}),
    }
    return {"status": "completed", "final_payload": payload}


def _route_after_cache_check(state: JobApplicationState) -> str:
    if state.get("status") == "completed":
        return "finalize_ai_run"
    if state["run_type"] == "job_pack" and isinstance(state.get("match_gap_report"), dict):
        return "build_tailoring_plan"
    return "build_match_gap_report"


def _route_after_match_gap(state: JobApplicationState) -> str:
    if state["run_type"] == "match_gap":
        return "finalize_ai_run"
    return "build_tailoring_plan"


def build_job_application_graph():
    graph = StateGraph(JobApplicationState)
    graph.add_node("load_application_context", load_application_context_node)
    graph.add_node("check_cached_outputs", check_cached_outputs_node)
    graph.add_node("build_match_gap_report", build_match_gap_report_node)
    graph.add_node("build_tailoring_plan", build_tailoring_plan_node)
    graph.add_node("generate_tailored_resume", generate_tailored_resume_node)
    graph.add_node("generate_application_packet", generate_application_packet_node)
    graph.add_node("finalize_ai_run", finalize_ai_run_node)

    graph.add_edge(START, "load_application_context")
    graph.add_edge("load_application_context", "check_cached_outputs")
    graph.add_conditional_edges("check_cached_outputs", _route_after_cache_check)
    graph.add_conditional_edges("build_match_gap_report", _route_after_match_gap)
    graph.add_edge("build_tailoring_plan", "generate_tailored_resume")
    graph.add_edge("generate_tailored_resume", "generate_application_packet")
    graph.add_edge("generate_application_packet", "finalize_ai_run")
    graph.add_edge("finalize_ai_run", END)
    return graph.compile()


@lru_cache(maxsize=1)
def get_job_application_graph():
    return build_job_application_graph()
