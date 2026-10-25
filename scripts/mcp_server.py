#!/usr/bin/env python3
"""Minimal stdio MCP companion for the local OpenSAT service."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from opensat import LabService  # noqa: E402
from opensat.practice_scan import ChromeReadOnlyAdapter  # noqa: E402


SERVER_INFO = {"name": "opensat-local", "version": "0.1.0"}


def _schema(properties: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    return {"type": "object", "properties": properties, "required": required or []}


TOOL_DEFINITIONS = [
    {"name": "get_capabilities", "description": "Report available local, browser, and provider capabilities.", "inputSchema": _schema({})},
    {"name": "initialize_learner", "description": "Create an inspectable bilingual learner profile.", "inputSchema": _schema({"preferred_language": {"type": "string"}, "explanation_mode": {"type": "string"}, "reading_writing_score": {"type": ["integer", "null"]}, "math_score": {"type": ["integer", "null"]}, "total_score": {"type": ["integer", "null"]}, "test_date": {"type": ["string", "null"]}}, ["preferred_language"])},
    {"name": "get_learner_profile", "description": "Read one learner profile.", "inputSchema": _schema({"learner_id": {"type": "string"}}, ["learner_id"])},
    {"name": "update_learner_preferences", "description": "Merge durable practice-presentation preferences, test date, or session length into one learner profile.", "inputSchema": _schema({"learner_id": {"type": "string"}, "practice_preferences": {"type": ["object", "null"]}, "test_date": {"type": ["string", "null"]}, "session_length_preference": {"type": ["integer", "null"], "minimum": 1, "maximum": 30}}, ["learner_id"])},
    {"name": "record_assessment", "description": "Store a manual or reviewed assessment summary without official question content.", "inputSchema": _schema({"learner_id": {"type": "string"}, "source": {"type": "string"}, "assessment_type": {"type": "string"}, "external_id": {"type": "string"}, "is_official": {"type": "boolean"}, "total_score": {"type": ["integer", "null"]}, "reading_writing_score": {"type": ["integer", "null"]}, "math_score": {"type": ["integer", "null"]}, "domain_evidence": {"type": "object"}, "import_provenance": {"type": "object"}}, ["learner_id", "source", "assessment_type", "external_id", "is_official"])},
    {"name": "list_assessments", "description": "List persisted assessment summaries.", "inputSchema": _schema({"learner_id": {"type": "string"}}, ["learner_id"])},
    {"name": "begin_practice_import", "description": "Create or resume a low-level reviewable import preview without storing page content.", "inputSchema": _schema({"learner_id": {"type": "string"}, "source": {"type": "string"}, "external_id": {"type": "string"}, "preview": {"type": "object"}, "cursor": {"type": ["string", "null"]}}, ["learner_id", "source", "external_id", "preview"])},
    {"name": "update_practice_import", "description": "Advance or pause a safe import cursor without storing page content.", "inputSchema": _schema({"learner_id": {"type": "string"}, "import_id": {"type": "string"}, "cursor": {"type": ["string", "null"]}, "status": {"type": "string"}, "preview": {"type": ["object", "null"]}}, ["learner_id", "import_id", "status"])},
    {"name": "get_practice_import", "description": "Read one import preview and its current resumable cursor.", "inputSchema": _schema({"learner_id": {"type": "string"}, "import_id": {"type": "string"}}, ["learner_id", "import_id"])},
    {"name": "begin_chrome_practice_scan", "description": "Inspect one user-authorized, read-only Chrome review snapshot and create a metadata-only import preview.", "inputSchema": _schema({"learner_id": {"type": "string"}, "authorization": {"type": "object"}, "page": {"type": "object"}}, ["learner_id", "authorization", "page"])},
    {"name": "resume_chrome_practice_scan", "description": "Resume a read-only Chrome scan with the exact current opaque cursor; stale cursors and scope changes are rejected.", "inputSchema": _schema({"learner_id": {"type": "string"}, "import_id": {"type": "string"}, "cursor": {"type": "string"}, "authorization": {"type": "object"}, "page": {"type": "object"}}, ["learner_id", "import_id", "cursor", "authorization", "page"])},
    {"name": "commit_chrome_practice_scan", "description": "Persist only derived assessment and question metadata after explicit confirmation; transient page content is never committed.", "inputSchema": _schema({"learner_id": {"type": "string"}, "import_id": {"type": "string"}, "cursor": {"type": "string"}, "confirm": {"type": "boolean"}}, ["learner_id", "import_id", "cursor", "confirm"])},
    {"name": "discard_chrome_practice_scan", "description": "Delete an uncommitted Chrome scan preview and cursor after explicit confirmation.", "inputSchema": _schema({"learner_id": {"type": "string"}, "import_id": {"type": "string"}, "confirm": {"type": "boolean"}}, ["learner_id", "import_id", "confirm"])},
    {"name": "record_question_event", "description": "Store an incorrect, omitted, or diagnostically important response using derived metadata only, including an optional post-answer pre-feedback apparent-difficulty tag.", "inputSchema": _schema({"learner_id": {"type": "string"}, "assessment_id": {"type": "string"}, "event_key": {"type": "string"}, "section": {"type": "string"}, "question_locator": {"type": "string"}, "result": {"type": "string"}, "provenance_type": {"type": "string"}, "module": {"type": ["string", "null"]}, "time_seconds": {"type": ["number", "null"]}, "confidence": {"type": ["integer", "null"]}, "apparent_difficulty": {"type": ["string", "null"], "enum": ["routine", "noticeable", "intimidating", None]}, "selected_answer": {"type": ["string", "null"]}, "correct_answer": {"type": ["string", "null"]}, "provisional_skill": {"type": ["string", "null"]}, "abstract_context": {"type": "object"}}, ["learner_id", "assessment_id", "event_key", "section", "question_locator", "result", "provenance_type"])},
    {"name": "record_generated_item", "description": "Persist synthetic-item provenance and exposure history with the required simulated label.", "inputSchema": _schema({"learner_id": {"type": "string"}, "provider": {"type": "string"}, "target_skill": {"type": "string"}, "target_error_signature": {"type": ["string", "null"]}, "intended_difficulty": {"type": "string"}, "validation_status": {"type": "string"}, "item_version": {"type": "string"}, "specification": {"type": "object"}, "exposure_history": {"type": "array"}}, ["learner_id", "provider", "target_skill", "intended_difficulty", "validation_status", "item_version", "specification"])},
    {"name": "record_reasoning_response", "description": "Record one targeted autopsy response.", "inputSchema": _schema({"learner_id": {"type": "string"}, "event_id": {"type": "string"}, "prompt_id": {"type": "string"}, "response_text": {"type": "string"}, "confidence": {"type": ["integer", "null"]}}, ["learner_id", "event_id", "prompt_id", "response_text"])},
    {"name": "record_diagnostic_hypothesis", "description": "Store an observed fact and a clearly labeled provisional hypothesis.", "inputSchema": _schema({"learner_id": {"type": "string"}, "event_id": {"type": ["string", "null"]}, "observed_fact": {"type": "string"}, "hypothesis": {"type": "string"}, "confidence": {"type": "number"}, "status": {"type": "string"}, "supporting_event_ids": {"type": "array"}, "contradicting_evidence": {"type": "array"}}, ["learner_id", "observed_fact", "hypothesis", "confidence"])},
    {"name": "confirm_error_signature", "description": "Advance a named error signature only when evidence supports the requested status.", "inputSchema": _schema({"learner_id": {"type": "string"}, "code": {"type": "string"}, "status": {"type": "string"}, "evidence_event_ids": {"type": "array"}, "notes": {"type": ["string", "null"]}}, ["learner_id", "code", "status", "evidence_event_ids"])},
    {"name": "get_review_queue", "description": "Read open reviews and transfer distance.", "inputSchema": _schema({"learner_id": {"type": "string"}, "due_only": {"type": "boolean"}}, ["learner_id"])},
    {"name": "get_session_start_context", "description": "Read the local clock and any review sessions due or overdue when practice starts.", "inputSchema": _schema({"learner_id": {"type": "string"}, "section": {"type": "string", "enum": ["reading-writing"]}, "limit": {"type": "integer", "minimum": 1, "maximum": 5}}, ["learner_id"])},
    {"name": "get_session_state", "description": "Read a learner-owned session or the latest incomplete session.", "inputSchema": _schema({"learner_id": {"type": "string"}, "session_id": {"type": ["string", "null"]}}, ["learner_id"])},
    {"name": "get_difficulty_recommendation", "description": "Recommend future Reading and Writing difficulty from band, correctness, timing, confidence, and response stability.", "inputSchema": _schema({"learner_id": {"type": "string"}, "section": {"type": "string", "enum": ["reading-writing"]}, "limit": {"type": "integer", "minimum": 4, "maximum": 50}}, ["learner_id"])},
    {"name": "get_on_demand_recommendations", "description": "Recommend optional issue-specific follow-up sessions from recent mistakes, slow or fragile correctness, and open reviews.", "inputSchema": _schema({"learner_id": {"type": "string"}, "section": {"type": "string", "enum": ["reading-writing"]}, "limit": {"type": "integer", "minimum": 1, "maximum": 5}}, ["learner_id"])},
    {"name": "build_daily_session", "description": "Build a band-adaptive 20-minute session in one or two coherent persistence activities.", "inputSchema": _schema({"learner_id": {"type": "string"}, "band": {"type": ["string", "null"]}, "session_mode": {"type": "string", "enum": ["default", "strategy_trial"]}}, ["learner_id"])},
    {"name": "record_visual_submission", "description": "Validate and idempotently persist a content-free Visualize section against its transient manifest.", "inputSchema": _schema({"learner_id": {"type": "string"}, "payload": {"type": "object"}, "manifest": {"type": "object"}}, ["learner_id", "payload", "manifest"])},
    {"name": "record_activity_result", "description": "Record a session activity and update completion.", "inputSchema": _schema({"learner_id": {"type": "string"}, "session_id": {"type": "string"}, "activity_type": {"type": "string"}, "outcome": {"type": "string"}, "actual_minutes": {"type": "integer"}, "fatigue": {"type": ["string", "null"]}, "completed": {"type": "boolean"}}, ["learner_id", "session_id", "activity_type", "outcome", "actual_minutes"])},
    {"name": "begin_strategy_trial", "description": "Start a paired or counterbalanced strategy trial.", "inputSchema": _schema({"learner_id": {"type": "string"}, "strategy": {"type": "string"}, "question_type": {"type": "string"}, "condition_a": {"type": "object"}, "condition_b": {"type": "object"}}, ["learner_id", "strategy", "question_type", "condition_a", "condition_b"])},
    {"name": "record_strategy_trial_result", "description": "Add one strategy-trial observation without overclaiming from a tiny sample.", "inputSchema": _schema({"learner_id": {"type": "string"}, "trial_id": {"type": "string"}, "condition": {"type": "string"}, "correct": {"type": "boolean"}, "time_seconds": {"type": ["number", "null"]}, "confidence": {"type": ["integer", "null"]}, "reread_count": {"type": "integer"}}, ["learner_id", "trial_id", "condition", "correct"])},
    {"name": "get_progress_summary", "description": "Summarize evidence, not an official score prediction.", "inputSchema": _schema({"learner_id": {"type": "string"}}, ["learner_id"])},
    {"name": "export_learner_model", "description": "Write an inspectable local JSON export outside the repository.", "inputSchema": _schema({"learner_id": {"type": "string"}, "output_path": {"type": ["string", "null"]}}, ["learner_id"])},
    {"name": "import_learner_model", "description": "Merge a validated learner-model export.", "inputSchema": _schema({"input_path": {"type": "string"}}, ["input_path"])},
    {"name": "delete_learner_data", "description": "Delete one learner only after explicit confirmation.", "inputSchema": _schema({"learner_id": {"type": "string"}, "confirm": {"type": "boolean"}}, ["learner_id", "confirm"])},
]


def _call(service: LabService, name: str, args: dict[str, Any]) -> Any:
    browser_adapter = ChromeReadOnlyAdapter(service)
    methods: dict[str, Callable[..., Any]] = {
        "get_capabilities": service.get_capabilities,
        "initialize_learner": service.initialize_learner,
        "get_learner_profile": service.get_learner_profile,
        "update_learner_preferences": service.update_learner_preferences,
        "record_assessment": service.record_assessment,
        "list_assessments": service.list_assessments,
        "begin_practice_import": service.begin_practice_import,
        "update_practice_import": service.update_practice_import,
        "get_practice_import": lambda **kw: service.get_practice_import(kw["learner_id"], kw["import_id"]),
        "begin_chrome_practice_scan": browser_adapter.begin_scan,
        "resume_chrome_practice_scan": browser_adapter.resume_scan,
        "commit_chrome_practice_scan": browser_adapter.commit_scan,
        "discard_chrome_practice_scan": browser_adapter.discard_scan,
        "record_question_event": service.record_question_event,
        "record_generated_item": service.record_generated_item,
        "record_reasoning_response": service.record_reasoning_response,
        "record_diagnostic_hypothesis": service.record_diagnostic_hypothesis,
        "confirm_error_signature": service.confirm_error_signature,
        "get_review_queue": service.get_review_queue,
        "get_session_start_context": service.get_session_start_context,
        "get_session_state": service.get_session_state,
        "get_difficulty_recommendation": service.get_difficulty_recommendation,
        "get_on_demand_recommendations": service.get_on_demand_recommendations,
        "build_daily_session": service.build_daily_session,
        "record_visual_submission": service.record_visual_submission,
        "record_activity_result": service.record_activity_result,
        "begin_strategy_trial": service.begin_strategy_trial,
        "record_strategy_trial_result": service.record_strategy_trial_result,
        "get_progress_summary": service.get_progress_summary,
        "export_learner_model": lambda **kw: service.export_learner_model(kw["learner_id"], kw.get("output_path")),
        "import_learner_model": service.import_learner_model,
        "delete_learner_data": service.delete_learner_data,
    }
    if name not in methods:
        raise ValueError(f"Unknown tool: {name}")
    return methods[name](**args)


def _reply(request_id: Any, result: Any = None, error: dict[str, Any] | None = None) -> dict[str, Any]:
    response: dict[str, Any] = {"jsonrpc": "2.0", "id": request_id}
    if error is not None:
        response["error"] = error
    else:
        response["result"] = result
    return response


def handle(request: dict[str, Any], service: LabService) -> dict[str, Any] | None:
    method = request.get("method")
    request_id = request.get("id")
    if method in {"notifications/initialized", "notifications/cancelled"}:
        return None
    if method == "initialize":
        return _reply(request_id, {"protocolVersion": "2025-06-18", "capabilities": {"tools": {"listChanged": False}}, "serverInfo": SERVER_INFO})
    if method == "ping":
        return _reply(request_id, {})
    if method == "tools/list":
        return _reply(request_id, {"tools": TOOL_DEFINITIONS})
    if method == "tools/call":
        params = request.get("params") or {}
        try:
            result = _call(service, params["name"], params.get("arguments") or {})
            return _reply(request_id, {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False, indent=2)}], "structuredContent": result})
        except Exception as exc:  # MCP must return a structured tool error, not crash the session.
            return _reply(request_id, {"content": [{"type": "text", "text": str(exc)}], "isError": True})
    if request_id is not None:
        return _reply(request_id, error={"code": -32601, "message": f"Method not found: {method}"})
    return None


def main() -> int:
    service = LabService()
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            request = json.loads(line)
            response = handle(request, service)
            if response is not None:
                sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
                sys.stdout.flush()
        except Exception as exc:
            sys.stdout.write(json.dumps(_reply(None, error={"code": -32700, "message": str(exc)}), ensure_ascii=False) + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
