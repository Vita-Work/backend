import dspy


class VerifyProfileSignature(dspy.Signature):
    """Assess whether the candidate profile is sufficiently grounded for planning."""

    user_profile: str = dspy.InputField()
    missing_info: list[str] = dspy.InputField()
    clarification_chat: str = dspy.InputField()
    verification_score: float = dspy.OutputField()
    is_verified: bool = dspy.OutputField()
    verification_summary: str = dspy.OutputField()
    remaining_gaps: list[str] = dspy.OutputField()
