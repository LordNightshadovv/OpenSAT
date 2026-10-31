"""Application service for the first local vertical slice.

The service owns validation and persistence boundaries so the MCP server, CLI,
and future browser adapter cannot silently create a second learner model.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from hashlib import sha256
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

from ..adaptation import recommend_practice_difficulty
from ..diagnosis.taxonomy import validate_signature, validate_status, validate_transition
from ..domain.constants import (
    APPARENT_DIFFICULTY_TAGS,
    ASSESSMENT_SOURCES,
    DIAGNOSIS_STATUSES,
    ERROR_SIGNATURES,
    EXPLANATION_MODES,
    LANGUAGES,
    PILOT_BANDS,
    PROVENANCE_TYPES,
    QUESTION_RESULTS,
    SIMULATED_LABEL,
    SKILL_STAGES,
    TRANSFER_DISTANCES,
    band_for_score,
)
from ..privacy.paths import DataPaths, ensure_data_layout
from ..privacy.redaction import dumps_safe, ensure_safe_metadata, load_json_object
from ..scheduling.engine import build_daily_plan, choose_transfer_distance, next_review_date
from ..scheduling.on_demand import recommend_on_demand_sessions
from ..storage.database import connect, utc_now
from ..visualize import validate_visual_submission


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _json(value: Any) -> str:
    return dumps_safe(value)


_PREVIEW_FORBIDDEN_KEYS = {
    "visibletext",
    "pagetext",
    "rawtext",
    "transienttext",
    "pagetitle",
    "questionbody",
    "passage",
    "choices",
    "rationale",
}


def _ensure_preview_metadata(value: Any, path: str = "preview") -> None:
    """Reject browser-content-shaped fields at the low-level import boundary."""

    ensure_safe_metadata(value, path)
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = "".join(character.lower() for character in str(key) if character.isalnum())
            if normalized in _PREVIEW_FORBIDDEN_KEYS:
                raise ValueError(f"Prohibited transient page field at {path}.{key}")
            _ensure_preview_metadata(child, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _ensure_preview_metadata(child, f"{path}[{index}]")


def _decode(value: str | None, default: Any) -> Any:
    if value is None:
        return default
    return json.loads(value)


def _row(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    result = dict(row)
    for key in list(result):
        if key.endswith("_json"):
            result[key[:-5]] = _decode(result.pop(key), {})
    for key in ("is_official", "flagged", "answer_changed", "completed"):
        if key in result:
            result[key] = bool(result[key])
    return result


def _rows(rows: Iterable[sqlite3.Row]) -> list[dict[str, Any]]:
    return [_row(row) for row in rows if row is not None]


def _require_int(value: Any, name: str, minimum: int, maximum: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or not minimum <= value <= maximum:
        raise ValueError(f"{name} must be an integer between {minimum} and {maximum}")
    return value


def _require_learner(connection: sqlite3.Connection, learner_id: str) -> None:
    if connection.execute("SELECT 1 FROM learners WHERE learner_id = ?", (learner_id,)).fetchone() is None:
        raise ValueError(f"Unknown learner: {learner_id}")


class LabService:
    """Validated application operations used by all supported surfaces."""

    def __init__(
        self,
        data_dir: str | Path | None = None,
        *,
        clock: Callable[[], datetime] | None = None,
    ):
        self.data_dir = Path(data_dir).expanduser().resolve() if data_dir else None
        self._clock = clock or (lambda: datetime.now().astimezone())

    def _open(self) -> tuple[sqlite3.Connection, DataPaths]:
        return connect(self.data_dir)

    def get_capabilities(self) -> dict[str, Any]:
        paths = ensure_data_layout(self.data_dir)
        return {
            "mode": "full_local",
            "local_storage": True,
            "sqlite": True,
            "manual_score_import": True,
            "manual_mistake_autopsy": True,
            "learner_model_export": True,
            "learner_model_import": True,
            "explicit_delete": True,
            "adaptive_practice_difficulty": "band_correctness_time_confidence_apparent_difficulty_and_stability",
            "apparent_difficulty_tag": "post_answer_pre_feedback_routine_noticeable_intimidating",
            "session_start_clock": "system_local_date_time_with_due_review_gate",
            "visualize_question_timers": "schema_1_2_timer_and_apparent_difficulty_required_for_new_surfaces",
            "signed_in_chrome_inspection": False,
            "browser_practice_scan": "read_only_adapter_ready_requires_authorized_bridge",
            "chrome_read_only_adapter": {
                "implemented": True,
                "user_authorization_required": True,
                "browser_mutations": False,
                "prompt_injection_response": "stop_and_discard",
                "transient_content_deleted": True,
            },
            "live_gemini": False,
            "runtime_data_directory": str(paths.root),
            "official_score_prediction_from_simulated_items": False,
        }

    def initialize_learner(
        self,
        *,
        preferred_language: str,
        explanation_mode: str | None = None,
        learner_id: str | None = None,
        reading_writing_score: int | None = None,
        math_score: int | None = None,
        total_score: int | None = None,
        score_context: dict[str, Any] | None = None,
        test_date: str | None = None,
        accessibility_preferences: dict[str, Any] | None = None,
        session_length_preference: int = 20,
    ) -> dict[str, Any]:
        if preferred_language not in LANGUAGES:
            raise ValueError(f"preferred_language must be one of {LANGUAGES}")
        explanation_mode = explanation_mode or preferred_language
        if explanation_mode not in EXPLANATION_MODES:
            raise ValueError(f"explanation_mode must be one of {EXPLANATION_MODES}")
        if not isinstance(session_length_preference, int) or session_length_preference <= 0:
            raise ValueError("session_length_preference must be a positive integer")
        if reading_writing_score is not None:
            _require_int(reading_writing_score, "reading_writing_score", 200, 800)
        if math_score is not None:
            _require_int(math_score, "math_score", 200, 800)
        if total_score is not None:
            _require_int(total_score, "total_score", 400, 1600)
        score_context = dict(score_context or {})
        score_context.update(
            {
                "reading_writing_score": reading_writing_score,
                "math_score": math_score,
                "total_score": total_score,
            }
        )
        ensure_safe_metadata(score_context)
        accessibility_preferences = dict(accessibility_preferences or {})
        ensure_safe_metadata(accessibility_preferences)
        score_for_band = reading_writing_score or total_score
        band = band_for_score(score_for_band)
        learner_id = learner_id or _id("learner")
        now = utc_now()
        connection, _ = self._open()
        try:
            existing = connection.execute("SELECT * FROM learners WHERE learner_id = ?", (learner_id,)).fetchone()
            if existing:
                return {"created": False, "learner": _row(existing)}
            connection.execute(
                """INSERT INTO learners
                (learner_id, preferred_language, explanation_mode, score_context_json,
                 score_band_prior, test_date, accessibility_preferences_json,
                 session_length_preference, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    learner_id,
                    preferred_language,
                    explanation_mode,
                    _json(score_context),
                    band,
                    test_date,
                    _json(accessibility_preferences),
                    session_length_preference,
                    now,
                    now,
                ),
            )
            connection.commit()
            return {"created": True, "learner": self._get_learner(connection, learner_id)}
        finally:
            connection.close()

    def _get_learner(self, connection: sqlite3.Connection, learner_id: str) -> dict[str, Any]:
        result = _row(connection.execute("SELECT * FROM learners WHERE learner_id = ?", (learner_id,)).fetchone())
        if result is None:
            raise ValueError(f"Unknown learner: {learner_id}")
        result["user_band_label"] = {
            "600-640": "600–650",
            "650-690": "650–700",
            "700-740": "700–750",
            "750-800": "750–800",
        }[result["score_band_prior"]]
        return result

    def get_learner_profile(self, learner_id: str) -> dict[str, Any]:
        connection, _ = self._open()
        try:
            return self._get_learner(connection, learner_id)
        finally:
            connection.close()

    def update_learner_preferences(
        self,
        *,
        learner_id: str,
        practice_preferences: dict[str, Any] | None = None,
        test_date: str | None = None,
        session_length_preference: int | None = None,
    ) -> dict[str, Any]:
        """Merge durable practice preferences into an existing learner profile."""
        if practice_preferences is None and test_date is None and session_length_preference is None:
            raise ValueError("Provide at least one learner preference to update")
        if test_date is not None:
            try:
                date.fromisoformat(test_date)
            except ValueError as exc:
                raise ValueError("test_date must use YYYY-MM-DD") from exc
        if session_length_preference is not None:
            _require_int(session_length_preference, "session_length_preference", 1, 30)
        if practice_preferences is not None:
            practice_preferences = dict(practice_preferences)
            ensure_safe_metadata(practice_preferences)
            grouping = practice_preferences.get("purpose_groups")
            if grouping is not None:
                if not isinstance(grouping, dict):
                    raise ValueError("purpose_groups must be an object")
                minimum = grouping.get("preferred_min", 1)
                maximum = grouping.get("preferred_max", 4)
                per_group = grouping.get("max_questions_per_group", 4)
                limits = (minimum, maximum, per_group)
                if any(not isinstance(value, int) or isinstance(value, bool) for value in limits):
                    raise ValueError("purpose-group limits must be integers")
                if not 1 <= minimum <= maximum <= 4:
                    raise ValueError("preferred purpose-group count must stay between one and four")
                if not 1 <= per_group <= 4:
                    raise ValueError("max_questions_per_group must be less than five")
        connection, _ = self._open()
        try:
            profile = self._get_learner(connection, learner_id)
            accessibility = dict(profile.get("accessibility_preferences", {}))
            if practice_preferences is not None:
                current_practice = dict(accessibility.get("practice", {}))
                current_practice.update(practice_preferences)
                accessibility["practice"] = current_practice
            next_test_date = test_date if test_date is not None else profile.get("test_date")
            next_length = session_length_preference if session_length_preference is not None else profile["session_length_preference"]
            connection.execute(
                """UPDATE learners
                SET accessibility_preferences_json = ?, test_date = ?,
                    session_length_preference = ?, updated_at = ?
                WHERE learner_id = ?""",
                (_json(accessibility), next_test_date, next_length, utc_now(), learner_id),
            )
            connection.commit()
            return {"updated": True, "learner": self._get_learner(connection, learner_id)}
        finally:
            connection.close()

    def record_assessment(
        self,
        *,
        learner_id: str,
        source: str,
        assessment_type: str,
        external_id: str,
        taken_at: str | None = None,
        is_official: bool,
        total_score: int | None = None,
        reading_writing_score: int | None = None,
        math_score: int | None = None,
        domain_evidence: dict[str, Any] | None = None,
        import_provenance: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if source not in ASSESSMENT_SOURCES:
            raise ValueError(f"source must be one of {ASSESSMENT_SOURCES}")
        if not external_id.strip():
            raise ValueError("external_id is required for idempotent assessment import")
        if total_score is not None:
            _require_int(total_score, "total_score", 400, 1600)
        if reading_writing_score is not None:
            _require_int(reading_writing_score, "reading_writing_score", 200, 800)
        if math_score is not None:
            _require_int(math_score, "math_score", 200, 800)
        domain_evidence = dict(domain_evidence or {})
        import_provenance = dict(import_provenance or {})
        ensure_safe_metadata(domain_evidence)
        ensure_safe_metadata(import_provenance)
        connection, _ = self._open()
        try:
            _require_learner(connection, learner_id)
            existing = connection.execute(
                "SELECT * FROM assessments WHERE learner_id = ? AND source = ? AND external_id = ?",
                (learner_id, source, external_id),
            ).fetchone()
            if existing:
                return {"created": False, "assessment": _row(existing)}
            assessment_id = _id("assessment")
            connection.execute(
                """INSERT INTO assessments
                (assessment_id, learner_id, source, assessment_type, external_id, taken_at,
                 is_official, total_score, reading_writing_score, math_score,
                 domain_evidence_json, import_provenance_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    assessment_id,
                    learner_id,
                    source,
                    assessment_type,
                    external_id,
                    taken_at,
                    int(is_official),
                    total_score,
                    reading_writing_score,
                    math_score,
                    _json(domain_evidence),
                    _json(import_provenance),
                    utc_now(),
                ),
            )
            if reading_writing_score is not None:
                connection.execute(
                    "UPDATE learners SET score_band_prior = ?, updated_at = ? WHERE learner_id = ?",
                    (band_for_score(reading_writing_score), utc_now(), learner_id),
                )
            connection.commit()
            return {
                "created": True,
                "assessment": _row(connection.execute("SELECT * FROM assessments WHERE assessment_id = ?", (assessment_id,)).fetchone()),
            }
        finally:
            connection.close()

    def list_assessments(self, learner_id: str) -> list[dict[str, Any]]:
        connection, _ = self._open()
        try:
            _require_learner(connection, learner_id)
            return _rows(connection.execute("SELECT * FROM assessments WHERE learner_id = ? ORDER BY taken_at, created_at", (learner_id,)).fetchall())
        finally:
            connection.close()

    def get_practice_import(self, learner_id: str, import_id: str) -> dict[str, Any]:
        """Read one import record without exposing browser page content."""

        connection, _ = self._open()
        try:
            row = connection.execute(
                "SELECT * FROM practice_imports WHERE import_id = ? AND learner_id = ?",
                (import_id, learner_id),
            ).fetchone()
            if row is None:
                raise ValueError("import_id must belong to learner_id")
            result = _row(row)
            if result is None:
                raise ValueError("practice import could not be read")
            _ensure_preview_metadata(result.get("preview", {}))
            return result
        finally:
            connection.close()

    def begin_practice_import(
        self,
        *,
        learner_id: str,
        source: str,
        external_id: str,
        preview: dict[str, Any],
        cursor: str | None = None,
    ) -> dict[str, Any]:
        if source not in {"bluebook", "college-board", "manual"}:
            raise ValueError("practice import source must be an authorized practice source")
        _ensure_preview_metadata(preview)
        connection, _ = self._open()
        try:
            _require_learner(connection, learner_id)
            existing = connection.execute(
                "SELECT * FROM practice_imports WHERE learner_id = ? AND source = ? AND external_id = ?",
                (learner_id, source, external_id),
            ).fetchone()
            if existing:
                return {"created": False, "import": _row(existing)}
            import_id = _id("import")
            now = utc_now()
            connection.execute(
                """INSERT INTO practice_imports
                (import_id, learner_id, source, external_id, cursor, status, preview_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, 'preview', ?, ?, ?)""",
                (import_id, learner_id, source, external_id, cursor, _json(preview), now, now),
            )
            connection.commit()
            return {"created": True, "import": _row(connection.execute("SELECT * FROM practice_imports WHERE import_id = ?", (import_id,)).fetchone())}
        finally:
            connection.close()

    def update_practice_import(
        self,
        *,
        learner_id: str,
        import_id: str,
        cursor: str | None,
        status: str,
        expected_cursor: str | None = None,
        preview: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if status not in {"preview", "running", "paused", "complete", "failed", "blocked"}:
            raise ValueError("invalid practice import status")
        if preview is not None:
            _ensure_preview_metadata(preview)
        connection, _ = self._open()
        try:
            row = connection.execute(
                "SELECT * FROM practice_imports WHERE import_id = ? AND learner_id = ?",
                (import_id, learner_id),
            ).fetchone()
            if row is None:
                raise ValueError("import_id must belong to learner_id")
            if expected_cursor is not None and row["cursor"] != expected_cursor:
                raise ValueError("practice import cursor is stale or mismatched")
            connection.execute(
                """UPDATE practice_imports SET cursor = ?, status = ?,
                preview_json = COALESCE(?, preview_json), updated_at = ?
                WHERE import_id = ?""",
                (cursor, status, _json(preview) if preview is not None else None, utc_now(), import_id),
            )
            connection.commit()
            return {"import_id": import_id, "status": status, "cursor": cursor}
        finally:
            connection.close()

    def discard_practice_import(self, learner_id: str, import_id: str, *, confirm: bool) -> dict[str, Any]:
        """Delete an uncommitted scan preview after explicit confirmation."""

        if confirm is not True:
            raise ValueError("explicit confirmation is required to discard a practice import")
        connection, _ = self._open()
        try:
            row = connection.execute(
                "SELECT status FROM practice_imports WHERE import_id = ? AND learner_id = ?",
                (import_id, learner_id),
            ).fetchone()
            if row is None:
                raise ValueError("import_id must belong to learner_id")
            if row["status"] == "complete":
                raise ValueError("completed practice imports cannot be discarded")
            connection.execute(
                "DELETE FROM practice_imports WHERE import_id = ? AND learner_id = ?",
                (import_id, learner_id),
            )
            connection.commit()
            return {"discarded": True, "import_id": import_id}
        finally:
            connection.close()

    def record_question_event(
        self,
        *,
        learner_id: str,
        assessment_id: str,
        event_key: str,
        section: str,
        question_locator: str,
        result: str,
        provenance_type: str,
        module: str | None = None,
        time_seconds: float | None = None,
        time_source: str | None = None,
        confidence: int | None = None,
        apparent_difficulty: str | None = None,
        flagged: bool = False,
        answer_changed: bool = False,
        selected_answer: str | None = None,
        correct_answer: str | None = None,
        provisional_skill: str | None = None,
        content_fingerprint: str | None = None,
        abstract_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if result not in QUESTION_RESULTS:
            raise ValueError(f"result must be one of {QUESTION_RESULTS}")
        if provenance_type not in PROVENANCE_TYPES:
            raise ValueError(f"provenance_type must be one of {PROVENANCE_TYPES}")
        if confidence is not None:
            _require_int(confidence, "confidence", 1, 5)
        if apparent_difficulty is not None and apparent_difficulty not in APPARENT_DIFFICULTY_TAGS:
            raise ValueError(f"apparent_difficulty must be one of {APPARENT_DIFFICULTY_TAGS}")
        if time_seconds is not None and (not isinstance(time_seconds, (int, float)) or time_seconds < 0):
            raise ValueError("time_seconds must be non-negative")
        abstract_context = dict(abstract_context or {})
        ensure_safe_metadata(abstract_context)
        connection, _ = self._open()
        try:
            _require_learner(connection, learner_id)
            assessment = connection.execute(
                "SELECT 1 FROM assessments WHERE assessment_id = ? AND learner_id = ?", (assessment_id, learner_id)
            ).fetchone()
            if assessment is None:
                raise ValueError("assessment_id must belong to learner_id")
            existing = connection.execute(
                "SELECT * FROM question_events WHERE learner_id = ? AND assessment_id = ? AND event_key = ?",
                (learner_id, assessment_id, event_key),
            ).fetchone()
            if existing:
                return {"created": False, "event": _row(existing)}
            event_id = _id("event")
            connection.execute(
                """INSERT INTO question_events
                (event_id, learner_id, assessment_id, event_key, section, module,
                 question_locator, result, time_seconds, time_source, confidence, flagged,
                 apparent_difficulty, answer_changed, selected_answer, correct_answer, provisional_skill,
                 provenance_type, content_fingerprint, abstract_context_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    event_id,
                    learner_id,
                    assessment_id,
                    event_key,
                    section,
                    module,
                    question_locator,
                    result,
                    time_seconds,
                    time_source,
                    confidence,
                    int(flagged),
                    apparent_difficulty,
                    int(answer_changed),
                    selected_answer,
                    correct_answer,
                    provisional_skill,
                    provenance_type,
                    content_fingerprint,
                    _json(abstract_context),
                    utc_now(),
                ),
            )
            if result in {"incorrect", "omitted", "correct_uncertain", "correct_slow", "correct_changed"}:
                due = next_review_date(
                    today=date.fromisoformat(self._clock_snapshot()["local_date"]),
                    prior_success=result not in {"incorrect", "omitted"},
                    confidence=confidence,
                    days_since_exposure=0,
                    similarity=1.0,
                    help_used=False,
                    timed=time_seconds is not None,
                    recurrence_count=1,
                )
                connection.execute(
                    """INSERT INTO review_queue
                    (review_id, learner_id, event_id, skill, reason, due_at,
                     recurrence_risk, evidence_strength, transfer_distance, status, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'open', ?)""",
                    (
                        _id("review"),
                        learner_id,
                        event_id,
                        provisional_skill,
                        f"Review {result} event after an initial diagnostic pass",
                        due.isoformat(),
                        0.7 if result in {"incorrect", "omitted"} else 0.45,
                        0.35,
                        choose_transfer_distance(new_skill=True, recurrence_count=1, help_used=False),
                        utc_now(),
                    ),
                )
            stored_event = _row(
                connection.execute(
                    "SELECT * FROM question_events WHERE event_id = ?",
                    (event_id,),
                ).fetchone()
            )
            completed_review_ids = self._complete_due_review_after_clean_transfer(
                connection,
                learner_id,
                stored_event or {},
            )
            connection.commit()
            return {
                "created": True,
                "event": stored_event,
                "completed_review_ids": completed_review_ids,
            }
        finally:
            connection.close()

    def record_generated_item(
        self,
        *,
        learner_id: str,
        provider: str,
        target_skill: str,
        intended_difficulty: str,
        validation_status: str,
        item_version: str,
        specification: dict[str, Any],
        target_error_signature: str | None = None,
        exposure_history: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        ensure_safe_metadata(specification)
        exposure_history = list(exposure_history or [])
        ensure_safe_metadata(exposure_history)
        connection, _ = self._open()
        try:
            _require_learner(connection, learner_id)
            existing = connection.execute(
                "SELECT * FROM generated_items WHERE learner_id = ? AND provider = ? AND item_version = ? ORDER BY created_at LIMIT 1",
                (learner_id, provider, item_version),
            ).fetchone()
            if existing:
                return {
                    "created": False,
                    "item_id": existing["item_id"],
                    "simulated_label": existing["simulated_label"],
                    "validation_status": existing["validation_status"],
                }
            item_id = _id("item")
            connection.execute(
                """INSERT INTO generated_items
                (item_id, learner_id, provider, target_skill, target_error_signature,
                 intended_difficulty, validation_status, item_version, simulated_label,
                 specification_json, exposure_history_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (item_id, learner_id, provider, target_skill, target_error_signature, intended_difficulty, validation_status, item_version, SIMULATED_LABEL, _json(specification), _json(exposure_history), utc_now()),
            )
            connection.commit()
            return {"created": True, "item_id": item_id, "simulated_label": SIMULATED_LABEL, "validation_status": validation_status}
        finally:
            connection.close()

    def record_reasoning_response(
        self,
        *,
        learner_id: str,
        event_id: str,
        prompt_id: str,
        response_text: str,
        confidence: int | None = None,
    ) -> dict[str, Any]:
        if not response_text.strip():
            raise ValueError("response_text is required")
        if len(response_text) > 4000:
            raise ValueError("response_text is limited to 4000 characters")
        if confidence is not None:
            _require_int(confidence, "confidence", 1, 5)
        connection, _ = self._open()
        try:
            _require_learner(connection, learner_id)
            if connection.execute("SELECT 1 FROM question_events WHERE event_id = ? AND learner_id = ?", (event_id, learner_id)).fetchone() is None:
                raise ValueError("event_id must belong to learner_id")
            response_id = _id("reasoning")
            connection.execute(
                """INSERT INTO reasoning_responses
                (response_id, learner_id, event_id, prompt_id, response_text, confidence, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (response_id, learner_id, event_id, prompt_id, response_text.strip(), confidence, utc_now()),
            )
            connection.commit()
            return {"response_id": response_id, "stored": True}
        finally:
            connection.close()

    def record_diagnostic_hypothesis(
        self,
        *,
        learner_id: str,
        observed_fact: str,
        hypothesis: str,
        confidence: float,
        event_id: str | None = None,
        status: str = "provisional",
        supporting_event_ids: list[str] | None = None,
        contradicting_evidence: list[str] | None = None,
    ) -> dict[str, Any]:
        if not observed_fact.strip() or not hypothesis.strip():
            raise ValueError("observed_fact and hypothesis are required")
        if not 0 <= confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")
        validate_status(status)
        supporting_event_ids = list(supporting_event_ids or [])
        contradicting_evidence = list(contradicting_evidence or [])
        ensure_safe_metadata({"supporting_event_ids": supporting_event_ids, "contradicting_evidence": contradicting_evidence})
        connection, _ = self._open()
        try:
            _require_learner(connection, learner_id)
            if event_id and connection.execute("SELECT 1 FROM question_events WHERE event_id = ? AND learner_id = ?", (event_id, learner_id)).fetchone() is None:
                raise ValueError("event_id must belong to learner_id")
            hypothesis_id = _id("hypothesis")
            now = utc_now()
            connection.execute(
                """INSERT INTO diagnostic_hypotheses
                (hypothesis_id, learner_id, event_id, observed_fact, hypothesis, confidence,
                 status, supporting_event_ids_json, contradicting_evidence_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (hypothesis_id, learner_id, event_id, observed_fact.strip(), hypothesis.strip(), confidence, status, _json(supporting_event_ids), _json(contradicting_evidence), now, now),
            )
            connection.commit()
            return {"hypothesis_id": hypothesis_id, "status": status, "diagnostic_ceiling": "Do not generalize until recurring evidence supports it."}
        finally:
            connection.close()

    def confirm_error_signature(
        self,
        *,
        learner_id: str,
        code: str,
        status: str,
        evidence_event_ids: list[str],
        notes: str | None = None,
    ) -> dict[str, Any]:
        validate_signature(code)
        validate_status(status)
        if not evidence_event_ids:
            raise ValueError("At least one evidence event is required")
        if status == "confirmed" and len(set(evidence_event_ids)) < 2:
            raise ValueError("A confirmed error signature requires recurring evidence from at least two events")
        ensure_safe_metadata({"evidence_event_ids": evidence_event_ids})
        connection, _ = self._open()
        try:
            _require_learner(connection, learner_id)
            placeholders = ",".join("?" for _ in evidence_event_ids)
            count = connection.execute(
                f"SELECT COUNT(*) FROM question_events WHERE learner_id = ? AND event_id IN ({placeholders})",
                [learner_id, *evidence_event_ids],
            ).fetchone()[0]
            if count != len(set(evidence_event_ids)):
                raise ValueError("All evidence_event_ids must belong to learner_id")
            existing = connection.execute("SELECT * FROM error_signatures WHERE learner_id = ? AND code = ?", (learner_id, code)).fetchone()
            if existing:
                validate_transition(existing["status"], status)
                signature_id = existing["signature_id"]
                recurrence_count = max(existing["recurrence_count"], len(set(evidence_event_ids)))
                connection.execute(
                    """UPDATE error_signatures SET status = ?, evidence_event_ids_json = ?,
                    recurrence_count = ?, last_seen = ?, notes = ?, updated_at = ?
                    WHERE signature_id = ?""",
                    (status, _json(sorted(set(evidence_event_ids))), recurrence_count, utc_now(), notes, utc_now(), signature_id),
                )
            else:
                signature_id = _id("signature")
                connection.execute(
                    """INSERT INTO error_signatures
                    (signature_id, learner_id, code, status, evidence_event_ids_json,
                     recurrence_count, last_seen, notes, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (signature_id, learner_id, code, status, _json(sorted(set(evidence_event_ids))), len(set(evidence_event_ids)), utc_now(), notes, utc_now()),
                )
            connection.commit()
            return {"signature_id": signature_id, "code": code, "description": ERROR_SIGNATURES[code], "status": status, "evidence_count": len(set(evidence_event_ids))}
        finally:
            connection.close()

    def get_review_queue(self, learner_id: str, *, due_only: bool = False) -> list[dict[str, Any]]:
        connection, _ = self._open()
        try:
            _require_learner(connection, learner_id)
            query = "SELECT * FROM review_queue WHERE learner_id = ? AND status = 'open'"
            args: list[Any] = [learner_id]
            if due_only:
                query += " AND due_at <= ?"
                query_args = [*args, utc_now()[:10]]
            else:
                query_args = args
            query += " ORDER BY due_at, recurrence_risk DESC"
            return _rows(connection.execute(query, query_args).fetchall())
        finally:
            connection.close()

    def get_session_state(self, learner_id: str, *, session_id: str | None = None) -> dict[str, Any] | None:
        """Return one learner-owned session or the most recent incomplete session."""
        connection, _ = self._open()
        try:
            _require_learner(connection, learner_id)
            if session_id is None:
                row = connection.execute(
                    "SELECT * FROM sessions WHERE learner_id = ? AND completed = 0 ORDER BY created_at DESC LIMIT 1",
                    (learner_id,),
                ).fetchone()
            else:
                row = connection.execute(
                    "SELECT * FROM sessions WHERE learner_id = ? AND session_id = ?",
                    (learner_id, session_id),
                ).fetchone()
            return _row(row)
        finally:
            connection.close()

    def _clock_snapshot(self) -> dict[str, str]:
        current = self._clock()
        if not isinstance(current, datetime):
            raise TypeError("clock must return a datetime")
        if current.tzinfo is None:
            current = current.astimezone()
        current = current.replace(microsecond=0)
        offset = current.strftime("%z")
        if len(offset) == 5:
            offset = f"{offset[:3]}:{offset[3:]}"
        timezone_name = getattr(current.tzinfo, "key", None) or current.tzname() or str(current.tzinfo)
        return {
            "checked_at": current.isoformat(),
            "local_date": current.date().isoformat(),
            "local_time": current.strftime("%H:%M:%S"),
            "timezone": timezone_name,
            "utc_offset": offset,
            "source": "system_local_clock",
        }

    def _session_start_context(
        self,
        connection: sqlite3.Connection,
        learner_id: str,
        band: str,
        *,
        limit: int = 3,
    ) -> dict[str, Any]:
        """Check the local date once and resolve reviews scheduled for that date."""

        clock = self._clock_snapshot()
        local_date = clock["local_date"]
        reviews = _rows(
            connection.execute(
                """SELECT * FROM review_queue
                WHERE learner_id = ? AND status = 'open' AND due_at <= ?
                ORDER BY due_at, recurrence_risk DESC""",
                (learner_id, local_date),
            ).fetchall()
        )
        event_ids = sorted({str(review["event_id"]) for review in reviews if review.get("event_id")})
        events: list[dict[str, Any]] = []
        if event_ids:
            placeholders = ",".join("?" for _ in event_ids)
            events = _rows(
                connection.execute(
                    f"""SELECT * FROM question_events
                    WHERE learner_id = ? AND event_id IN ({placeholders})
                    ORDER BY created_at DESC""",
                    [learner_id, *event_ids],
                ).fetchall()
            )
        signatures = _rows(
            connection.execute(
                "SELECT * FROM error_signatures WHERE learner_id = ? ORDER BY recurrence_count DESC",
                (learner_id,),
            ).fetchall()
        )
        scheduled = recommend_on_demand_sessions(
            band,
            events,
            reviews,
            signatures=signatures,
            limit=limit,
        )
        return {
            "clock": clock,
            "checked_for_date": local_date,
            "due_review_count": len(reviews),
            "due_today_count": sum(review.get("due_at") == local_date for review in reviews),
            "overdue_review_count": sum(str(review.get("due_at", "")) < local_date for review in reviews),
            "due_reviews": reviews,
            "scheduled_session_count": scheduled["recommendation_count"],
            "scheduled_sessions": scheduled["recommendations"],
            "no_due_session_message": (
                None
                if reviews
                else "No review-queue session is due today. Continue the next planned sprint."
            ),
            "selection_rule": (
                "Check the learner's local date before practice. Surface due or overdue reviews "
                "without silently extending the daily 20-minute budget."
            ),
        }

    def _complete_due_review_after_clean_transfer(
        self,
        connection: sqlite3.Connection,
        learner_id: str,
        event: dict[str, Any],
    ) -> list[str]:
        """Close one due review when a later clean same-skill transfer succeeds."""

        context = event.get("abstract_context", {})
        if (
            event.get("result") != "correct"
            or not isinstance(event.get("confidence"), int)
            or event["confidence"] < 4
            or context.get("help_used") is True
            or not event.get("provisional_skill")
        ):
            return []
        local_date = self._clock_snapshot()["local_date"]
        review = connection.execute(
            """SELECT review_id FROM review_queue
            WHERE learner_id = ? AND status = 'open' AND skill = ? AND due_at <= ?
              AND event_id != ? AND created_at <= ?
            ORDER BY due_at, recurrence_risk DESC LIMIT 1""",
            (
                learner_id,
                event["provisional_skill"],
                local_date,
                event["event_id"],
                event["created_at"],
            ),
        ).fetchone()
        if review is None:
            return []
        connection.execute(
            "UPDATE review_queue SET status = 'completed' WHERE review_id = ?",
            (review["review_id"],),
        )
        return [review["review_id"]]

    def get_session_start_context(
        self,
        learner_id: str,
        *,
        section: str = "reading-writing",
        limit: int = 3,
    ) -> dict[str, Any]:
        """Return the local clock and any review sessions due when practice starts."""

        if section != "reading-writing":
            raise ValueError("session-start scheduling currently supports reading-writing")
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 5:
            raise ValueError("limit must be an integer between 1 and 5")
        connection, _ = self._open()
        try:
            profile = self._get_learner(connection, learner_id)
            return self._session_start_context(
                connection,
                learner_id,
                profile["score_band_prior"],
                limit=limit,
            )
        finally:
            connection.close()

    def _difficulty_recommendation(
        self,
        connection: sqlite3.Connection,
        learner_id: str,
        band: str,
        *,
        limit: int = 12,
    ) -> dict[str, Any]:
        rows = _rows(
            connection.execute(
                """SELECT * FROM question_events
                WHERE learner_id = ? AND section = 'reading-writing'
                ORDER BY created_at DESC LIMIT ?""",
                (learner_id, limit),
            ).fetchall()
        )
        skill_rows = connection.execute(
            "SELECT skill, stage FROM skill_states WHERE learner_id = ?",
            (learner_id,),
        ).fetchall()
        skill_stages = {row["skill"]: row["stage"] for row in skill_rows}
        return recommend_practice_difficulty(band, rows, skill_stages=skill_stages)

    def _on_demand_recommendations(
        self,
        connection: sqlite3.Connection,
        learner_id: str,
        band: str,
        *,
        limit: int = 3,
    ) -> dict[str, Any]:
        """Build optional follow-up blueprints from recent learner evidence."""

        recent_cutoff = (datetime.now(timezone.utc) - timedelta(days=14)).isoformat()
        events = _rows(
            connection.execute(
                """SELECT question_events.*, assessments.taken_at AS assessment_taken_at,
                    assessments.source AS assessment_source
                FROM question_events
                LEFT JOIN assessments ON assessments.assessment_id = question_events.assessment_id
                WHERE question_events.learner_id = ?
                  AND question_events.section = 'reading-writing'
                  AND COALESCE(assessments.taken_at, question_events.created_at) >= ?
                  AND NOT EXISTS (
                      SELECT 1 FROM review_queue resolved_review
                      WHERE resolved_review.event_id = question_events.event_id
                        AND resolved_review.status = 'completed'
                  )
                ORDER BY question_events.created_at DESC LIMIT 24""",
                (learner_id, recent_cutoff[:10]),
            ).fetchall()
        )
        reviews = _rows(
            connection.execute(
                """SELECT * FROM review_queue
                WHERE learner_id = ? AND status = 'open' AND due_at <= ?
                ORDER BY due_at, recurrence_risk DESC LIMIT 50""",
                (learner_id, self._clock_snapshot()["local_date"]),
            ).fetchall()
        )
        signatures = _rows(
            connection.execute(
                "SELECT * FROM error_signatures WHERE learner_id = ? ORDER BY recurrence_count DESC",
                (learner_id,),
            ).fetchall()
        )
        return recommend_on_demand_sessions(
            band,
            events,
            reviews,
            signatures=signatures,
            limit=limit,
        )

    def get_difficulty_recommendation(
        self,
        learner_id: str,
        *,
        section: str = "reading-writing",
        limit: int = 12,
    ) -> dict[str, Any]:
        """Return the transparent future-practice difficulty recommendation."""
        if section != "reading-writing":
            raise ValueError("difficulty adaptation currently supports reading-writing")
        _require_int(limit, "limit", 4, 50)
        connection, _ = self._open()
        try:
            profile = self._get_learner(connection, learner_id)
            return self._difficulty_recommendation(
                connection,
                learner_id,
                profile["score_band_prior"],
                limit=limit,
            )
        finally:
            connection.close()

    def get_on_demand_recommendations(
        self,
        learner_id: str,
        *,
        section: str = "reading-writing",
        limit: int = 3,
    ) -> dict[str, Any]:
        """Return optional issue-specific sessions after a sprint or review."""

        if section != "reading-writing":
            raise ValueError("on-demand recommendations currently support reading-writing")
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 5:
            raise ValueError("limit must be an integer between 1 and 5")
        connection, _ = self._open()
        try:
            profile = self._get_learner(connection, learner_id)
            return self._on_demand_recommendations(
                connection,
                learner_id,
                profile["score_band_prior"],
                limit=limit,
            )
        finally:
            connection.close()

    def build_daily_session(
        self,
        learner_id: str,
        *,
        band: str | None = None,
        session_mode: str = "default",
    ) -> dict[str, Any]:
        connection, _ = self._open()
        try:
            profile = self._get_learner(connection, learner_id)
            band = band or profile["score_band_prior"]
            plan = build_daily_plan(band, session_mode=session_mode)
            difficulty = self._difficulty_recommendation(connection, learner_id, band)
            session_start = self._session_start_context(connection, learner_id, band)
            session_id = _id("session")
            now = utc_now()
            connection.execute(
                """INSERT INTO sessions
                (session_id, learner_id, planned_minutes, actual_minutes, band,
                 activities_json, results_json, fatigue, completed, created_at, updated_at)
                VALUES (?, ?, ?, NULL, ?, ?, '[]', NULL, 0, ?, ?)""",
                (session_id, learner_id, plan.planned_minutes, band, _json(plan.as_dict()["activities"]), now, now),
            )
            connection.commit()
            return {
                "session_id": session_id,
                "plan": plan.as_dict(),
                "difficulty_recommendation": difficulty,
                "session_start_context": session_start,
                "stored": True,
            }
        finally:
            connection.close()

    def record_activity_result(
        self,
        *,
        learner_id: str,
        session_id: str,
        activity_type: str,
        outcome: str,
        actual_minutes: int,
        fatigue: str | None = None,
        completed: bool = False,
    ) -> dict[str, Any]:
        _require_int(actual_minutes, "actual_minutes", 0, 20)
        ensure_safe_metadata({"activity_type": activity_type, "outcome": outcome, "fatigue": fatigue})
        connection, _ = self._open()
        try:
            session = connection.execute("SELECT * FROM sessions WHERE session_id = ? AND learner_id = ?", (session_id, learner_id)).fetchone()
            if session is None:
                raise ValueError("session_id must belong to learner_id")
            planned_types = {item["activity_type"] for item in _decode(session["activities_json"], [])}
            if activity_type not in planned_types:
                raise ValueError("activity_type is not part of the planned session")
            results = _decode(session["results_json"], [])
            existing = next((item for item in results if item["activity_type"] == activity_type), None)
            candidate = {"activity_type": activity_type, "outcome": outcome, "actual_minutes": actual_minutes}
            if existing is not None:
                if existing != candidate:
                    raise ValueError("conflicting retry for an already recorded activity")
                follow_up = self._on_demand_recommendations(
                    connection,
                    learner_id,
                    session["band"],
                ) if bool(session["completed"]) else None
                return {
                    "created": False,
                    "session_id": session_id,
                    "activity_count": len(results),
                    "actual_minutes": session["actual_minutes"],
                    "completed": bool(session["completed"]),
                    "on_demand_recommendations": follow_up,
                }
            results.append(candidate)
            total_minutes = sum(item["actual_minutes"] for item in results)
            if total_minutes > session["planned_minutes"]:
                raise ValueError(
                    f"Recorded activities would exceed the planned {session['planned_minutes']}-minute budget"
                )
            connection.execute(
                "UPDATE sessions SET actual_minutes = ?, results_json = ?, fatigue = ?, completed = ?, updated_at = ? WHERE session_id = ?",
                (total_minutes, _json(results), fatigue, int(completed), utc_now(), session_id),
            )
            connection.commit()
            follow_up = self._on_demand_recommendations(
                connection,
                learner_id,
                session["band"],
            ) if completed else None
            return {
                "created": True,
                "session_id": session_id,
                "activity_count": len(results),
                "actual_minutes": total_minutes,
                "completed": completed,
                "on_demand_recommendations": follow_up,
            }
        finally:
            connection.close()

    def record_visual_submission(
        self,
        *,
        learner_id: str,
        payload: dict[str, Any],
        manifest: dict[str, Any],
    ) -> dict[str, Any]:
        """Validate and idempotently persist one content-free Visualize section.

        The transient manifest resolves answer keys and diagnostic metadata. It
        is inspected but never copied wholesale into the learner model.
        """

        connection, _ = self._open()
        try:
            _require_learner(connection, learner_id)
            session_row = connection.execute(
                "SELECT * FROM sessions WHERE session_id = ? AND learner_id = ?",
                (payload.get("session_id"), learner_id),
            ).fetchone()
            if session_row is None:
                raise ValueError("session_id must belong to learner_id")
            session = _row(session_row)
            if session is None:
                raise ValueError("session could not be read")
            validated = validate_visual_submission(
                payload,
                learner_id=learner_id,
                session_state=session,
                manifest=manifest,
            )
            submission = validated["payload"]
            submission_id = submission["submission_id"]
            digest = sha256(_json(submission).encode("utf-8")).hexdigest()
            prior_results = list(session.get("results", []))
            existing = next((item for item in prior_results if item.get("submission_id") == submission_id), None)
            if existing is not None:
                if existing.get("payload_digest") != digest:
                    raise ValueError("conflicting retry for an already persisted Visualize section")
                completed_review_ids: list[str] = []
                for event_id in existing.get("event_ids", []):
                    event = _row(
                        connection.execute(
                            "SELECT * FROM question_events WHERE event_id = ? AND learner_id = ?",
                            (event_id, learner_id),
                        ).fetchone()
                    )
                    if event is not None:
                        completed_review_ids.extend(
                            self._complete_due_review_after_clean_transfer(connection, learner_id, event)
                        )
                if completed_review_ids:
                    connection.commit()
                follow_up = self._on_demand_recommendations(
                    connection,
                    learner_id,
                    session["band"],
                )
                return {
                    "created": False,
                    "persisted": True,
                    "submission_id": submission_id,
                    "session_id": session["session_id"],
                    "section": submission["section"],
                    "event_count": len(existing.get("event_ids", [])),
                    "completed_review_ids": completed_review_ids,
                    "strategy_conclusion": existing.get("strategy_conclusion"),
                    "on_demand_recommendations": follow_up,
                }

            section = submission["section"]
            if section == "strategy_and_reflection" and not any(
                item.get("submission_id") == f"{session['session_id']}:diagnostic_core"
                for item in prior_results
            ):
                raise ValueError("diagnostic_core must be persisted before the final section")

            # Legacy incomplete sessions can be safely consolidated from the
            # earlier five-fragment plan before they receive any result.
            planned_types = frozenset(item.get("activity_type") for item in session.get("activities", []))
            surface_types = frozenset({"focused_diagnostic_block", "strategy_reflection_block"})
            default_types = frozenset(
                item["activity_type"]
                for item in build_daily_plan(session["band"]).as_dict()["activities"]
            )
            if not prior_results and planned_types not in (surface_types, default_types):
                plan = build_daily_plan(session["band"], session_mode="strategy_trial")
                session["activities"] = plan.as_dict()["activities"]
                connection.execute(
                    "UPDATE sessions SET activities_json = ?, updated_at = ? WHERE session_id = ?",
                    (_json(session["activities"]), utc_now(), session["session_id"]),
                )

            assessment_external_id = f"visualize:{session['session_id']}"
            resolved_provenance = sorted({
                metadata.get("provenance_type", "simulated")
                for metadata in validated["resolved_items"]
            })
            assessment = connection.execute(
                "SELECT * FROM assessments WHERE learner_id = ? AND source = 'other' AND external_id = ?",
                (learner_id, assessment_external_id),
            ).fetchone()
            if assessment is None:
                assessment_id = _id("assessment")
                connection.execute(
                    """INSERT INTO assessments
                    (assessment_id, learner_id, source, assessment_type, external_id, taken_at,
                     is_official, total_score, reading_writing_score, math_score,
                     domain_evidence_json, import_provenance_json, created_at)
                    VALUES (?, ?, 'other', 'visualize_practice', ?, ?, 0,
                            NULL, NULL, NULL, ?, ?, ?)""",
                    (
                        assessment_id,
                        learner_id,
                        assessment_external_id,
                        self._clock_snapshot()["local_date"],
                        _json({"surface": "visualize", "manifest_id": submission["manifest_id"]}),
                        _json({
                            "mode": "structured_follow_up",
                            "content_stored": False,
                            "provenance_types": resolved_provenance,
                        }),
                        utc_now(),
                    ),
                )
            else:
                assessment_id = assessment["assessment_id"]

            event_ids: list[str] = []
            completed_review_ids: list[str] = []
            strategy_observations: list[dict[str, Any]] = []
            answer_by_id = {item["item_id"]: item for item in submission["answers"]}
            for metadata in validated["resolved_items"]:
                item_id = metadata["item_id"]
                answer = answer_by_id[item_id]
                provider = metadata["provider"]
                item_version = metadata["item_version"]
                provenance_type = metadata.get("provenance_type", "simulated")
                if provenance_type == "simulated":
                    generated = connection.execute(
                        "SELECT item_id FROM generated_items WHERE learner_id = ? AND provider = ? AND item_version = ? ORDER BY created_at LIMIT 1",
                        (learner_id, provider, item_version),
                    ).fetchone()
                    if generated is None:
                        connection.execute(
                            """INSERT INTO generated_items
                            (item_id, learner_id, provider, target_skill, target_error_signature,
                             intended_difficulty, validation_status, item_version, simulated_label,
                             specification_json, exposure_history_json, created_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '[]', ?)""",
                            (
                                _id("item"),
                                learner_id,
                                provider,
                                metadata["target_skill"],
                                metadata.get("target_error_signature"),
                                metadata["intended_difficulty"],
                                metadata["validation_status"],
                                item_version,
                                SIMULATED_LABEL,
                                _json({
                                    "manifest_id": submission["manifest_id"],
                                    "question_type": metadata.get("question_type"),
                                    "strategy_condition": metadata.get("strategy_condition"),
                                }),
                                utc_now(),
                            ),
                        )

                selected = answer["selected_answer"]
                correct = selected == metadata["correct_answer"]
                if selected is None:
                    result = "omitted"
                elif not correct:
                    result = "incorrect"
                elif answer["answer_changed"]:
                    result = "correct_changed"
                elif metadata.get("slow_threshold_seconds") is not None and answer["time_seconds"] > metadata["slow_threshold_seconds"]:
                    result = "correct_slow"
                elif answer["confidence"] <= 2 or answer["almost_choice"] is not None:
                    result = "correct_uncertain"
                else:
                    result = "correct"

                event_key = f"{session['session_id']}:{item_id}"
                event = connection.execute(
                    "SELECT * FROM question_events WHERE learner_id = ? AND assessment_id = ? AND event_key = ?",
                    (learner_id, assessment_id, event_key),
                ).fetchone()
                if event is None:
                    event_id = _id("event")
                    abstract_context = {
                        "manifest_id": submission["manifest_id"],
                        "provenance_type": provenance_type,
                        "source_label": metadata.get("source_label"),
                        "target_error_signature": metadata.get("target_error_signature"),
                        "intended_difficulty": metadata["intended_difficulty"],
                        "slow_threshold_seconds": metadata.get("slow_threshold_seconds"),
                        "almost_choice": answer["almost_choice"],
                        "help_used": answer["help_used"],
                        "strategy_condition": metadata.get("strategy_condition"),
                        "timing_source": answer.get("timing_source", "legacy_visualize_reported"),
                        "timer_state": answer.get("timer_state"),
                    }
                    connection.execute(
                        """INSERT INTO question_events
                        (event_id, learner_id, assessment_id, event_key, section, module,
                         question_locator, result, time_seconds, time_source, confidence, flagged,
                         apparent_difficulty, answer_changed, selected_answer, correct_answer, provisional_skill,
                         provenance_type, content_fingerprint, abstract_context_json, created_at)
                        VALUES (?, ?, ?, ?, 'reading-writing', ?, ?, ?, ?, ?, ?, 0,
                                ?, ?, ?, ?, ?, ?, NULL, ?, ?)""",
                        (
                            event_id,
                            learner_id,
                            assessment_id,
                            event_key,
                            section,
                            metadata.get("source_locator", item_id),
                            result,
                            answer["time_seconds"],
                            "visualize_monotonic_timer" if submission["schema_version"] in {"1.1", "1.2"} else "learner_reported",
                            answer["confidence"],
                            answer.get("apparent_difficulty"),
                            int(answer["answer_changed"]),
                            selected,
                            metadata["correct_answer"],
                            metadata["target_skill"],
                            provenance_type,
                            _json(abstract_context),
                            utc_now(),
                        ),
                    )
                    if result in {"incorrect", "omitted", "correct_uncertain", "correct_slow", "correct_changed"}:
                        due = next_review_date(
                            today=date.fromisoformat(self._clock_snapshot()["local_date"]),
                            prior_success=result not in {"incorrect", "omitted"},
                            confidence=answer["confidence"],
                            days_since_exposure=0,
                            similarity=1.0,
                            help_used=answer["help_used"],
                            timed=True,
                            recurrence_count=1,
                        )
                        connection.execute(
                            """INSERT INTO review_queue
                            (review_id, learner_id, event_id, skill, reason, due_at,
                             recurrence_risk, evidence_strength, transfer_distance, status, created_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'open', ?)""",
                            (
                                _id("review"), learner_id, event_id, metadata["target_skill"],
                                f"Review {result} {provenance_type} response", due.isoformat(),
                                0.7 if result in {"incorrect", "omitted"} else 0.45,
                                0.35, "near", utc_now(),
                            ),
                        )
                else:
                    event_id = event["event_id"]
                event_ids.append(event_id)
                stored_event = _row(
                    connection.execute(
                        "SELECT * FROM question_events WHERE event_id = ?",
                        (event_id,),
                    ).fetchone()
                )
                if stored_event is not None:
                    completed_review_ids.extend(
                        self._complete_due_review_after_clean_transfer(connection, learner_id, stored_event)
                    )
                condition = metadata.get("strategy_condition")
                if condition in {"A", "B"}:
                    strategy_observations.append({
                        "event_key": event_key,
                        "condition": condition,
                        "correct": correct,
                        "time_seconds": answer["time_seconds"],
                        "confidence": answer["confidence"],
                        "reread_count": 0,
                    })

            strategy_conclusion = None
            if strategy_observations:
                trial_id = f"trial_visual_{sha256(session['session_id'].encode('utf-8')).hexdigest()[:24]}"
                trial = connection.execute(
                    "SELECT * FROM strategy_trials WHERE trial_id = ? AND learner_id = ?",
                    (trial_id, learner_id),
                ).fetchone()
                if trial is None:
                    connection.execute(
                        """INSERT INTO strategy_trials
                        (trial_id, learner_id, strategy, question_type, condition_a_json,
                         condition_b_json, results_json, sample_size, provisional_conclusion,
                         status, created_at, updated_at)
                        VALUES (?, ?, 'stem-first-vs-options-first', 'rhetorical-synthesis', ?, ?,
                                '[]', 0, NULL, 'active', ?, ?)""",
                        (
                            trial_id, learner_id,
                            _json({"label": "predict_before_options"}),
                            _json({"label": "inspect_options_first"}),
                            utc_now(), utc_now(),
                        ),
                    )
                    trial_results: list[dict[str, Any]] = []
                else:
                    trial_results = _decode(trial["results_json"], [])
                known = {item.get("event_key") for item in trial_results}
                trial_results.extend(item for item in strategy_observations if item["event_key"] not in known)
                by_condition = {label: [item for item in trial_results if item["condition"] == label] for label in ("A", "B")}
                if len(by_condition["A"]) >= 2 and len(by_condition["B"]) >= 2:
                    strategy_conclusion = {
                        "status": "provisional",
                        "accuracy_A": sum(item["correct"] for item in by_condition["A"]) / len(by_condition["A"]),
                        "accuracy_B": sum(item["correct"] for item in by_condition["B"]) / len(by_condition["B"]),
                    }
                else:
                    strategy_conclusion = {"status": "inconclusive", "minimum": "two observations per condition"}
                connection.execute(
                    """UPDATE strategy_trials SET results_json = ?, sample_size = ?,
                    provisional_conclusion = ?, updated_at = ? WHERE trial_id = ?""",
                    (_json(trial_results), len(trial_results), _json(strategy_conclusion), utc_now(), trial_id),
                )

            activity_index = 0 if section == "diagnostic_core" else 1
            activities = session.get("activities", [])
            fallback_type = "focused_diagnostic_block" if section == "diagnostic_core" else "strategy_reflection_block"
            activity_type = (
                activities[activity_index].get("activity_type", fallback_type)
                if len(activities) > activity_index
                else fallback_type
            )
            result_entry = {
                "activity_type": activity_type,
                "submission_id": submission_id,
                "payload_digest": digest,
                "outcome": "persisted",
                "actual_minutes": submission["actual_minutes"],
                "event_ids": event_ids,
                "reflection": submission["reflection"],
                "strategy_conclusion": strategy_conclusion,
            }
            updated_results = [*prior_results, result_entry]
            total_minutes = sum(int(item.get("actual_minutes", 0)) for item in updated_results)
            if total_minutes > session["planned_minutes"]:
                raise ValueError("recorded sections exceed the planned session time")
            completed = section == "strategy_and_reflection"
            connection.execute(
                """UPDATE sessions SET actual_minutes = ?, results_json = ?, fatigue = ?,
                completed = ?, updated_at = ? WHERE session_id = ?""",
                (
                    total_minutes, _json(updated_results), submission["fatigue"],
                    int(completed), utc_now(), session["session_id"],
                ),
            )
            connection.commit()
            follow_up = self._on_demand_recommendations(
                connection,
                learner_id,
                session["band"],
            )
            return {
                "created": True,
                "persisted": True,
                "submission_id": submission_id,
                "session_id": session["session_id"],
                "section": section,
                "event_count": len(event_ids),
                "completed_review_ids": completed_review_ids,
                "actual_minutes": total_minutes,
                "completed": completed,
                "strategy_conclusion": strategy_conclusion,
                "on_demand_recommendations": follow_up,
            }
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def begin_strategy_trial(
        self,
        *,
        learner_id: str,
        strategy: str,
        question_type: str,
        condition_a: dict[str, Any],
        condition_b: dict[str, Any],
    ) -> dict[str, Any]:
        ensure_safe_metadata({"condition_a": condition_a, "condition_b": condition_b})
        connection, _ = self._open()
        try:
            _require_learner(connection, learner_id)
            trial_id = _id("trial")
            now = utc_now()
            connection.execute(
                """INSERT INTO strategy_trials
                (trial_id, learner_id, strategy, question_type, condition_a_json,
                 condition_b_json, results_json, sample_size, provisional_conclusion,
                 status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, '[]', 0, NULL, 'active', ?, ?)""",
                (trial_id, learner_id, strategy, question_type, _json(condition_a), _json(condition_b), now, now),
            )
            connection.commit()
            return {"trial_id": trial_id, "status": "active", "warning": "Use paired or counterbalanced evidence; do not conclude from one item."}
        finally:
            connection.close()

    def record_strategy_trial_result(
        self,
        *,
        learner_id: str,
        trial_id: str,
        condition: str,
        correct: bool,
        time_seconds: float | None,
        confidence: int | None,
        reread_count: int = 0,
    ) -> dict[str, Any]:
        if condition not in {"A", "B"}:
            raise ValueError("condition must be A or B")
        if confidence is not None:
            _require_int(confidence, "confidence", 1, 5)
        if reread_count < 0:
            raise ValueError("reread_count cannot be negative")
        connection, _ = self._open()
        try:
            trial = connection.execute("SELECT * FROM strategy_trials WHERE trial_id = ? AND learner_id = ?", (trial_id, learner_id)).fetchone()
            if trial is None:
                raise ValueError("trial_id must belong to learner_id")
            results = _decode(trial["results_json"], [])
            results.append({"condition": condition, "correct": bool(correct), "time_seconds": time_seconds, "confidence": confidence, "reread_count": reread_count})
            by_condition = {label: [item for item in results if item["condition"] == label] for label in ("A", "B")}
            conclusion = None
            if len(by_condition["A"]) >= 2 and len(by_condition["B"]) >= 2:
                acc_a = sum(item["correct"] for item in by_condition["A"]) / len(by_condition["A"])
                acc_b = sum(item["correct"] for item in by_condition["B"]) / len(by_condition["B"])
                conclusion = {"accuracy_A": acc_a, "accuracy_B": acc_b, "status": "provisional"}
            else:
                conclusion = {"status": "inconclusive", "minimum": "two observations per condition"}
            connection.execute(
                "UPDATE strategy_trials SET results_json = ?, sample_size = ?, provisional_conclusion = ?, updated_at = ? WHERE trial_id = ?",
                (_json(results), len(results), json.dumps(conclusion, ensure_ascii=False, sort_keys=True), utc_now(), trial_id),
            )
            connection.commit()
            return {"trial_id": trial_id, "sample_size": len(results), "conclusion": conclusion}
        finally:
            connection.close()

    def get_progress_summary(self, learner_id: str) -> dict[str, Any]:
        connection, _ = self._open()
        try:
            profile = self._get_learner(connection, learner_id)
            assessment_count = connection.execute("SELECT COUNT(*) FROM assessments WHERE learner_id = ?", (learner_id,)).fetchone()[0]
            event_counts = {
                result: connection.execute("SELECT COUNT(*) FROM question_events WHERE learner_id = ? AND result = ?", (learner_id, result)).fetchone()[0]
                for result in QUESTION_RESULTS
            }
            signatures = _rows(connection.execute("SELECT * FROM error_signatures WHERE learner_id = ? ORDER BY recurrence_count DESC", (learner_id,)).fetchall())
            skills = _rows(connection.execute("SELECT * FROM skill_states WHERE learner_id = ? ORDER BY recurrence_risk DESC", (learner_id,)).fetchall())
            difficulty = self._difficulty_recommendation(
                connection,
                learner_id,
                profile["score_band_prior"],
            )
            on_demand = self._on_demand_recommendations(
                connection,
                learner_id,
                profile["score_band_prior"],
            )
            return {
                "learner_id": learner_id,
                "score_band_prior": profile["score_band_prior"],
                "assessment_count": assessment_count,
                "question_event_counts": event_counts,
                "error_signatures": signatures,
                "skill_states": skills,
                "difficulty_recommendation": difficulty,
                "on_demand_recommendations": on_demand,
                "interpretation": "Evidence summary only; not an official score prediction.",
            }
        finally:
            connection.close()

    def export_learner_model(self, learner_id: str, output_path: str | Path | None = None) -> dict[str, Any]:
        connection, paths = self._open()
        try:
            learner = self._get_learner(connection, learner_id)
            tables = {
                "assessments": "SELECT * FROM assessments WHERE learner_id = ? ORDER BY created_at",
                "question_events": "SELECT * FROM question_events WHERE learner_id = ? ORDER BY created_at",
                "reasoning_responses": "SELECT * FROM reasoning_responses WHERE learner_id = ? ORDER BY created_at",
                "diagnostic_hypotheses": "SELECT * FROM diagnostic_hypotheses WHERE learner_id = ? ORDER BY created_at",
                "error_signatures": "SELECT * FROM error_signatures WHERE learner_id = ? ORDER BY updated_at",
                "skill_states": "SELECT * FROM skill_states WHERE learner_id = ? ORDER BY updated_at",
                "review_queue": "SELECT * FROM review_queue WHERE learner_id = ? ORDER BY due_at",
                "strategy_trials": "SELECT * FROM strategy_trials WHERE learner_id = ? ORDER BY created_at",
                "sessions": "SELECT * FROM sessions WHERE learner_id = ? ORDER BY created_at",
            }
            payload: dict[str, Any] = {
                "schema_version": 1,
                "exported_at": utc_now(),
                "product": "OpenSAT",
                "learner": learner,
                "records": {name: _rows(connection.execute(query, (learner_id,)).fetchall()) for name, query in tables.items()},
                "content_boundary": {
                    "official_content_persisted": False,
                    "official_item_text_included": False,
                    "simulated_label_only": True,
                    "secrets_included": False,
                },
            }
            ensure_safe_metadata(payload)
            if output_path is None:
                output = paths.exports / f"learner-{learner_id}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
            else:
                output = Path(output_path).expanduser().resolve()
                if _is_inside(output, _repository_root()):
                    raise ValueError("Learner-model exports must be outside the repository")
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
            try:
                output.chmod(0o600)
            except OSError:
                pass
            return {"path": str(output), "learner_id": learner_id, "records": {name: len(values) for name, values in payload["records"].items()}}
        finally:
            connection.close()

    def import_learner_model(self, input_path: str | Path) -> dict[str, Any]:
        source = Path(input_path).expanduser().resolve()
        payload = load_json_object(source.read_text(), "learner_model_export")
        if payload.get("schema_version") != 1 or not isinstance(payload.get("learner"), dict):
            raise ValueError("Unsupported learner-model export")
        learner = payload["learner"]
        learner_id = learner.get("learner_id")
        if not learner_id:
            raise ValueError("Export is missing learner_id")
        records = payload.get("records", {})
        connection, _ = self._open()
        try:
            exists = connection.execute("SELECT 1 FROM learners WHERE learner_id = ?", (learner_id,)).fetchone()
            if not exists:
                connection.execute(
                    """INSERT INTO learners
                    (learner_id, preferred_language, explanation_mode, score_context_json,
                     score_band_prior, test_date, accessibility_preferences_json,
                     session_length_preference, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (learner_id, learner["preferred_language"], learner["explanation_mode"], _json(learner.get("score_context", {})), learner["score_band_prior"], learner.get("test_date"), _json(learner.get("accessibility_preferences", {})), learner.get("session_length_preference", 20), learner.get("created_at", utc_now()), utc_now()),
                )
            imported = {"learner": 0 if exists else 1}
            for assessment in records.get("assessments", []):
                connection.execute(
                    """INSERT OR IGNORE INTO assessments
                    (assessment_id, learner_id, source, assessment_type, external_id, taken_at,
                     is_official, total_score, reading_writing_score, math_score,
                     domain_evidence_json, import_provenance_json, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (assessment["assessment_id"], learner_id, assessment["source"], assessment["assessment_type"], assessment["external_id"], assessment.get("taken_at"), int(assessment.get("is_official", False)), assessment.get("total_score"), assessment.get("reading_writing_score"), assessment.get("math_score"), _json(assessment.get("domain_evidence", {})), _json(assessment.get("import_provenance", {})), assessment.get("created_at", utc_now())),
                )
                imported["assessments"] = imported.get("assessments", 0) + 1
            for event in records.get("question_events", []):
                connection.execute(
                    """INSERT OR IGNORE INTO question_events
                    (event_id, learner_id, assessment_id, event_key, section, module,
                     question_locator, result, time_seconds, time_source, confidence, flagged,
                     apparent_difficulty, answer_changed, selected_answer, correct_answer, provisional_skill,
                     provenance_type, content_fingerprint, abstract_context_json, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (event["event_id"], learner_id, event.get("assessment_id"), event["event_key"], event["section"], event.get("module"), event["question_locator"], event["result"], event.get("time_seconds"), event.get("time_source"), event.get("confidence"), int(event.get("flagged", False)), event.get("apparent_difficulty"), int(event.get("answer_changed", False)), event.get("selected_answer"), event.get("correct_answer"), event.get("provisional_skill"), event["provenance_type"], event.get("content_fingerprint"), _json(event.get("abstract_context", {})), event.get("created_at", utc_now())),
                )
                imported["question_events"] = imported.get("question_events", 0) + 1
            connection.commit()
            return {"learner_id": learner_id, "imported": imported}
        finally:
            connection.close()

    def delete_learner_data(self, learner_id: str, *, confirm: bool = False) -> dict[str, Any]:
        if confirm is not True:
            raise ValueError("Explicit confirm=true is required to delete learner data")
        connection, paths = self._open()
        try:
            exists = connection.execute("SELECT 1 FROM learners WHERE learner_id = ?", (learner_id,)).fetchone()
            if exists is None:
                return {"deleted": False, "learner_id": learner_id, "removed_exports": 0}
            connection.execute("DELETE FROM learners WHERE learner_id = ?", (learner_id,))
            connection.commit()
        finally:
            connection.close()
        removed_exports = 0
        for export in paths.exports.glob(f"learner-{learner_id}-*.json"):
            export.unlink()
            removed_exports += 1
        return {"deleted": True, "learner_id": learner_id, "removed_exports": removed_exports}


def _repository_root() -> Path:
    # service.py -> learner_model -> opensat -> src -> plugin root
    return Path(__file__).resolve().parents[3]


def _is_inside(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False
