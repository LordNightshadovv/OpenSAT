"""Named error signatures and conservative status transitions."""

from __future__ import annotations

from ..domain.constants import DIAGNOSIS_STATUSES, ERROR_SIGNATURES


ALLOWED_TRANSITIONS = {
    "provisional": {"provisional", "supported", "rejected"},
    "supported": {"supported", "confirmed", "rejected"},
    "confirmed": {"confirmed", "rejected"},
    "rejected": {"rejected", "provisional"},
}


def validate_signature(code: str) -> None:
    if code not in ERROR_SIGNATURES:
        raise ValueError(f"Unknown error signature: {code}")
    if code == "careless":
        raise ValueError("Use an observable mechanism; 'careless' is not a terminal diagnosis")


def validate_status(status: str) -> None:
    if status not in DIAGNOSIS_STATUSES:
        raise ValueError(f"Unknown diagnosis status: {status}")


def validate_transition(previous: str, requested: str) -> None:
    validate_status(previous)
    validate_status(requested)
    if requested not in ALLOWED_TRANSITIONS[previous]:
        raise ValueError(f"Invalid diagnostic transition: {previous} -> {requested}")


def minimal_autopsy_prompts(*, result: str, confidence: int | None, time_seconds: float | None, answer_changed: bool) -> list[str]:
    """Return the smallest high-value prompt set for current uncertainty."""
    prompts = ["what_did_you_think_the_question_was_asking"]
    if result in {"incorrect", "omitted"}:
        prompts.append("what_evidence_or_grammatical_structure_did_you_use")
    if confidence is None or confidence <= 2:
        prompts.append("how_confident_were_you_before_seeing_the_answer")
    if answer_changed:
        prompts.append("what_evidence_caused_the_answer_change")
    if time_seconds is not None and time_seconds >= 90:
        prompts.append("did_time_pressure_or_rereading_affect_the_decision")
    return prompts[:4]
