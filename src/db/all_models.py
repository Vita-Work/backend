"""
This module imports all models to make them available for migrations.
Import this module explicitly when needed, but avoid importing it during normal application startup.
"""

from src.modules.auth.models import AuthEmailChallenge, AuthSession
from src.modules.billing.models import (
    BillingAccessPass,
    BillingCreditLedgerEntry,
    BillingSubscription,
    BillingWebhookEvent,
)
from src.modules.extraction.models import ExtractionProgressEvent, ExtractionWorkflowRun
from src.modules.job_ai.models import TrackedJobAiRun
from src.modules.job_tracker.models import TrackedJob, TrackedJobActivity, TrackedJobContact
from src.modules.onboarding.models import OnboardingSession
from src.modules.resume_intakes.models import ResumeIntake
from src.modules.search_jobs.models import (
    SearchJobProgressEvent,
    SearchJobSeenJob,
    SearchJobWorkflowRun,
)
from src.modules.users.models import User

__all__ = [
    "AuthEmailChallenge",
    "AuthSession",
    "BillingAccessPass",
    "BillingCreditLedgerEntry",
    "BillingSubscription",
    "BillingWebhookEvent",
    "ExtractionProgressEvent",
    "ExtractionWorkflowRun",
    "TrackedJobAiRun",
    "TrackedJob",
    "TrackedJobActivity",
    "TrackedJobContact",
    "OnboardingSession",
    "ResumeIntake",
    "SearchJobProgressEvent",
    "SearchJobSeenJob",
    "SearchJobWorkflowRun",
    "User",
]
