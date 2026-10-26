from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from dataclasses import replace
from datetime import date
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from opensat import LabService
from opensat.domain.constants import PILOT_BANDS
from opensat.generation.pipeline import ItemSpecification, validate_candidate, validate_purpose_groups
from opensat.privacy.paths import ensure_data_layout
from opensat.scheduling.engine import build_daily_plan, next_review_date
from opensat.storage.database import connect
from opensat.visualize import validate_visual_submission


class VerticalSliceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(prefix="opensat-test-")
        self.data_dir = Path(self.temp_dir.name) / "runtime"
        self.service = LabService(self.data_dir)
        learner = self.service.initialize_learner(
            preferred_language="bilingual",
            explanation_mode="bilingual",
            reading_writing_score=680,
            math_score=670,
        )
        self.learner_id = learner["learner"]["learner_id"]
        assessment = self.service.record_assessment(
            learner_id=self.learner_id,
            source="manual",
            assessment_type="baseline",
            external_id="assessment-001",
            is_official=True,
            reading_writing_score=680,
            domain_evidence={"grammar": "synthetic summary"},
            import_provenance={"mode": "manual", "content_stored": False},
        )
        self.assessment_id = assessment["assessment"]["assessment_id"]

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def make_event(self, key: str, result: str = "incorrect", apparent_difficulty: str | None = None) -> dict:
        return self.service.record_question_event(
            learner_id=self.learner_id,
            assessment_id=self.assessment_id,
            event_key=key,
            section="reading-writing",
            module="module-1",
            question_locator=f"synthetic-{key}",
            result=result,
            provenance_type="simulated",
            confidence=4,
            apparent_difficulty=apparent_difficulty,
            time_seconds=72,
            selected_answer="B",
            correct_answer="D",
            provisional_skill="transitions",
            abstract_context={"fixture": True},
        )

    def test_runtime_data_is_outside_repository_and_schema_initializes(self) -> None:
        paths = ensure_data_layout(self.data_dir)
        self.assertNotIn(str(ROOT), str(paths.root))
        self.assertTrue(paths.database.exists())
        connection, _ = connect(self.data_dir)
        try:
            self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], 2)
            self.assertIsNotNone(connection.execute("SELECT 1 FROM learners LIMIT 1").fetchone())
        finally:
            connection.close()

    def test_migration_creates_backup_before_upgrade(self) -> None:
        paths = ensure_data_layout(self.data_dir / "migration")
        old = sqlite3.connect(paths.database)
        old.execute("PRAGMA user_version = 0")
        old.commit()
        old.close()
        connection, _ = connect(self.data_dir / "migration")
        connection.close()
        self.assertTrue(list(paths.backups.glob("opensat_pre_migration_v0_*.sqlite3")))

    def test_v1_migration_adds_apparent_difficulty_column(self) -> None:
        paths = ensure_data_layout(self.data_dir / "migration-v1")
        old = sqlite3.connect(paths.database)
        old.execute("CREATE TABLE question_events (event_id TEXT PRIMARY KEY)")
        old.execute("PRAGMA user_version = 1")
        old.commit()
        old.close()
        connection, _ = connect(self.data_dir / "migration-v1")
        try:
            columns = {row[1] for row in connection.execute("PRAGMA table_info(question_events)")}
            self.assertIn("apparent_difficulty", columns)
            self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], 2)
        finally:
            connection.close()
        self.assertTrue(list(paths.backups.glob("opensat_pre_migration_v1_*.sqlite3")))

    def test_assessment_and_question_event_imports_are_idempotent(self) -> None:
        duplicate_assessment = self.service.record_assessment(
            learner_id=self.learner_id,
            source="manual",
            assessment_type="baseline",
            external_id="assessment-001",
            is_official=True,
            reading_writing_score=680,
        )
        self.assertFalse(duplicate_assessment["created"])
        first = self.make_event("event-001")
        duplicate_event = self.make_event("event-001")
        self.assertTrue(first["created"])
        self.assertFalse(duplicate_event["created"])
        self.assertEqual(len(self.service.get_review_queue(self.learner_id)), 1)

    def test_question_event_persists_bounded_apparent_difficulty(self) -> None:
        event = self.make_event("appearance-001", apparent_difficulty="routine")
        self.assertEqual(event["event"]["apparent_difficulty"], "routine")
        with self.assertRaisesRegex(ValueError, "apparent_difficulty"):
            self.make_event("appearance-bad", apparent_difficulty="deceptive")

    def test_learner_practice_preferences_are_merged_and_bounded(self) -> None:
        updated = self.service.update_learner_preferences(
            learner_id=self.learner_id,
            test_date="2026-09-12",
            session_length_preference=20,
            practice_preferences={
                "purpose_groups": {"preferred_min": 3, "preferred_max": 4, "max_questions_per_group": 4},
                "difficulty_center": "hard",
            },
        )
        practice = updated["learner"]["accessibility_preferences"]["practice"]
        self.assertEqual(practice["purpose_groups"]["preferred_min"], 3)
        self.assertEqual(updated["learner"]["test_date"], "2026-09-12")
        with self.assertRaises(ValueError):
            self.service.update_learner_preferences(
                learner_id=self.learner_id,
                practice_preferences={"purpose_groups": {"preferred_min": 3, "preferred_max": 4, "max_questions_per_group": 5}},
            )

    def test_practice_import_cursor_and_generated_item_provenance(self) -> None:
        started = self.service.begin_practice_import(
            learner_id=self.learner_id,
            source="bluebook",
            external_id="attempt-001",
            preview={"attempt_found": True, "question_count": 0},
            cursor="page-1",
        )
        advanced = self.service.update_practice_import(
            learner_id=self.learner_id,
            import_id=started["import"]["import_id"],
            cursor="page-2",
            status="paused",
        )
        self.assertEqual(advanced["cursor"], "page-2")
        item = self.service.record_generated_item(
            learner_id=self.learner_id,
            provider="local-synthetic-fixture",
            target_skill="transitions",
            target_error_signature="qualifier_omission",
            intended_difficulty="medium",
            validation_status="approved",
            item_version="fixture-1",
            specification={"synthetic": True, "transfer_distance": "near"},
        )
        self.assertIn("Simulated SAT-style practice", item["simulated_label"])
        duplicate = self.service.record_generated_item(
            learner_id=self.learner_id,
            provider="local-synthetic-fixture",
            target_skill="transitions",
            target_error_signature="qualifier_omission",
            intended_difficulty="medium",
            validation_status="approved",
            item_version="fixture-1",
            specification={"synthetic": True, "transfer_distance": "near"},
        )
        self.assertFalse(duplicate["created"])
        self.assertEqual(duplicate["item_id"], item["item_id"])

    def test_persistence_boundary_rejects_secrets_and_official_content_fields(self) -> None:
        with self.assertRaises(ValueError):
            self.service.record_assessment(
                learner_id=self.learner_id,
                source="manual",
                assessment_type="bad",
                external_id="secret-attempt",
                is_official=True,
                import_provenance={"api_key": "never-store"},
            )
        with self.assertRaises(ValueError):
            self.make_event("bad-event")
            self.service.record_question_event(
                learner_id=self.learner_id,
                assessment_id=self.assessment_id,
                event_key="bad-event-2",
                section="reading-writing",
                question_locator="synthetic-bad",
                result="incorrect",
                provenance_type="official",
                abstract_context={"question_text": "not persisted"},
            )

    def test_export_excludes_secrets_and_official_content(self) -> None:
        event = self.make_event("export-event")
        self.service.record_reasoning_response(
            learner_id=self.learner_id,
            event_id=event["event"]["event_id"],
            prompt_id="what_did_you_think_the_question_was_asking",
            response_text="I followed the local wording cue.",
        )
        output = Path(self.temp_dir.name) / "exports" / "model.json"
        result = self.service.export_learner_model(self.learner_id, output)
        self.assertTrue(Path(result["path"]).exists())
        raw = output.read_text()
        self.assertNotIn("question_text", raw)
        self.assertNotIn("api_key", raw)
        payload = json.loads(raw)
        self.assertFalse(payload["content_boundary"]["official_content_persisted"])
        with self.assertRaises(ValueError):
            self.service.export_learner_model(self.learner_id, ROOT / "learner-data.json")

    def test_all_pilot_bands_produce_exactly_twenty_minutes(self) -> None:
        for band in PILOT_BANDS:
            plan = build_daily_plan(band)
            self.assertEqual(plan.planned_minutes, 20)
            self.assertEqual(sum(item.minutes for item in plan.activities), 20)
            self.assertLessEqual(len(plan.activities), 2)
        self.assertEqual(self.service.get_learner_profile(self.learner_id)["score_band_prior"], "650-690")
        session = self.service.build_daily_session(self.learner_id)
        first = self.service.record_activity_result(
            learner_id=self.learner_id,
            session_id=session["session_id"],
            activity_type="targeted_practice_block",
            outcome="completed",
            actual_minutes=18,
        )
        self.assertTrue(first["created"])
        retry = self.service.record_activity_result(
            learner_id=self.learner_id,
            session_id=session["session_id"],
            activity_type="targeted_practice_block",
            outcome="completed",
            actual_minutes=18,
        )
        self.assertFalse(retry["created"])
        with self.assertRaises(ValueError):
            self.service.record_activity_result(
                learner_id=self.learner_id,
                session_id=session["session_id"],
                activity_type="targeted_practice_block",
                outcome="conflicting retry",
                actual_minutes=17,
            )
        final = self.service.record_activity_result(
            learner_id=self.learner_id,
            session_id=session["session_id"],
            activity_type="review_reflection",
            outcome="completed",
            actual_minutes=2,
            fatigue="low",
            completed=True,
        )
        self.assertEqual(final["actual_minutes"], 20)
        self.assertTrue(self.service.get_session_state(self.learner_id, session_id=session["session_id"])["completed"])

    def test_strategy_mode_is_two_blocks_and_current_session_is_learner_owned(self) -> None:
        session = self.service.build_daily_session(self.learner_id, session_mode="strategy_trial")
        activities = session["plan"]["activities"]
        self.assertEqual([item["minutes"] for item in activities], [14, 6])
        self.assertEqual(
            [item["activity_type"] for item in activities],
            ["focused_diagnostic_block", "strategy_reflection_block"],
        )
        state = self.service.get_session_state(self.learner_id)
        self.assertEqual(state["session_id"], session["session_id"])
        other = self.service.initialize_learner(preferred_language="english")["learner"]["learner_id"]
        self.assertIsNone(self.service.get_session_state(other, session_id=session["session_id"]))

    def test_visual_submission_requires_manifest_scope_and_content_free_payload(self) -> None:
        session = self.service.build_daily_session(self.learner_id, session_mode="strategy_trial")
        manifest = {
            "manifest_id": "manifest-fixture",
            "session_id": session["session_id"],
            "learner_id": self.learner_id,
            "sections": {"diagnostic_core": ["item-01"], "strategy_and_reflection": ["item-02"]},
            "items": {
                "item-01": {
                    "correct_answer": "A", "provider": "local-synthetic-fixture",
                    "target_skill": "evidence_selection", "target_error_signature": "weak_evidence_threshold",
                    "intended_difficulty": "hard", "validation_status": "approved", "item_version": "fixture-visual-01",
                },
                "item-02": {
                    "correct_answer": "D", "provider": "local-synthetic-fixture",
                    "target_skill": "rhetorical_synthesis", "target_error_signature": "task_goal_drift",
                    "intended_difficulty": "hard", "validation_status": "approved", "item_version": "fixture-visual-02",
                    "strategy_condition": "B",
                },
            },
        }
        payload = {
            "schema_version": "1.0",
            "surface": "visualize",
            "manifest_id": "manifest-fixture",
            "session_id": session["session_id"],
            "submission_id": f"{session['session_id']}:diagnostic_core",
            "section": "diagnostic_core",
            "answers": [{
                "item_id": "item-01",
                "selected_answer": "A",
                "confidence": 4,
                "time_seconds": 42,
                "answer_changed": False,
                "almost_choice": None,
                "help_used": False,
            }],
            "actual_minutes": 14,
            "fatigue": None,
            "reflection": None,
        }
        validated = validate_visual_submission(
            payload,
            learner_id=self.learner_id,
            session_state=self.service.get_session_state(self.learner_id, session_id=session["session_id"]),
            manifest=manifest,
        )
        self.assertEqual(validated["status"], "validated_not_persisted")
        self.assertEqual(validated["resolved_items"][0]["correct_answer"], "A")
        with self.assertRaises(ValueError):
            validate_visual_submission(
                {**payload, "question_text": "must not cross the boundary"},
                learner_id=self.learner_id,
                session_state=self.service.get_session_state(self.learner_id, session_id=session["session_id"]),
                manifest=manifest,
            )
        with self.assertRaises(ValueError):
            validate_visual_submission(
                {**payload, "submission_id": "unstable"},
                learner_id=self.learner_id,
                session_state=self.service.get_session_state(self.learner_id, session_id=session["session_id"]),
                manifest=manifest,
            )

    def test_visual_submission_v12_requires_timer_and_apparent_difficulty(self) -> None:
        session = self.service.build_daily_session(self.learner_id, session_mode="strategy_trial")
        manifest = {
            "manifest_id": "manifest-timer-fixture",
            "session_id": session["session_id"],
            "learner_id": self.learner_id,
            "sections": {"diagnostic_core": ["item-timer"], "strategy_and_reflection": ["item-final"]},
            "items": {
                "item-timer": {
                    "correct_answer": "A", "provider": "local-synthetic-fixture",
                    "target_skill": "sentence_boundaries", "target_error_signature": "structural_misparse",
                    "intended_difficulty": "hard", "validation_status": "approved",
                    "item_version": "timer-01", "slow_threshold_seconds": 45,
                },
                "item-final": {
                    "correct_answer": "B", "provider": "local-synthetic-fixture",
                    "target_skill": "transitions", "target_error_signature": "task_goal_drift",
                    "intended_difficulty": "hard", "validation_status": "approved", "item_version": "timer-02",
                },
            },
        }
        answer = {
            "item_id": "item-timer", "selected_answer": "A", "confidence": 4,
            "apparent_difficulty": "routine",
            "time_seconds": 18.25, "answer_changed": False, "almost_choice": None,
            "help_used": False, "timing_source": "visualize_monotonic_timer", "timer_state": "stopped",
        }
        payload = {
            "schema_version": "1.2", "surface": "visualize", "manifest_id": manifest["manifest_id"],
            "session_id": session["session_id"], "submission_id": f"{session['session_id']}:diagnostic_core",
            "section": "diagnostic_core", "answers": [answer], "actual_minutes": 1,
            "fatigue": None, "reflection": None,
        }
        validated = validate_visual_submission(
            payload,
            learner_id=self.learner_id,
            session_state=self.service.get_session_state(self.learner_id, session_id=session["session_id"]),
            manifest=manifest,
        )
        self.assertEqual(validated["status"], "validated_not_persisted")
        for bad_answer in (
            {**answer, "timer_state": "locked"},
            {**answer, "timer_state": "running"},
            {**answer, "timing_source": "manual"},
            {**answer, "time_seconds": 0},
            {**answer, "apparent_difficulty": "deceptive"},
        ):
            with self.assertRaises(ValueError):
                validate_visual_submission(
                    {**payload, "answers": [bad_answer]},
                    learner_id=self.learner_id,
                    session_state=self.service.get_session_state(self.learner_id, session_id=session["session_id"]),
                    manifest=manifest,
                )

        persisted = self.service.record_visual_submission(
            learner_id=self.learner_id,
            payload=payload,
            manifest=manifest,
        )
        self.assertTrue(persisted["persisted"])
        exported = self.service.export_learner_model(self.learner_id)
        export_payload = json.loads(Path(exported["path"]).read_text())
        timer_event = next(
            item for item in export_payload["records"]["question_events"]
            if item["question_locator"] == "item-timer"
        )
        self.assertEqual(timer_event["time_source"], "visualize_monotonic_timer")
        self.assertEqual(timer_event["apparent_difficulty"], "routine")
        self.assertEqual(timer_event["abstract_context"]["slow_threshold_seconds"], 45)

    def test_visual_submission_preserves_direct_archive_provenance_without_generated_item(self) -> None:
        session = self.service.build_daily_session(self.learner_id, session_mode="strategy_trial")
        locator = "local-archive:2026-09-apac:m2:q11"
        direct_item = {
            "correct_answer": "B",
            "provider": "local-past-paper-archive",
            "target_skill": "quantitative_evidence",
            "target_error_signature": "task_goal_drift",
            "intended_difficulty": "hard",
            "validation_status": "reviewed",
            "item_version": "PA-F3-02",
            "provenance_type": "publisher_reconstruction",
            "source_label": "Publisher-reconstructed past-paper question",
            "source_locator": locator,
        }
        manifest = {
            "manifest_id": "manifest-direct-archive",
            "session_id": session["session_id"],
            "learner_id": self.learner_id,
            "sections": {"diagnostic_core": ["direct-01"], "strategy_and_reflection": ["simulated-final"]},
            "items": {
                "direct-01": direct_item,
                "simulated-final": {
                    "correct_answer": "A", "provider": "local-synthetic-fixture",
                    "target_skill": "transitions", "target_error_signature": "task_goal_drift",
                    "intended_difficulty": "hard", "validation_status": "approved",
                    "item_version": "direct-fixture-final",
                },
            },
        }
        answer = {
            "item_id": "direct-01", "selected_answer": "B", "confidence": 5,
            "apparent_difficulty": "routine", "time_seconds": 31,
            "answer_changed": False, "almost_choice": "C", "help_used": False,
            "timing_source": "visualize_monotonic_timer", "timer_state": "stopped",
        }
        payload = {
            "schema_version": "1.2", "surface": "visualize", "manifest_id": manifest["manifest_id"],
            "session_id": session["session_id"], "submission_id": f"{session['session_id']}:diagnostic_core",
            "section": "diagnostic_core", "answers": [answer], "actual_minutes": 1,
            "fatigue": None, "reflection": None,
        }

        with self.assertRaises(ValueError):
            validate_visual_submission(
                payload,
                learner_id=self.learner_id,
                session_state=self.service.get_session_state(self.learner_id, session_id=session["session_id"]),
                manifest={
                    **manifest,
                    "items": {
                        **manifest["items"],
                        "direct-01": {**direct_item, "source_label": "Official College Board question"},
                    },
                },
            )

        persisted = self.service.record_visual_submission(
            learner_id=self.learner_id,
            payload=payload,
            manifest=manifest,
        )
        self.assertTrue(persisted["persisted"])
        exported = self.service.export_learner_model(self.learner_id)
        export_payload = json.loads(Path(exported["path"]).read_text())
        event = next(
            item for item in export_payload["records"]["question_events"]
            if item["question_locator"] == locator
        )
        self.assertEqual(event["provenance_type"], "publisher_reconstruction")
        self.assertEqual(
            event["abstract_context"]["source_label"],
            "Publisher-reconstructed past-paper question",
        )
        self.assertFalse(any(
            item["item_version"] == "PA-F3-02"
            for item in export_payload["records"].get("generated_items", [])
        ))

    def test_visual_submission_persists_each_section_once_and_keeps_strategy_inconclusive(self) -> None:
        session = self.service.build_daily_session(self.learner_id, session_mode="strategy_trial")
        manifest = {
            "manifest_id": "manifest-persist-fixture",
            "session_id": session["session_id"],
            "learner_id": self.learner_id,
            "sections": {"diagnostic_core": ["item-01"], "strategy_and_reflection": ["item-02", "item-03"]},
            "items": {
                "item-01": {
                    "correct_answer": "A", "provider": "local-synthetic-fixture", "target_skill": "evidence_selection",
                    "target_error_signature": "weak_evidence_threshold", "intended_difficulty": "hard",
                    "validation_status": "approved", "item_version": "persist-01", "slow_threshold_seconds": 60,
                },
                "item-02": {
                    "correct_answer": "B", "provider": "local-synthetic-fixture", "target_skill": "rhetorical_synthesis",
                    "target_error_signature": "premature_answer_selection", "intended_difficulty": "hard",
                    "validation_status": "approved", "item_version": "persist-02", "strategy_condition": "A",
                },
                "item-03": {
                    "correct_answer": "D", "provider": "local-synthetic-fixture", "target_skill": "rhetorical_synthesis",
                    "target_error_signature": "premature_answer_selection", "intended_difficulty": "hard",
                    "validation_status": "approved", "item_version": "persist-03", "strategy_condition": "B",
                },
            },
        }

        def answer(item_id: str, selected: str) -> dict[str, object]:
            return {
                "item_id": item_id, "selected_answer": selected, "confidence": 4,
                "time_seconds": 42, "answer_changed": False, "almost_choice": None, "help_used": False,
            }

        core = {
            "schema_version": "1.0", "surface": "visualize", "manifest_id": manifest["manifest_id"],
            "session_id": session["session_id"], "submission_id": f"{session['session_id']}:diagnostic_core",
            "section": "diagnostic_core", "answers": [answer("item-01", "A")],
            "actual_minutes": 14, "fatigue": None, "reflection": None,
        }
        first = self.service.record_visual_submission(learner_id=self.learner_id, payload=core, manifest=manifest)
        self.assertTrue(first["persisted"])
        self.assertTrue(first["created"])
        retry = self.service.record_visual_submission(learner_id=self.learner_id, payload=core, manifest=manifest)
        self.assertTrue(retry["persisted"])
        self.assertFalse(retry["created"])
        with self.assertRaises(ValueError):
            self.service.record_visual_submission(
                learner_id=self.learner_id,
                payload={**core, "actual_minutes": 13},
                manifest=manifest,
            )

        final = {
            "schema_version": "1.0", "surface": "visualize", "manifest_id": manifest["manifest_id"],
            "session_id": session["session_id"], "submission_id": f"{session['session_id']}:strategy_and_reflection",
            "section": "strategy_and_reflection", "answers": [answer("item-02", "B"), answer("item-03", "D")],
            "actual_minutes": 6, "fatigue": "low",
            "reflection": {"observed_fact": "I stayed local.", "uncertainty": "Timing.", "next_review": "Review the slow item."},
        }
        finished = self.service.record_visual_submission(learner_id=self.learner_id, payload=final, manifest=manifest)
        self.assertTrue(finished["completed"])
        self.assertEqual(finished["strategy_conclusion"]["status"], "inconclusive")
        self.assertEqual(self.service.get_progress_summary(self.learner_id)["question_event_counts"]["correct"], 3)
        state = self.service.get_session_state(self.learner_id, session_id=session["session_id"])
        self.assertTrue(state["completed"])
        self.assertEqual(state["actual_minutes"], 20)

    def test_diagnosis_requires_recurring_evidence_for_confirmation(self) -> None:
        first = self.make_event("diagnosis-001")
        with self.assertRaises(ValueError):
            self.service.confirm_error_signature(
                learner_id=self.learner_id,
                code="scope_expansion",
                status="confirmed",
                evidence_event_ids=[first["event"]["event_id"]],
            )
        second = self.make_event("diagnosis-002")
        provisional = self.service.confirm_error_signature(
            learner_id=self.learner_id,
            code="scope_expansion",
            status="provisional",
            evidence_event_ids=[first["event"]["event_id"]],
        )
        self.assertEqual(provisional["status"], "provisional")
        supported = self.service.confirm_error_signature(
            learner_id=self.learner_id,
            code="scope_expansion",
            status="supported",
            evidence_event_ids=[first["event"]["event_id"], second["event"]["event_id"]],
        )
        self.assertEqual(supported["status"], "supported")
        confirmed = self.service.confirm_error_signature(
            learner_id=self.learner_id,
            code="scope_expansion",
            status="confirmed",
            evidence_event_ids=[first["event"]["event_id"], second["event"]["event_id"]],
        )
        self.assertEqual(confirmed["status"], "confirmed")

    def test_review_schedule_uses_evidence_signals(self) -> None:
        early = next_review_date(today=date(2026, 8, 23), prior_success=False, confidence=4, days_since_exposure=0, similarity=1.0, help_used=False, timed=True, recurrence_count=1)
        later = next_review_date(today=date(2026, 8, 23), prior_success=True, confidence=5, days_since_exposure=10, similarity=0.2, help_used=False, timed=False, recurrence_count=1)
        self.assertLessEqual((early - date(2026, 8, 23)).days, (later - date(2026, 8, 23)).days)

    def test_strategy_trial_stays_inconclusive_until_paired_sample(self) -> None:
        trial = self.service.begin_strategy_trial(
            learner_id=self.learner_id,
            strategy="paraphrase the task before reading notes",
            question_type="rhetorical_synthesis",
            condition_a={"method": "paraphrase_first"},
            condition_b={"method": "options_first"},
        )
        trial_id = trial["trial_id"]
        one = self.service.record_strategy_trial_result(learner_id=self.learner_id, trial_id=trial_id, condition="A", correct=True, time_seconds=35, confidence=4)
        self.assertEqual(one["conclusion"]["status"], "inconclusive")
        self.service.record_strategy_trial_result(learner_id=self.learner_id, trial_id=trial_id, condition="A", correct=False, time_seconds=46, confidence=3)
        self.service.record_strategy_trial_result(learner_id=self.learner_id, trial_id=trial_id, condition="B", correct=True, time_seconds=38, confidence=4)
        four = self.service.record_strategy_trial_result(learner_id=self.learner_id, trial_id=trial_id, condition="B", correct=True, time_seconds=34, confidence=4)
        self.assertEqual(four["conclusion"]["status"], "provisional")

    def test_generated_item_requires_all_validation_stages(self) -> None:
        specification = ItemSpecification(
            domain="reading-writing",
            skill="transitions",
            question_type="logical_transition",
            stem_family="most_logical_transition",
            score_band="650-690",
            difficulty="medium",
            cognitive_operation="discriminate",
            target_error_signature="qualifier_omission",
            stimulus_constraints={"synthetic": True},
            correct_answer_rationale="The transition matches the stated contrast.",
            distractor_mechanisms=["direction reversal", "scope drift", "true but irrelevant"],
            difficulty_mechanisms=["scope_or_strength_discrimination"],
            style_reference_ids=["college-board-public-question-stems"],
            timing_expectation_seconds=45,
            transfer_distance="near",
        )
        candidate = {
            "options": ["A", "B", "C", "D"],
            "proposed_key": "C",
            "independent_solution": "C",
            "option_defensibility": {"A": False, "B": False, "C": True, "D": False},
            "shortcut_check": True,
            "wording_check": True,
            "difficulty_check": True,
            "college_board_style_check": True,
            "difficulty_mechanism_check": True,
            "originality_check": True,
        }
        approved = validate_candidate(candidate, specification)
        self.assertEqual(approved["status"], "approved")
        synthesis = replace(
            specification,
            skill="rhetorical_synthesis",
            question_type="student_notes_writerly_goal",
            stem_family="uses_notes_to_accomplish_goal",
            difficulty_mechanisms=["rhetorical_goal_information_selection"],
        )
        with self.assertRaisesRegex(ValueError, "rhetorical_synthesis_scenario_check"):
            validate_candidate(candidate, synthesis)
        synthesis_approved = validate_candidate(
            {**candidate, "rhetorical_synthesis_scenario_check": True}, synthesis
        )
        self.assertEqual(synthesis_approved["status"], "approved")

    def test_purpose_groups_are_presentation_only_and_max_four_questions(self) -> None:
        validated = validate_purpose_groups(
            [
                {"purpose": "evidence direction", "item_ids": ["q1", "q2"]},
                {"purpose": "scope precision", "item_ids": ["q3", "q4"]},
                {"purpose": "writerly goal", "item_ids": ["q5", "q6"]},
            ],
            minimum_groups=3,
            maximum_groups=4,
        )
        self.assertTrue(validated["presentation_only"])
        self.assertEqual(validated["question_count"], 6)
        with self.assertRaises(ValueError):
            validate_purpose_groups(
                [{"purpose": "too many", "item_ids": ["q1", "q2", "q3", "q4", "q5"]}]
            )

    def test_graceful_capability_report_and_explicit_delete(self) -> None:
        capabilities = self.service.get_capabilities()
        self.assertFalse(capabilities["signed_in_chrome_inspection"])
        self.assertEqual(capabilities["browser_practice_scan"], "read_only_adapter_ready_requires_authorized_bridge")
        self.assertTrue(capabilities["chrome_read_only_adapter"]["implemented"])
        with self.assertRaises(ValueError):
            self.service.delete_learner_data(self.learner_id, confirm=False)
        export = self.service.export_learner_model(self.learner_id)
        deleted = self.service.delete_learner_data(self.learner_id, confirm=True)
        self.assertTrue(deleted["deleted"])
        self.assertFalse(Path(export["path"]).exists())
        with self.assertRaises(ValueError):
            self.service.get_learner_profile(self.learner_id)


if __name__ == "__main__":
    unittest.main()
