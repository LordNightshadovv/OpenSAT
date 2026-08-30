#!/usr/bin/env python3
"""Small local CLI for the OpenSAT vertical slice."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from opensat import LabService  # noqa: E402
from opensat.diagnosis.autopsy import build_autopsy  # noqa: E402


def demo(service: LabService) -> dict:
    learner = service.initialize_learner(
        preferred_language="bilingual",
        explanation_mode="bilingual",
        reading_writing_score=680,
        total_score=1350,
        test_date="2026-11-07",
    )
    learner_id = learner["learner"]["learner_id"]
    official = service.record_assessment(
        learner_id=learner_id,
        source="manual",
        assessment_type="baseline",
        external_id="synthetic-manual-official-summary-001",
        is_official=True,
        total_score=1350,
        reading_writing_score=680,
        math_score=670,
        domain_evidence={"reading_writing": {"expression_of_ideas": "needs_review"}},
        import_provenance={"mode": "manual", "content_stored": False},
    )
    synthetic = service.record_assessment(
        learner_id=learner_id,
        source="manual",
        assessment_type="synthetic_diagnostic_fixture",
        external_id="synthetic-fixture-assessment-001",
        is_official=False,
        domain_evidence={"fixture": True},
        import_provenance={"mode": "local_fixture"},
    )
    event = service.record_question_event(
        learner_id=learner_id,
        assessment_id=synthetic["assessment"]["assessment_id"],
        event_key="synthetic-module-1-question-07",
        section="reading-writing",
        module="module-1",
        question_locator="synthetic-fixture-07",
        result="incorrect",
        provenance_type="simulated",
        confidence=4,
        time_seconds=71,
        selected_answer="B",
        correct_answer="D",
        provisional_skill="rhetorical-synthesis",
        abstract_context={"question_type": "rhetorical_synthesis", "fixture": True},
    )
    event_record = event["event"]
    autopsy = build_autopsy(event_record)
    service.record_reasoning_response(
        learner_id=learner_id,
        event_id=event_record["event_id"],
        prompt_id="what_did_you_think_the_question_was_asking",
        response_text="I chose the option that sounded most complete before checking the exact goal.",
        confidence=4,
    )
    hypothesis = service.record_diagnostic_hypothesis(
        learner_id=learner_id,
        event_id=event_record["event_id"],
        observed_fact="The learner selected a broader-sounding option and reported high confidence.",
        hypothesis="The learner may be expanding the task scope before comparing the stem and notes.",
        confidence=0.45,
        supporting_event_ids=[event_record["event_id"]],
    )
    signature = service.confirm_error_signature(
        learner_id=learner_id,
        code="scope_expansion",
        status="provisional",
        evidence_event_ids=[event_record["event_id"]],
        notes="One synthetic event only; do not treat as recurring yet.",
    )
    session = service.build_daily_session(learner_id)
    service.record_activity_result(
        learner_id=learner_id,
        session_id=session["session_id"],
        activity_type="retrieval_check",
        outcome="Named the task goal before seeing options.",
        actual_minutes=3,
    )
    on_demand = service.get_on_demand_recommendations(learner_id)
    export = service.export_learner_model(learner_id)
    return {
        "learner_id": learner_id,
        "official_assessment_id": official["assessment"]["assessment_id"],
        "synthetic_event_id": event_record["event_id"],
        "autopsy": autopsy,
        "hypothesis": hypothesis,
        "signature": signature,
        "session": session,
        "on_demand_recommendations": on_demand,
        "export": export,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="OpenSAT local vertical slice")
    parser.add_argument("--data-dir", type=Path, help="Optional test/demo data directory outside the repository")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("capabilities")
    subparsers.add_parser("demo")

    export_parser = subparsers.add_parser("export")
    export_parser.add_argument("learner_id")
    export_parser.add_argument("--output", type=Path)

    delete_parser = subparsers.add_parser("delete")
    delete_parser.add_argument("learner_id")
    delete_parser.add_argument("--confirm", action="store_true")

    args = parser.parse_args()
    service = LabService(args.data_dir)
    if args.command == "capabilities":
        result = service.get_capabilities()
    elif args.command == "demo":
        result = demo(service)
    elif args.command == "export":
        result = service.export_learner_model(args.learner_id, args.output)
    else:
        result = service.delete_learner_data(args.learner_id, confirm=args.confirm)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
