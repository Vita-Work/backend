"""
This module imports all models to make them available for migrations.
Import this module explicitly when needed, but avoid importing it during normal application startup.
"""

from src.modules.auth.models import AuthEmailChallenge, AuthSession
from src.modules.extraction.models import ExtractionWorkflowRun
from src.modules.job_tracker.models import TrackedJob, TrackedJobActivity, TrackedJobContact
from src.modules.onboarding.models import OnboardingSession
from src.modules.search_jobs.models import SearchJobWorkflowRun
from src.modules.users.models import User

__all__ = [
    "AuthEmailChallenge",
    "AuthSession",
    "ExtractionWorkflowRun",
    "TrackedJob",
    "TrackedJobActivity",
    "TrackedJobContact",
    "OnboardingSession",
    "SearchJobWorkflowRun",
    "User",
]
