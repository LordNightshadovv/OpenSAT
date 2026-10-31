"""Validate content-free Visualize submissions before OpenSAT persistence."""

from __future__ import annotations

from typing import Any

from ..privacy.redaction import ensure_safe_metadata
from ..domain.constants import APPARENT_DIFFICULTY_TAGS, PROVENANCE_TYPES


SUPPORTED_SCHEMA_VERSIONS = ("1.0", "1.1", "1.2")
SURFACE = "visualize"
SECTIONS = ("diagnostic_core", "strategy_and_reflection")
ANSWER_ALPHABET = ("A", "B", "C", "D")
FATIGUE_LEVELS = (None, "low", "moderate", "high")
REQUIRED_KEYS = {
    "schema_version",
    "surface",
    "manifest_id",
    "session_id",
    "submission_id",
    "section",
    "answers",
    "actual_minutes",
    "fatigue",
    "reflection",
}
LEGACY_ANSWER_KEYS = {
    "item_id",
    "selected_answer",
    "confidence",
    "time_seconds",
    "answer_changed",
    "almost_choice",
    "help_used",
}
TIMED_ANSWER_KEYS = LEGACY_ANSWER_KEYS | {"timing_source", "timer_state"}
CALIBRATED_ANSWER_KEYS = TIMED_ANSWER_KEYS | {"apparent_difficulty"}
REFLECTION_KEYS = {"observed_fact", "uncertainty", "next_review"}
MANIFEST_ITEM_REQUIRED_KEYS = {
    "correct_answer",
    "provider",
    "target_skill",
    "intended_difficulty",
    "validation_status",
    "item_version",
}
DIRECT_SOURCE_LABELS = {
    "official": "Official College Board question",
    "licensed": "Licensed source question",
    "publisher_reconstruction": "Publisher-reconstructed past-paper question",
}


def _exact_keys(value: dict[str, Any], expected: set[str], label: str) -> None:
    missing = expected - set(value)
    extra = set(value) - expected
    if missing or extra:
        raise ValueError(f"{label} keys mismatch; missing={sorted(missing)}, extra={sorted(extra)}")


def _bounded_text(value: Any, label: str, maximum: int = 1000) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a string")
    text = value.strip()
    if not text or len(text) > maximum:
        raise ValueError(f"{label} must contain 1-{maximum} characters")
    return text


