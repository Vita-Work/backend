import dspy


class SearchPlanSignature(dspy.Signature):
    """Signature for job search planning."""

    planning_context: str = dspy.InputField()
    user_profile: str = dspy.InputField()
    search_strategy_summary: str = dspy.OutputField()
    soft_preferences: list[str] = dspy.OutputField()
    hard_preferences: list[str] = dspy.OutputField()
