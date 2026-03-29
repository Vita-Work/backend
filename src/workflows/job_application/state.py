from __future__ import annotations

from typing import NotRequired, TypedDict


class JobApplicationState(TypedDict):
    run_id: str
    run_type: str
    user_id: str
    tracked_job_id: str
    context: NotRequired[dict[str, object]]
    source_profile_hash: NotRequired[str]
    source_job_hash: NotRequired[str]
    cached_match_gap_report: NotRequired[dict[str, object]]
    match_gap_report: NotRequired[dict[str, object]]
    tailoring_plan: NotRequired[dict[str, object]]
    tailored_resume: NotRequired[dict[str, object]]
    application_packet: NotRequired[dict[str, object]]
    cached_completed_payload: NotRequired[dict[str, object]]
    final_payload: NotRequired[dict[str, object]]
    status: NotRequired[str]
    error_message: NotRequired[str | None]
