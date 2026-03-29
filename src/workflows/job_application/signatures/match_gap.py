import dspy


class MatchGapReportSignature(dspy.Signature):
    """Assess job fit and identify concrete application gaps for one tracked job."""

    user_profile: str = dspy.InputField()
    verification_summary: str = dspy.InputField()
    search_strategy_summary: str = dspy.InputField()
    hard_preferences: list[str] = dspy.InputField()
    soft_preferences: list[str] = dspy.InputField()
    job_title: str = dspy.InputField()
    company_name: str = dspy.InputField()
    job_description: str = dspy.InputField()
    job_skills: list[str] = dspy.InputField()
    why_apply_snapshot: str = dspy.InputField()
    fit_level: str = dspy.InputField()

    overall_fit_score: int = dspy.OutputField()
    fit_label: str = dspy.OutputField()
    strengths: list[str] = dspy.OutputField()
    gaps: list[str] = dspy.OutputField()
    missing_keywords: list[str] = dspy.OutputField()
    risks: list[str] = dspy.OutputField()
    recommended_positioning_angle: str = dspy.OutputField()
    apply_recommendation: str = dspy.OutputField()
