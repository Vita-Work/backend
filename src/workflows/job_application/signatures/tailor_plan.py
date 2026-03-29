import dspy


class TailorResumePlanSignature(dspy.Signature):
    """Create a compact, fact-grounded transformation plan for a tailored application."""

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
    match_gap_report: str = dspy.InputField()

    target_headline: str = dspy.OutputField()
    target_summary_angle: str = dspy.OutputField()
    must_emphasize: list[str] = dspy.OutputField()
    must_downplay: list[str] = dspy.OutputField()
    must_include_keywords: list[str] = dspy.OutputField()
    forbidden_claims: list[str] = dspy.OutputField()
    experience_reordering_strategy: str = dspy.OutputField()
    cover_letter_angle: str = dspy.OutputField()
    recruiter_intro_angle: str = dspy.OutputField()
