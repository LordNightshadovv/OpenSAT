"""Provider-neutral candidate-item gates; no official content is copied."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..domain.constants import SIMULATED_LABEL
from ..privacy.redaction import ensure_safe_metadata


@dataclass(frozen=True)
class ItemSpecification:
    domain: str
    skill: str
    question_type: str
    stem_family: str
    score_band: str
    difficulty: str
    cognitive_operation: str
    target_error_signature: str | None
    stimulus_constraints: dict[str, Any]
    correct_answer_rationale: str
    distractor_mechanisms: list[str]
    difficulty_mechanisms: list[str]
    style_reference_ids: list[str]
    timing_expectation_seconds: int
    transfer_distance: str

    def as_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


def validate_candidate(candidate: dict[str, Any], specification: ItemSpecification) -> dict[str, Any]:
    """Require explicit validation evidence before an item can be approved."""
    ensure_safe_metadata(candidate)
    if not specification.question_type.strip() or not specification.stem_family.strip():
        raise ValueError("Reading and Writing candidates need a question type and public stem family")
    if not specification.difficulty_mechanisms:
        raise ValueError("State at least one substantive difficulty mechanism")
    if not specification.style_reference_ids:
        raise ValueError("State at least one public style-reference identifier")
    required = {
        "options",
        "proposed_key",
        "independent_solution",
        "option_defensibility",
        "shortcut_check",
        "wording_check",
        "difficulty_check",
        "college_board_style_check",
        "difficulty_mechanism_check",
        "originality_check",
    }
    if specification.skill == "rhetorical_synthesis":
        required.add("rhetorical_synthesis_scenario_check")
    missing = sorted(required.difference(candidate))
    if missing:
        raise ValueError(f"Candidate is missing validation stages: {', '.join(missing)}")
    options = candidate["options"]
    defensibility = candidate["option_defensibility"]
    if not isinstance(options, list) or len(options) != 4:
        raise ValueError("Synthetic SAT-style candidate must contain four options")
    if not isinstance(defensibility, dict) or len(defensibility) != 4:
        raise ValueError("Inspect every distractor before approval")
    if candidate.get("proposed_key") not in {"A", "B", "C", "D"}:
        raise ValueError("proposed_key must be A, B, C, or D")
    checks = [candidate[key] for key in required if key.endswith("_check") or key == "originality_check"]
    if not all(check is True for check in checks):
        return {"status": "needs_revision", "simulated_label": SIMULATED_LABEL, "specification": specification.as_dict()}
    return {
        "status": "approved",
        "simulated_label": SIMULATED_LABEL,
        "specification": specification.as_dict(),
        "proposed_key": candidate["proposed_key"],
    }


def validate_purpose_groups(
    groups: list[dict[str, Any]],
    *,
    minimum_groups: int = 1,
    maximum_groups: int = 4,
    maximum_questions_per_group: int = 4,
) -> dict[str, Any]:
    """Validate UI grouping without turning presentation labels into activities."""
    limits = (minimum_groups, maximum_groups, maximum_questions_per_group)
    if not all(isinstance(value, int) and not isinstance(value, bool) for value in limits):
        raise ValueError("Purpose-group limits must be integers")
    if not 1 <= minimum_groups <= maximum_groups <= 4:
        raise ValueError("Purpose-group count must stay between one and four")
    if not 1 <= maximum_questions_per_group <= 4:
        raise ValueError("A purpose group must contain fewer than five questions")
    if not isinstance(groups, list) or not minimum_groups <= len(groups) <= maximum_groups:
        raise ValueError(f"Expected {minimum_groups} to {maximum_groups} purpose groups")
    seen: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for index, group in enumerate(groups):
        if not isinstance(group, dict):
            raise ValueError(f"Purpose group {index + 1} must be an object")
        purpose = group.get("purpose")
        item_ids = group.get("item_ids")
        if not isinstance(purpose, str) or not purpose.strip():
            raise ValueError(f"Purpose group {index + 1} needs a shared purpose")
        if not isinstance(item_ids, list) or not 1 <= len(item_ids) <= maximum_questions_per_group:
            raise ValueError(f"Purpose group {index + 1} must contain one to {maximum_questions_per_group} item ids")
        if any(not isinstance(item_id, str) or not item_id.strip() for item_id in item_ids):
            raise ValueError(f"Purpose group {index + 1} contains an invalid item id")
        duplicates = seen.intersection(item_ids)
        if duplicates:
            raise ValueError(f"Item ids cannot appear in multiple purpose groups: {', '.join(sorted(duplicates))}")
        seen.update(item_ids)
        normalized.append({"purpose": purpose.strip(), "item_ids": list(item_ids)})
    return {
        "groups": normalized,
        "group_count": len(normalized),
        "question_count": len(seen),
        "presentation_only": True,
    }