def validate_visual_submission(
    payload: dict[str, Any],
    *,
    learner_id: str,
    session_state: dict[str, Any],
    manifest: dict[str, Any],
) -> dict[str, Any]:
    """Return a validated content-free payload plus manifest-resolved metadata.

    The transient manifest owns answer keys and diagnostic metadata. It must not
    contain passages, question text, or answer choices and is never persisted as
    part of the learner response.
    """

    if not isinstance(payload, dict) or not isinstance(manifest, dict):
        raise ValueError("payload and manifest must be objects")
    ensure_safe_metadata(payload, "visual_submission")
    ensure_safe_metadata(manifest, "diagnostic_manifest")
    _exact_keys(payload, REQUIRED_KEYS, "submission")

    schema_version = payload["schema_version"]
    if schema_version not in SUPPORTED_SCHEMA_VERSIONS or payload["surface"] != SURFACE:
        raise ValueError("unsupported Visualize submission contract")
    if manifest.get("learner_id") != learner_id or session_state.get("learner_id") != learner_id:
        raise ValueError("learner ownership mismatch")
    if payload["manifest_id"] != manifest.get("manifest_id"):
        raise ValueError("manifest_id mismatch")
    if payload["session_id"] != manifest.get("session_id") or payload["session_id"] != session_state.get("session_id"):
        raise ValueError("session_id mismatch")

    section = payload["section"]
    if section not in SECTIONS:
        raise ValueError("unknown submission section")
    if payload["submission_id"] != f"{payload['session_id']}:{section}":
        raise ValueError("submission_id must be the stable session-and-section key")

    sections = manifest.get("sections")
    items = manifest.get("items")
    if not isinstance(sections, dict) or not isinstance(items, dict):
        raise ValueError("manifest must define sections and items")
    expected_ids = sections.get(section)
    if not isinstance(expected_ids, list) or not expected_ids:
        raise ValueError("manifest section is unavailable")

    answers = payload["answers"]
    if not isinstance(answers, list):
        raise ValueError("answers must be an array")
    submitted_ids: list[str] = []
    resolved: list[dict[str, Any]] = []
    for index, answer in enumerate(answers):
        if not isinstance(answer, dict):
            raise ValueError(f"answers[{index}] must be an object")
        if schema_version == "1.2":
            expected_answer_keys = CALIBRATED_ANSWER_KEYS
        elif schema_version == "1.1":
            expected_answer_keys = TIMED_ANSWER_KEYS
        else:
            expected_answer_keys = LEGACY_ANSWER_KEYS
        _exact_keys(answer, expected_answer_keys, f"answers[{index}]")
        item_id = answer["item_id"]
        if not isinstance(item_id, str) or item_id not in items:
            raise ValueError(f"answers[{index}].item_id is not in the manifest")
        if item_id in submitted_ids:
            raise ValueError("duplicate item_id")
        submitted_ids.append(item_id)
        selected = answer["selected_answer"]
        almost = answer["almost_choice"]
        if selected is not None and selected not in ANSWER_ALPHABET:
            raise ValueError("selected_answer must be A-D or null")
        if almost is not None and almost not in ANSWER_ALPHABET:
            raise ValueError("almost_choice must be A-D or null")
        confidence = answer["confidence"]
        if isinstance(confidence, bool) or not isinstance(confidence, int) or not 1 <= confidence <= 5:
            raise ValueError("confidence must be an integer from 1 to 5")
        seconds = answer["time_seconds"]
        minimum_seconds = 0 if schema_version == "1.0" else 0.001
        if isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or not minimum_seconds <= seconds <= 3600:
            raise ValueError(f"time_seconds must be between {minimum_seconds} and 3600")
        if schema_version in {"1.1", "1.2"}:
            if answer["timing_source"] != "visualize_monotonic_timer":
                raise ValueError("timed schema timing_source must be visualize_monotonic_timer")
            if answer["timer_state"] != "stopped":
                raise ValueError("timed schemas require each question timer to be stopped before submission")
        if schema_version == "1.2" and answer["apparent_difficulty"] not in APPARENT_DIFFICULTY_TAGS:
            raise ValueError(f"apparent_difficulty must be one of {APPARENT_DIFFICULTY_TAGS}")
        if not isinstance(answer["answer_changed"], bool) or not isinstance(answer["help_used"], bool):
            raise ValueError("answer_changed and help_used must be booleans")
        metadata = items[item_id]
        if not isinstance(metadata, dict) or metadata.get("correct_answer") not in ANSWER_ALPHABET:
            raise ValueError("manifest item metadata is incomplete")
        if not MANIFEST_ITEM_REQUIRED_KEYS.issubset(metadata):
            raise ValueError("manifest item metadata is incomplete")
        for key in ("provider", "target_skill", "intended_difficulty", "item_version"):
            if not isinstance(metadata[key], str) or not metadata[key].strip():
                raise ValueError(f"manifest item {key} must be a non-empty string")
        provenance_type = metadata.get("provenance_type", "simulated")
        if provenance_type not in PROVENANCE_TYPES:
            raise ValueError(f"manifest item provenance_type must be one of {PROVENANCE_TYPES}")
        if provenance_type == "simulated":
            if metadata["validation_status"] != "approved":
                raise ValueError("only approved simulated items may be persisted")
        else:
            if metadata["validation_status"] != "reviewed":
                raise ValueError("direct source items must be visually reviewed")
            source_locator = metadata.get("source_locator")
            if not isinstance(source_locator, str) or not source_locator.strip():
                raise ValueError("direct source items require a non-empty source_locator")
            if metadata.get("source_label") != DIRECT_SOURCE_LABELS[provenance_type]:
                raise ValueError("direct source label must match provenance_type")
        if metadata.get("strategy_condition") not in {None, "A", "B"}:
            raise ValueError("strategy_condition must be A, B, or null")
        slow_threshold = metadata.get("slow_threshold_seconds")
        if slow_threshold is not None and (
            isinstance(slow_threshold, bool)
            or not isinstance(slow_threshold, (int, float))
            or slow_threshold <= 0
        ):
            raise ValueError("slow_threshold_seconds must be positive when present")
        resolved.append({"item_id": item_id, **metadata})

    if submitted_ids != expected_ids:
        raise ValueError("submitted item scope or order does not match the manifest section")
    minutes = payload["actual_minutes"]
    if isinstance(minutes, bool) or not isinstance(minutes, int) or not 0 <= minutes <= 20:
        raise ValueError("actual_minutes must be an integer from 0 to 20")
    if payload["fatigue"] not in FATIGUE_LEVELS:
        raise ValueError("fatigue must be low, moderate, high, or null")

    reflection = payload["reflection"]
    if section == "diagnostic_core":
        if reflection is not None:
            raise ValueError("diagnostic_core reflection must be null")
    elif reflection is not None:
        if not isinstance(reflection, dict):
            raise ValueError("reflection must be an object or null")
        _exact_keys(reflection, REFLECTION_KEYS, "reflection")
        payload["reflection"] = {
            key: _bounded_text(reflection[key], f"reflection.{key}")
            for key in sorted(REFLECTION_KEYS)
        }

    return {
        "payload": payload,
        "resolved_items": resolved,
        "idempotency_key": payload["submission_id"],
        "status": "validated_not_persisted",
    }
