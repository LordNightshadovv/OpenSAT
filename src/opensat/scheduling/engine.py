"""Evidence-sensitive scheduling without a universal memory-curve promise."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from ..domain.constants import BAND_DEFAULTS, SESSION_MODES, STRATEGY_TRIAL_MIX, TRANSFER_DISTANCES
from ..domain.models import Activity, DailySessionPlan


def build_daily_plan(band: str, *, session_mode: str = "default") -> DailySessionPlan:
    """Build one or two coherent blocks totaling exactly 20 minutes."""
    if band not in BAND_DEFAULTS:
        raise ValueError(f"Unknown instructional band: {band}")
    if session_mode not in SESSION_MODES:
        raise ValueError(f"Unknown session mode: {session_mode}")
    default = BAND_DEFAULTS[band]
    purposes = {
        "retrieval_check": ("Retrieve one prior method before seeing help.", "State the method and one cue that selects it.", "Stop after one clean retrieval or record the missing cue."),
        "worked_example": ("Make the reasoning visible with a worked example.", "Explain why the correct option is defensible.", "Fade one support prompt after the example."),
        "blocked_practice": ("Practice one weak skill with low variation.", "Complete the target procedure with evidence.", "Exit when the procedure is explainable, not merely correct."),
        "delayed_review": ("Revisit a prior event after a delay.", "Recover the rule without copying the prior explanation.", "Stop after retrieval plus a short confidence rating."),
        "targeted_practice": ("Reduce a named error signature.", "Meet the item-level success criterion and name the error guardrail.", "Stop when the targeted evidence is recorded."),
        "transfer_check": ("Test the idea on a changed surface form.", "Transfer the method without the original cue.", "Escalate to a smaller scaffold if transfer fails."),
        "interleaved_practice": ("Discriminate among nearby question types.", "Choose the method and justify the choice before solving.", "Stop when method selection is explicit."),
        "strategy_lab": ("Trial a strategy under a defined condition.", "Record accuracy, time, confidence, and downside.", "Do not conclude from one item."),
        "reflection": ("Update the learner model and next review.", "Name one observed fact and one uncertainty.", "Exit with a next action or an explicit insufficient-evidence state."),
        "calibration_check": ("Compare confidence with evidence quality.", "Predict outcome before answer reveal.", "Record calibration gap rather than a score judgment."),
        "near_miss_review": ("Study correct-but-uncertain, slow, or changed answers.", "Identify what made the answer fragile.", "Select one guardrail for the next item."),
        "timed_precision_cluster": ("Test precision under realistic time pressure.", "Maintain evidence threshold without rushing.", "Stop at the planned time and record the time-trigger condition."),
        "guided_practice_block": ("Build and apply one foundational method without context switching.", "Explain the method, use it on a short blocked set, and attempt one transfer item.", "Stop at 18 minutes or after the transfer attempt is recorded."),
        "targeted_practice_block": ("Improve one named procedure through a coherent practice run.", "Retrieve the rule, solve a short targeted set, and inspect the strongest distractor.", "Stop at 18 minutes or when the named mechanism has usable evidence."),
        "interleaved_transfer_block": ("Discriminate among nearby methods under changed surface forms.", "Choose and justify each method before solving a short interleaved set.", "Stop at 18 minutes or when the transfer evidence is recorded."),
        "timed_precision_block": ("Reduce high-score variance in one realistic uninterrupted run.", "Record confidence, timing, changes, and near-misses within the same timed set.", "Stop at 17 minutes even if an item remains unfinished."),
        "review_reflection": ("Debrief the most informative response and set the next review.", "Name one observed fact, one uncertainty, and one next action.", "Stop when the three reflection fields are complete or time expires."),
        "focused_diagnostic_block": ("Collect focused diagnostic evidence without fragmenting the work period.", "Complete the calibrated near-miss and timed-precision items as one continuous block.", "Stop at 14 minutes and preserve omissions rather than extending time."),
        "strategy_reflection_block": ("Run a small strategy comparison and close the session coherently.", "Record both strategy observations, fatigue, and the three reflection fields.", "Stop at 6 minutes; keep the strategy result inconclusive when the sample is too small."),
    }
    activity_mix = STRATEGY_TRIAL_MIX if session_mode == "strategy_trial" else default.activity_mix
    activities = tuple(
        Activity(activity_type, minutes, *purposes[activity_type])
        for activity_type, minutes in activity_mix
    )
    total = sum(activity.minutes for activity in activities)
    if total != 20:
        raise AssertionError(f"Daily plan must total 20 minutes, got {total}")
    return DailySessionPlan(
        band=band,
        planned_minutes=total,
        activities=activities,
        rationale=f"{default.support} Delivered as {len(activities)} coherent block(s); micro-activities are embedded rather than separately scheduled.",
    )


def choose_transfer_distance(*, new_skill: bool, recurrence_count: int, help_used: bool) -> str:
    """Select near/mid/far transfer from evidence, not from a fixed sequence."""
    if new_skill or recurrence_count <= 1 or help_used:
        return "near"
    if recurrence_count <= 3:
        return "mid"
    return "far"


def next_review_date(
    *,
    today: date | None = None,
    prior_success: bool,
    confidence: int | None,
    days_since_exposure: int,
    similarity: float,
    help_used: bool,
    timed: bool,
    recurrence_count: int,
    test_date: date | None = None,
) -> date:
    """Return a review date using several evidence signals.

    This is a transparent heuristic. It is deliberately not presented as a
    universal memory curve or a score predictor.
    """
    today = today or date.today()
    confidence = 3 if confidence is None else max(1, min(5, confidence))
    base = 2 if not prior_success else 5
    base += max(0, confidence - 3)
    base -= 2 if help_used else 0
    base -= 1 if timed and not prior_success else 0
    base -= min(2, max(0, recurrence_count - 1))
    base += 1 if days_since_exposure >= 7 and prior_success else 0
    base -= 1 if similarity >= 0.8 else 0
    days = max(1, min(28, base))
    candidate = today + timedelta(days=days)
    if test_date is not None:
        candidate = min(candidate, test_date - timedelta(days=1))
        if candidate < today:
            candidate = today
    return candidate
