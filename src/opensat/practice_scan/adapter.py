"""User-authorized, read-only Chrome practice-scan adapter.

The host-specific Chrome bridge is deliberately outside this module.  It must
provide a normalized page snapshot; this adapter owns authorization, scope,
prompt-injection defenses, metadata allowlisting, preview/resume semantics,
explicit commit, and transient-content disposal.
"""

from __future__ import annotations

from collections import Counter
import json
from typing import Any

from ..domain.constants import QUESTION_RESULTS
from ..privacy.redaction import ensure_safe_metadata
from .cursor import ScanCursor
from .models import (
    ChromePageSnapshot,
    ChromeScanAuthorization,
    validate_identifier,
    validate_result,
)
from .security import ConfirmationRequired, CursorError, ScanBlocked, raise_for_unsafe_page


_ALLOWED_ATTEMPT_KEYS = {
    "attempt_id",
    "assessment_type",
    "taken_at",
    "total_score",
    "reading_writing_score",
    "math_score",
    "domain_evidence",
}
_ALLOWED_QUESTION_KEYS = {
    "event_key",
    "question_locator",
    "section",
    "module",
    "result",
    "time_seconds",
    "time_source",
    "confidence",
    "flagged",
    "answer_changed",
    "selected_answer",
    "correct_answer",
    "provisional_skill",
    "abstract_context",
}
_SCORE_FIELDS = ("total_score", "reading_writing_score", "math_score")


def _safe_scalar(value: Any, field_name: str, *, maximum: int = 200) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    value = value.strip()
    if not value or len(value) > maximum or "\x00" in value:
        raise ValueError(f"{field_name} is invalid")
    return value


def _optional_scalar_map(value: Any, field_name: str) -> dict[str, str | int | float | bool]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be an object")
    ensure_safe_metadata(value)
    result: dict[str, str | int | float | bool] = {}
    for key, item in value.items():
        key = _safe_scalar(key, f"{field_name} key", maximum=80)
        if isinstance(item, bool):
            result[key] = item
        elif isinstance(item, (int, float)) and not isinstance(item, bool):
            result[key] = item
        elif isinstance(item, str):
            result[key] = _safe_scalar(item, f"{field_name}.{key}", maximum=160)
        else:
            raise ValueError(f"{field_name} values must be scalar derived metadata")
    if len(result) > 30:
        raise ValueError(f"{field_name} contains too many fields")
    return result


def _optional_score(value: Any, field_name: str, minimum: int, maximum: int) -> int | None:
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool) or not minimum <= value <= maximum:
        raise ValueError(f"{field_name} is outside the allowed score range")
    return value


def _optional_answer(value: Any, field_name: str) -> str | None:
    if value is None:
        return None
    answer = _safe_scalar(value, field_name, maximum=32)
    return answer


