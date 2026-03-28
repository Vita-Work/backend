"""
This module imports all models to make them available for migrations.
Import this module explicitly when needed, but avoid importing it during normal application startup.
"""

from src.modules.auth.models import AuthEmailChallenge, AuthSession
from src.modules.billing.models import BillingSubscription, BillingWebhookEvent
from src.modules.extraction.models import ExtractionProgressEvent, ExtractionWorkflowRun
from src.modules.job_tracker.models import TrackedJob, TrackedJobActivity, TrackedJobContact
from src.modules.onboarding.models import OnboardingSession
from src.modules.search_jobs.models import (
    SearchJobProgressEvent,
    SearchJobSeenJob,
    SearchJobWorkflowRun,
)
from src.modules.users.models import User

__all__ = [
    "AuthEmailChallenge",
    "AuthSession",
    "BillingSubscription",
    "BillingWebhookEvent",
    "ExtractionProgressEvent",
    "ExtractionWorkflowRun",
    "TrackedJob",
    "TrackedJobActivity",
    "TrackedJobContact",
    "OnboardingSession",
    "SearchJobProgressEvent",
    "SearchJobSeenJob",
    "SearchJobWorkflowRun",
    "User",
]
