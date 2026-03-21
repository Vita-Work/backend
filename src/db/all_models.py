"""
This module imports all models to make them available for migrations.
Import this module explicitly when needed, but avoid importing it during normal application startup.
"""

from src.modules.extraction.models import ExtractionWorkflowRun
from src.modules.onboarding.models import OnboardingSession
from src.modules.users.models import User

__all__ = ["ExtractionWorkflowRun", "OnboardingSession", "User"]
