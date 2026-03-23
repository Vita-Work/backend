import dspy


class SearchJobExecutionPlanSignature(dspy.Signature):
    """Signature for building a runtime search execution plan."""

    search_strategy_summary: str = dspy.InputField()
    hard_preferences: list[str] = dspy.InputField()
    soft_preferences: list[str] = dspy.InputField()
    available_sites: list[str] = dspy.InputField()

    queries: list[str] = dspy.OutputField()
    include_keywords: list[str] = dspy.OutputField()
    exclude_keywords: list[str] = dspy.OutputField()
    locations: list[str] = dspy.OutputField()
    remote_only: bool = dspy.OutputField()
    salary_from: int | None = dspy.OutputField()
    seniority: str | None = dspy.OutputField()
    target_sites: list[str] = dspy.OutputField()
    notes: list[str] = dspy.OutputField()
