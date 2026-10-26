"""Stable product vocabulary used by storage, skills, and the MCP layer."""

from __future__ import annotations

from dataclasses import dataclass


PILOT_BANDS = ("600-640", "650-690", "700-740", "750-800")
SESSION_MODES = ("default", "strategy_trial")
USER_BAND_LABELS = {
    "600-640": "600–650",
    "650-690": "650–700",
    "700-740": "700–750",
    "750-800": "750–800",
}

LANGUAGES = ("english", "chinese", "bilingual")
EXPLANATION_MODES = ("english", "chinese", "bilingual")
ASSESSMENT_SOURCES = ("manual", "bluebook", "college-board", "gemini-module", "other")
PROVENANCE_TYPES = ("official", "simulated", "licensed", "publisher_reconstruction")
QUESTION_RESULTS = (
    "incorrect",
    "omitted",
    "correct",
    "correct_uncertain",
    "correct_slow",
    "correct_changed",
)
DIAGNOSIS_STATUSES = ("provisional", "supported", "confirmed", "rejected")
SKILL_STAGES = ("recognize", "explain", "execute", "transfer", "stabilize")
TRANSFER_DISTANCES = ("near", "mid", "far")
APPARENT_DIFFICULTY_TAGS = ("routine", "noticeable", "intimidating")
SIMULATED_LABEL = "Simulated SAT-style practice — not an official College Board question"


ERROR_SIGNATURES = {
    "qualifier_omission": "Misses a limiting word, condition, or qualifier.",
    "unsupported_strengthening": "Chooses a claim stronger than the evidence supports.",
    "scope_expansion": "Expands a local claim to a broader scope than the prompt supports.",
    "task_goal_drift": "Solves a nearby task rather than the exact question goal.",
    "structural_misparse": "Misreads clause, modifier, sentence, or passage structure.",
    "premature_answer_selection": "Commits before comparing the stem, evidence, and options.",
    "weak_evidence_threshold": "Accepts plausible language without sufficient textual evidence.",
    "unsupported_answer_change": "Changes a defensible answer without stronger evidence.",
    "time_triggered_rushing": "Accuracy degrades after a time threshold or late-module pressure.",
    "overconfidence": "Confidence is high despite weak evidence or unstable performance.",
    "attention_lapse": "A repeatable attention failure appears under a specified condition.",
    "vocabulary_neighbor_confusion": "Confuses a near-synonym or contextual vocabulary neighbor.",
}

FORBIDDEN_KEYS = {
    "password",
    "passwd",
    "secret",
    "token",
    "access_token",
    "refresh_token",
    "api_key",
    "apikey",
    "cookie",
    "auth_header",
    "authentication_token",
    "screenshot",
    "screenshot_path",
    "page_html",
    "html",
    "full_passage",
    "passage_text",
    "question_text",
    "answer_choices",
    "official_rationale",
    "official_explanation",
    "copied_content",
}


@dataclass(frozen=True)
class BandDefault:
    """Instructional prior, not a rigid curriculum."""

    band: str
    mode: str
    activity_mix: tuple[tuple[str, int], ...]
    support: str


BAND_DEFAULTS = {
    "600-640": BandDefault(
        "600-640",
        "guided_foundation",
        (("guided_practice_block", 18), ("review_reflection", 2)),
        "Explicit teaching, bilingual clarification, worked examples, and slower fading of support.",
    ),
    "650-690": BandDefault(
        "650-690",
        "reliability_procedure",
        (("targeted_practice_block", 18), ("review_reflection", 2)),
        "Question-type recognition, rule retrieval, distractor analysis, and guided-to-independent practice.",
    ),
    "700-740": BandDefault(
        "700-740",
        "transfer_discrimination",
        (("interleaved_transfer_block", 18), ("review_reflection", 2)),
        "Transfer, difficult distractor distinctions, efficiency, and interleaving.",
    ),
    "750-800": BandDefault(
        "750-800",
        "precision_variance_reduction",
        (("timed_precision_block", 17), ("review_reflection", 3)),
        "Near-misses, timing, confidence calibration, rare traps, fatigue, and score-floor stability.",
    ),
}

STRATEGY_TRIAL_MIX = (
    ("focused_diagnostic_block", 14),
    ("strategy_reflection_block", 6),
)


def band_for_score(score: int | None) -> str:
    """Map a score to an instructional prior; boundary cases use nearest band."""
    if score is None:
        return "650-690"
    if score <= 645:
        return "600-640"
    if score <= 695:
        return "650-690"
    if score <= 745:
        return "700-740"
    return "750-800"
