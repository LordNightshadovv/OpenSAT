"""Transparent difficulty recommendations for future OpenSAT practice.

The policy combines the learner's score-band prior with recent correctness,
timing, confidence, answer stability, and help use. It never treats a single
fast block as proof of mastery or a single miss as a confirmed weakness.
"""

from __future__ import annotations

from collections import Counter
from statistics import median
from typing import Any, Iterable


DIFFICULTY_TIERS = ("foundation", "medium", "upper-medium", "hard", "challenge")
BAND_BASE_TIER = {
    "600-640": "foundation",
    "650-690": "medium",
    "700-740": "upper-medium",
    "750-800": "hard",
}
BAND_FLOOR_TIER = {
    "600-640": "foundation",
    "650-690": "foundation",
    "700-740": "medium",
    "750-800": "upper-medium",
}
CORRECT_RESULTS = {"correct", "correct_uncertain", "correct_slow", "correct_changed"}
FRAGILE_RESULTS = {"correct_uncertain", "correct_slow", "correct_changed"}
DEFAULT_SLOW_THRESHOLD_SECONDS = 60.0


def _tier_index(tier: str) -> int:
    try:
        return DIFFICULTY_TIERS.index(tier)
    except ValueError:
        return DIFFICULTY_TIERS.index("medium")


def _shift(tier: str, amount: int, floor: str) -> str:
    index = max(_tier_index(floor), min(len(DIFFICULTY_TIERS) - 1, _tier_index(tier) + amount))
    return DIFFICULTY_TIERS[index]


def _context(event: dict[str, Any]) -> dict[str, Any]:
    value = event.get("abstract_context")
    return value if isinstance(value, dict) else {}


def _positive_number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        return None
    return float(value)


def recommend_practice_difficulty(
    band: str,
    events: Iterable[dict[str, Any]],
    *,
    minimum_observations: int = 4,
    skill_stages: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Recommend a future item mix from a band prior and recent evidence.

    `target_tier` is the centre of the next practice mix; `stretch_tier` and
    `stretch_share` let a generator increase challenge without turning one
    strong block into a brittle all-or-nothing level jump.
    """

    if band not in BAND_BASE_TIER:
        raise ValueError(f"Unknown instructional band: {band}")
    recent = list(events)
    skill_stages = skill_stages or {}
    base = BAND_BASE_TIER[band]
    floor = BAND_FLOOR_TIER[band]
    if not recent:
        return {
            "policy_version": "1.0",
            "band_prior": band,
            "band_base_tier": base,
            "target_tier": base,
            "stretch_tier": _shift(base, 1, floor),
            "stretch_share": 0.25,
            "evidence_status": "band_prior_only",
            "observation_count": 0,
            "accuracy_rate": None,
            "median_time_seconds": None,
            "median_pace_ratio": None,
            "high_confidence_misses": 0,
            "fragile_correct_count": 0,
            "priority_skills": [],
            "skill_stage_evidence": skill_stages,
            "skill_overrides": {},
            "selection_directive": "Start from the learner's band prior and collect calibrated timing evidence before changing level.",
            "caveat": "This is a practice-selection heuristic, not an official score prediction.",
        }

    correct_count = sum(event.get("result") in CORRECT_RESULTS for event in recent)
    accuracy = correct_count / len(recent)
    high_confidence_misses = sum(
        event.get("result") in {"incorrect", "omitted"}
        and isinstance(event.get("confidence"), int)
        and event["confidence"] >= 4
        for event in recent
    )
    fragile_correct_count = sum(event.get("result") in FRAGILE_RESULTS for event in recent)
    help_count = sum(bool(_context(event).get("help_used")) for event in recent)
    changed_count = sum(bool(event.get("answer_changed")) for event in recent)

    times: list[float] = []
    pace_ratios: list[float] = []
    used_manifest_threshold = False
    for event in recent:
        seconds = _positive_number(event.get("time_seconds"))
        if seconds is None:
            continue
        times.append(seconds)
        threshold = _positive_number(_context(event).get("slow_threshold_seconds"))
        if threshold is None:
            threshold = DEFAULT_SLOW_THRESHOLD_SECONDS
        else:
            used_manifest_threshold = True
        pace_ratios.append(seconds / threshold)

    median_seconds = round(median(times), 1) if times else None
    median_pace_ratio = round(median(pace_ratios), 3) if pace_ratios else None
    sufficiently_observed = len(recent) >= minimum_observations
    fast_enough = median_pace_ratio is not None and median_pace_ratio <= 0.85
    slow_pattern = median_pace_ratio is not None and median_pace_ratio > 1.15

    incorrect_skills = Counter(
        str(event.get("provisional_skill"))
        for event in recent
        if event.get("result") in {"incorrect", "omitted"} and event.get("provisional_skill")
    )
    priority_skills = [skill for skill, _ in incorrect_skills.most_common(3)]
    skill_overrides = {
        skill: {
            "stage": skill_stages.get(skill, "unmeasured"),
            "transfer": (
                "near_scaffolded"
                if skill_stages.get(skill) in {"recognize", "explain"}
                else "near_calibration"
            ),
        }
        for skill in priority_skills
    }

    target = base
    stretch_share = 0.25
    evidence_status = "insufficient_recent_evidence"
    directive = "Hold the band-based level while collecting more correctness, timing, and calibration evidence."

    if sufficiently_observed:
        if accuracy >= 0.85 and fast_enough and high_confidence_misses == 0 and help_count == 0:
            target = _shift(base, 1, floor)
            stretch_share = 0.35
            evidence_status = "ready_for_level_increase"
            directive = "Raise the centre difficulty one tier and retain a smaller same-skill transfer check for calibration."
        elif accuracy >= 0.80 and fast_enough:
            target = base
            stretch_share = 0.50
            evidence_status = "increase_challenge_mix_with_calibration"
            directive = "Use harder distractors and more challenge items, plus a near-transfer check for each high-confidence miss; do not label one miss a confirmed weakness."
        elif accuracy < 0.60 or (accuracy < 0.75 and (slow_pattern or help_count >= 2)):
            target = _shift(base, -1, floor)
            stretch_share = 0.10
            evidence_status = "temporary_scaffold"
            directive = "Temporarily reduce one tier, model the procedure, and recheck near transfer before restoring difficulty."
        else:
            target = base
            stretch_share = 0.25
            evidence_status = "hold_and_target"
            directive = "Keep the current centre difficulty and target recurring fragile or incorrect skills with near transfer."

    return {
        "policy_version": "1.0",
        "band_prior": band,
        "band_base_tier": base,
        "target_tier": target,
        "stretch_tier": _shift(target, 1, floor),
        "stretch_share": stretch_share,
        "evidence_status": evidence_status,
        "observation_count": len(recent),
        "accuracy_rate": round(accuracy, 3),
        "median_time_seconds": median_seconds,
        "median_pace_ratio": median_pace_ratio,
        "pace_reference": "manifest_item_thresholds" if used_manifest_threshold else "60_second_internal_heuristic",
        "high_confidence_misses": high_confidence_misses,
        "fragile_correct_count": fragile_correct_count,
        "help_used_count": help_count,
        "answer_changed_count": changed_count,
        "priority_skills": priority_skills,
        "skill_stage_evidence": skill_stages,
        "skill_overrides": skill_overrides,
        "selection_directive": directive,
        "caveat": "This is a practice-selection heuristic, not an official score prediction.",
    }