class ChromeReadOnlyAdapter:
    """Process normalized Chrome observations without controlling the account."""

    def __init__(self, service: Any):
        self.service = service

    def begin_scan(
        self,
        *,
        learner_id: str,
        authorization: ChromeScanAuthorization | dict[str, Any],
        page: ChromePageSnapshot | dict[str, Any],
    ) -> dict[str, Any]:
        auth = ChromeScanAuthorization.from_value(authorization)
        snapshot = ChromePageSnapshot.from_value(page)
        try:
            auth.require_user_confirmation()
            self._guard_page(auth, snapshot)
            attempt, observations, uncertainty = self._derive_page(snapshot)
            external_id = attempt["attempt_id"]
            preview = self._build_preview(
                auth=auth,
                snapshot=snapshot,
                attempt=attempt,
                observations=observations,
                uncertainty=uncertainty,
                pages_seen=1,
            )
            started = self.service.begin_practice_import(
                learner_id=learner_id,
                source=auth.source,
                external_id=external_id,
                preview=preview,
                cursor=None,
            )
            import_row = started["import"]
            if not started["created"]:
                return self._response(import_row, has_more=snapshot.has_more, existing=True)
            cursor = ScanCursor.new(
                import_id=import_row["import_id"],
                next_page_index=snapshot.page_index + 1,
                observation_count=len(observations),
            ).encode()
            self.service.update_practice_import(
                learner_id=learner_id,
                import_id=import_row["import_id"],
                cursor=cursor,
                expected_cursor=None,
                status="preview",
                preview=preview,
            )
            import_row = self.service.get_practice_import(learner_id, import_row["import_id"])
            return self._response(import_row, has_more=snapshot.has_more, existing=False)
        finally:
            snapshot.discard()

    def resume_scan(
        self,
        *,
        learner_id: str,
        import_id: str,
        cursor: str,
        authorization: ChromeScanAuthorization | dict[str, Any],
        page: ChromePageSnapshot | dict[str, Any],
    ) -> dict[str, Any]:
        auth = ChromeScanAuthorization.from_value(authorization)
        snapshot = ChromePageSnapshot.from_value(page)
        try:
            auth.require_user_confirmation()
            import_row = self.service.get_practice_import(learner_id, import_id)
            if import_row["status"] == "blocked":
                raise ScanBlocked("blocked_import_requires_new_scan")
            if import_row["status"] == "complete":
                raise ValueError("completed practice imports cannot be resumed")
            self._validate_cursor(import_row, import_id, cursor)
            state = ScanCursor.decode(cursor)
            if snapshot.page_index != state.next_page_index:
                raise CursorError("cursor_page_mismatch")
            self._guard_page(auth, snapshot)
            attempt, observations, uncertainty = self._derive_page(snapshot)
            existing_preview = import_row.get("preview") or {}
            existing_attempt = existing_preview.get("attempt") or {}
            if existing_attempt.get("attempt_id") != attempt["attempt_id"]:
                raise ScanBlocked("attempt_identity_changed")
            merged_observations = self._merge_observations(existing_preview.get("observations", []), observations)
            prior_uncertainty = existing_preview.get("uncertainty", [])
            if not isinstance(prior_uncertainty, list) or not all(isinstance(item, str) for item in prior_uncertainty):
                raise ValueError("stored scan uncertainty is malformed")
            merged_uncertainty = sorted(set(prior_uncertainty) | set(uncertainty))
            preview = self._build_preview(
                auth=auth,
                snapshot=snapshot,
                attempt={**existing_attempt, **{key: value for key, value in attempt.items() if value is not None}},
                observations=merged_observations,
                uncertainty=merged_uncertainty,
                pages_seen=int(existing_preview.get("pages_seen", 0)) + 1,
                existing=existing_preview,
            )
            next_cursor = ScanCursor.new(
                import_id=import_id,
                next_page_index=snapshot.page_index + 1,
                observation_count=len(merged_observations),
            ).encode()
            self.service.update_practice_import(
                learner_id=learner_id,
                import_id=import_id,
                cursor=next_cursor,
                expected_cursor=cursor,
                status="preview",
                preview=preview,
            )
            import_row = self.service.get_practice_import(learner_id, import_id)
            return self._response(import_row, has_more=snapshot.has_more, existing=False)
        except ScanBlocked as exc:
            self._mark_blocked(learner_id, import_id, cursor, exc)
            raise
        finally:
            snapshot.discard()

    def commit_scan(self, *, learner_id: str, import_id: str, cursor: str, confirm: bool) -> dict[str, Any]:
        if confirm is not True:
            raise ConfirmationRequired("explicit confirmation is required before persisting scan results")
        import_row = self.service.get_practice_import(learner_id, import_id)
        self._validate_cursor(import_row, import_id, cursor)
        if import_row["status"] == "blocked":
            raise ScanBlocked("blocked_scan_cannot_commit")
        if import_row["status"] == "complete":
            return {"committed": False, "status": "complete", "import_id": import_id}
        preview = import_row.get("preview") or {}
        attempt = preview.get("attempt") or {}
        observations = preview.get("observations") or []
        if not isinstance(attempt, dict) or not isinstance(observations, list):
            raise ValueError("scan preview is malformed")
        provenance = dict(preview.get("provenance") or {})
        provenance.update({"confirmed": True, "content_retained": False, "transient_content_deleted": True})
        assessment = self.service.record_assessment(
            learner_id=learner_id,
            source=import_row["source"],
            assessment_type=attempt.get("assessment_type", "practice_review"),
            external_id=import_row["external_id"],
            taken_at=attempt.get("taken_at"),
            is_official=True,
            total_score=attempt.get("total_score"),
            reading_writing_score=attempt.get("reading_writing_score"),
            math_score=attempt.get("math_score"),
            domain_evidence=attempt.get("domain_evidence") or {},
            import_provenance=provenance,
        )
        assessment_id = assessment["assessment"]["assessment_id"]
        events_created = 0
        for observation in observations:
            event = self.service.record_question_event(
                learner_id=learner_id,
                assessment_id=assessment_id,
                event_key=observation["event_key"],
                section=observation.get("section", "reading-writing"),
                module=observation.get("module"),
                question_locator=observation["question_locator"],
                result=observation["result"],
                provenance_type="official",
                time_seconds=observation.get("time_seconds"),
                time_source=observation.get("time_source"),
                confidence=observation.get("confidence"),
                flagged=observation.get("flagged", False),
                answer_changed=observation.get("answer_changed", False),
                selected_answer=observation.get("selected_answer"),
                correct_answer=observation.get("correct_answer"),
                provisional_skill=observation.get("provisional_skill"),
                abstract_context=observation.get("abstract_context") or {},
            )
            events_created += int(event.get("created", False))
        completed_preview = {key: value for key, value in preview.items() if key != "observations"}
        completed_preview.update(
            {
                "status": "complete",
                "assessment_id": assessment_id,
                "events_created": events_created,
                "content_retained": False,
                "transient_content_deleted": True,
            }
        )
        self.service.update_practice_import(
            learner_id=learner_id,
            import_id=import_id,
            cursor=cursor,
            expected_cursor=cursor,
            status="complete",
            preview=completed_preview,
        )
        return {
            "committed": True,
            "status": "complete",
            "import_id": import_id,
            "assessment_id": assessment_id,
            "events_created": events_created,
            "content_retained": False,
        }

    def discard_scan(self, *, learner_id: str, import_id: str, confirm: bool) -> dict[str, Any]:
        return self.service.discard_practice_import(learner_id, import_id, confirm=confirm)

    def _guard_page(self, auth: ChromeScanAuthorization, snapshot: ChromePageSnapshot) -> str:
        if snapshot.discarded:
            raise ScanBlocked("snapshot_already_discarded")
        if snapshot.page_index >= auth.max_pages:
            raise ScanBlocked("page_limit_exceeded")
        host = auth.validate_url(snapshot.url)
        structured = json.dumps(
            {"attempt": snapshot.attempt, "questions": snapshot.questions},
            ensure_ascii=False,
            separators=(",", ":"),
        )
        raise_for_unsafe_page(
            title=snapshot.title,
            visible_text=f"{snapshot.url}\n{snapshot.visible_text}\n{structured}",
        )
        return host

    def _derive_page(self, snapshot: ChromePageSnapshot) -> tuple[dict[str, Any], list[dict[str, Any]], list[str]]:
        attempt = self._normalize_attempt(snapshot.attempt)
        observations: list[dict[str, Any]] = []
        uncertainty: list[str] = []
        seen: set[str] = set()
        for raw in snapshot.questions:
            normalized = self._normalize_question(raw)
            if normalized is None:
                uncertainty.append("question_result_not_visible")
                continue
            if normalized["event_key"] in seen:
                continue
            seen.add(normalized["event_key"])
            observations.append(normalized)
        if not observations:
            uncertainty.append("question_results_not_visible")
        return attempt, observations, sorted(set(uncertainty))

    def _normalize_attempt(self, raw: dict[str, Any]) -> dict[str, Any]:
        ensure_safe_metadata(raw)
        attempt_id = validate_identifier(raw.get("attempt_id"), "attempt_id")
        result: dict[str, Any] = {
            "attempt_id": attempt_id,
            "assessment_type": _safe_scalar(raw.get("assessment_type", "practice_review"), "assessment_type", maximum=80),
        }
        taken_at = raw.get("taken_at")
        if taken_at is not None:
            result["taken_at"] = _safe_scalar(taken_at, "taken_at", maximum=80)
        result["total_score"] = _optional_score(raw.get("total_score"), "total_score", 400, 1600)
        result["reading_writing_score"] = _optional_score(raw.get("reading_writing_score"), "reading_writing_score", 200, 800)
        result["math_score"] = _optional_score(raw.get("math_score"), "math_score", 200, 800)
        result["domain_evidence"] = _optional_scalar_map(raw.get("domain_evidence"), "domain_evidence")
        return result

    def _normalize_question(self, raw: dict[str, Any]) -> dict[str, Any] | None:
        ensure_safe_metadata(raw)
        if set(raw) - _ALLOWED_QUESTION_KEYS:
            # Unknown fields are ignored after the page-level forbidden-key
            # check; this prevents an adapter from persisting future content.
            raw = {key: value for key, value in raw.items() if key in _ALLOWED_QUESTION_KEYS}
        locator_value = raw.get("question_locator")
        if locator_value is None:
            return None
        locator = validate_identifier(locator_value, "question_locator")
        event_key = validate_identifier(raw.get("event_key", locator), "event_key")
        result = validate_result(raw.get("result")) if raw.get("result") is not None else None
        if result is None:
            return None
        time_seconds = raw.get("time_seconds")
        if time_seconds is not None:
            if not isinstance(time_seconds, (int, float)) or isinstance(time_seconds, bool) or not 0 <= time_seconds <= 3600:
                raise ValueError("time_seconds is outside the allowed range")
            time_seconds = float(time_seconds)
        confidence = raw.get("confidence")
        if confidence is not None and (not isinstance(confidence, int) or isinstance(confidence, bool) or not 1 <= confidence <= 5):
            raise ValueError("confidence must be between 1 and 5")
        time_source = raw.get("time_source")
        if time_source is not None:
            time_source = _safe_scalar(time_source, "time_source", maximum=80)
        section = _safe_scalar(raw.get("section", "reading-writing"), "section", maximum=80)
        module = raw.get("module")
        if module is not None:
            module = _safe_scalar(module, "module", maximum=80)
        provisional_skill = raw.get("provisional_skill")
        if provisional_skill is not None:
            provisional_skill = _safe_scalar(provisional_skill, "provisional_skill", maximum=120)
        return {
            "event_key": event_key,
            "question_locator": locator,
            "section": section,
            "module": module,
            "result": result,
            "time_seconds": time_seconds,
            "time_source": time_source,
            "confidence": confidence,
            "flagged": raw.get("flagged") is True,
            "answer_changed": raw.get("answer_changed") is True,
            "selected_answer": _optional_answer(raw.get("selected_answer"), "selected_answer"),
            "correct_answer": _optional_answer(raw.get("correct_answer"), "correct_answer"),
            "provisional_skill": provisional_skill,
            "abstract_context": _optional_scalar_map(raw.get("abstract_context"), "abstract_context"),
        }

    def _build_preview(
        self,
        *,
        auth: ChromeScanAuthorization,
        snapshot: ChromePageSnapshot,
        attempt: dict[str, Any],
        observations: list[dict[str, Any]],
        uncertainty: list[str],
        pages_seen: int,
        existing: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        host = auth.validate_url(snapshot.url)
        counts = Counter(item["result"] for item in observations)
        provenance = dict((existing or {}).get("provenance") or {})
        provenance.update(
            {
                "mode": "user_authorized_read_only_chrome",
                "bridge": auth.bridge_name,
                "source": auth.source,
                "approved_host": host,
                "read_only": True,
                "prompt_injection_checks": "passed",
                "content_retained": False,
            }
        )
        preview = {
            "schema_version": 1,
            "status": "preview",
            "attempt": attempt,
            "attempt_id": attempt["attempt_id"],
            "question_count": len(observations),
            "result_counts": {result: counts.get(result, 0) for result in QUESTION_RESULTS if counts.get(result, 0)},
            "pages_seen": pages_seen,
            "uncertainty": sorted(set(uncertainty)),
            "provenance": provenance,
            "content_retained": False,
            "transient_content_deleted": True,
            "observations": observations,
        }
        ensure_safe_metadata(preview)
        return preview

    @staticmethod
    def _merge_observations(existing: Any, incoming: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not isinstance(existing, list):
            raise ValueError("stored scan observations are malformed")
        merged: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in [*existing, *incoming]:
            if not isinstance(item, dict) or not isinstance(item.get("event_key"), str):
                raise ValueError("stored scan observation is malformed")
            if item["event_key"] in seen:
                continue
            seen.add(item["event_key"])
            merged.append(dict(item))
        if len(merged) > 10_000:
            raise ValueError("scan contains too many question observations")
        return merged

    def _validate_cursor(self, import_row: dict[str, Any], import_id: str, cursor: str) -> ScanCursor:
        if import_row.get("cursor") != cursor:
            raise CursorError("cursor_stale_or_mismatched")
        state = ScanCursor.decode(cursor)
        if state.import_id != import_id:
            raise CursorError("cursor_import_mismatch")
        return state

    def _mark_blocked(self, learner_id: str, import_id: str, cursor: str, error: ScanBlocked) -> None:
        try:
            row = self.service.get_practice_import(learner_id, import_id)
            if row.get("cursor") != cursor or row.get("status") == "complete":
                return
            self.service.update_practice_import(
                learner_id=learner_id,
                import_id=import_id,
                cursor=cursor,
                expected_cursor=cursor,
                status="blocked",
                preview={
                    "schema_version": 1,
                    "status": "blocked",
                    "block_reasons": list(error.reasons),
                    "content_retained": False,
                    "transient_content_deleted": True,
                },
            )
        except Exception:
            # The original safe block reason is more useful than a secondary
            # persistence error and never includes page content.
            return

    @staticmethod
    def _response(import_row: dict[str, Any], *, has_more: bool, existing: bool) -> dict[str, Any]:
        preview = dict(import_row.get("preview") or {})
        public_preview = {key: value for key, value in preview.items() if key not in {"observations", "attempt"}}
        public_preview["observation_count"] = int(preview.get("question_count", 0))
        public_preview["has_more"] = has_more
        return {
            "status": import_row.get("status", "preview"),
            "requires_confirmation": import_row.get("status") == "preview",
            "existing": existing,
            "import_id": import_row["import_id"],
            "cursor": import_row.get("cursor"),
            "preview": public_preview,
        }
