from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from opensat import LabService
from opensat.scheduling.on_demand import recommend_on_demand_sessions
from opensat.storage.database import connect


def event(
    event_id: str,
    result: str,
    *,
    skill: str = "evidence_selection",
    confidence: int = 4,
    seconds: float = 30,
    target_signature: str | None = None,
) -> dict[str, object]:
    return {
        "event_id": event_id,
        "result": result,
        "provisional_skill": skill,
        "time_seconds": seconds,
        "confidence": confidence,
        "answer_changed": result == "correct_changed",
        "abstract_context": {
            "help_used": False,
            "slow_threshold_seconds": 60,
            "target_error_signature": target_signature,
        },
    }


class OnDemandRecommendationTests(unittest.TestCase):
    def test_session_start_clock_surfaces_only_due_reviews(self) -> None:
        fixed_now = datetime(2026, 9, 3, 8, 15, tzinfo=timezone(timedelta(hours=8)))
        with tempfile.TemporaryDirectory(prefix="opensat-session-clock-") as directory:
            data_dir = Path(directory) / "runtime"
            service = LabService(data_dir, clock=lambda: fixed_now)
            learner = service.initialize_learner(
                preferred_language="english",
                reading_writing_score=760,
            )
            learner_id = learner["learner"]["learner_id"]
            assessment = service.record_assessment(
                learner_id=learner_id,
                source="manual",
                assessment_type="clock-test",
                external_id="clock-test-assessment",
                is_official=False,
                reading_writing_score=760,
            )
            due_event = service.record_question_event(
                learner_id=learner_id,
                assessment_id=assessment["assessment"]["assessment_id"],
                event_key="due-inference",
                section="reading-writing",
                question_locator="due-inference",
                result="correct_slow",
                provenance_type="simulated",
                time_seconds=100,
                confidence=4,
                provisional_skill="inference",
                abstract_context={"slow_threshold_seconds": 60},
            )["event"]
            future_event = service.record_question_event(
                learner_id=learner_id,
                assessment_id=assessment["assessment"]["assessment_id"],
                event_key="future-evidence",
                section="reading-writing",
                question_locator="future-evidence",
                result="correct_slow",
                provenance_type="simulated",
                time_seconds=95,
                confidence=4,
                provisional_skill="command_of_evidence_quantitative",
                abstract_context={"slow_threshold_seconds": 60},
            )["event"]
            connection, _ = connect(data_dir)
            try:
                connection.execute(
                    "UPDATE review_queue SET due_at = ? WHERE event_id = ?",
                    ("2026-09-03", due_event["event_id"]),
                )
                connection.execute(
                    "UPDATE review_queue SET due_at = ? WHERE event_id = ?",
                    ("2026-09-05", future_event["event_id"]),
                )
                connection.commit()
            finally:
                connection.close()

            context = service.get_session_start_context(learner_id)
            self.assertEqual(context["clock"]["local_date"], "2026-09-03")
            self.assertEqual(context["clock"]["local_time"], "08:15:00")
            self.assertEqual(context["clock"]["utc_offset"], "+08:00")
            self.assertEqual(context["due_review_count"], 1)
            self.assertEqual(context["due_today_count"], 1)
            self.assertEqual(context["overdue_review_count"], 0)
            self.assertEqual(context["due_reviews"][0]["event_id"], due_event["event_id"])
            self.assertEqual(context["scheduled_session_count"], 1)
            self.assertEqual(context["scheduled_sessions"][0]["target_skill"], "inference")

            session = service.build_daily_session(learner_id)
            self.assertEqual(session["session_start_context"]["checked_for_date"], "2026-09-03")
            self.assertEqual(session["session_start_context"]["due_review_count"], 1)

    def test_high_accuracy_does_not_suppress_slow_correct_follow_up(self) -> None:
        result = recommend_on_demand_sessions(
            "750-800",
            [event(f"correct-{index}", "correct") for index in range(4)]
            + [event("slow-1", "correct_slow", skill="inference", confidence=5, seconds=101)],
        )
        self.assertEqual(result["recommendation_count"], 1)
        recommendation = result["recommendations"][0]
        self.assertEqual(recommendation["session_type"], "timed_precision_and_retrieval")
        self.assertEqual(recommendation["target_skill"], "inference")
        self.assertEqual(recommendation["diagnostic_status"], "provisional")
        self.assertEqual(recommendation["session_blueprint"]["planned_minutes"], 12)

    def test_incorrect_response_recommends_autopsy_worked_example_and_transfer(self) -> None:
        result = recommend_on_demand_sessions(
            "650-690",
            [event("miss-1", "incorrect", skill="transitions", target_signature="task_goal_drift")],
        )
        recommendation = result["recommendations"][0]
        self.assertEqual(recommendation["session_type"], "mistake_autopsy_worked_example")
        self.assertEqual(recommendation["target_error_signature"], "task_goal_drift")
        self.assertEqual(
            [item["activity_type"] for item in recommendation["session_blueprint"]["activities"]],
            ["retrieval_check", "worked_example", "targeted_practice", "transfer_check"],
        )
        self.assertEqual(recommendation["material_guidance"]["difficulty_center"], "medium")

    def test_confirmed_signature_is_attached_to_its_evidence_event(self) -> None:
        result = recommend_on_demand_sessions(
            "650-690",
            [event("miss-2", "incorrect", skill="transitions")],
            signatures=[{
                "code": "task_goal_drift",
                "status": "confirmed",
                "evidence_event_ids": ["miss-2", "miss-earlier"],
                "recurrence_count": 2,
            }],
        )
        recommendation = result["recommendations"][0]
        self.assertEqual(recommendation["target_error_signature"], "task_goal_drift")
        self.assertEqual(recommendation["diagnostic_status"], "confirmed")

    def test_clean_fast_calibrated_evidence_returns_no_issue_session(self) -> None:
        result = recommend_on_demand_sessions(
            "750-800",
            [event(f"correct-{index}", "correct", confidence=5, seconds=25) for index in range(6)],
        )
        self.assertEqual(result["recommendation_count"], 0)
        self.assertIsNotNone(result["no_issue_message"])

    def test_later_clean_transfer_suppresses_an_unconfirmed_older_miss(self) -> None:
        older = event("older-miss", "incorrect", skill="sentence_boundaries")
        older["created_at"] = "2026-08-29T09:00:00+00:00"
        later = event("later-clean", "correct", skill="sentence_boundaries", confidence=5, seconds=20)
        later["created_at"] = "2026-08-31T09:00:00+00:00"
        result = recommend_on_demand_sessions("750-800", [later, older])
        self.assertEqual(result["recommendation_count"], 0)

    def test_completed_due_review_stays_closed_after_clean_transfer(self) -> None:
        fixed_now = datetime(2026, 8, 31, 17, 0, tzinfo=timezone(timedelta(hours=8)))
        with tempfile.TemporaryDirectory(prefix="opensat-review-complete-") as directory:
            data_dir = Path(directory) / "runtime"
            service = LabService(data_dir, clock=lambda: fixed_now)
            learner = service.initialize_learner(preferred_language="english", reading_writing_score=760)
            learner_id = learner["learner"]["learner_id"]
            assessment = service.record_assessment(
                learner_id=learner_id,
                source="manual",
                assessment_type="review-complete-test",
                external_id="review-complete-test",
                is_official=False,
                reading_writing_score=760,
            )
            miss = service.record_question_event(
                learner_id=learner_id,
                assessment_id=assessment["assessment"]["assessment_id"],
                event_key="boundary-miss",
                section="reading-writing",
                question_locator="boundary-miss",
                result="incorrect",
                provenance_type="simulated",
                time_seconds=20,
                confidence=5,
                provisional_skill="sentence_boundaries",
            )["event"]
            connection, _ = connect(data_dir)
            try:
                connection.execute(
                    "UPDATE review_queue SET due_at = ? WHERE event_id = ?",
                    ("2026-08-31", miss["event_id"]),
                )
                connection.commit()
            finally:
                connection.close()

            clean = service.record_question_event(
                learner_id=learner_id,
                assessment_id=assessment["assessment"]["assessment_id"],
                event_key="boundary-clean-transfer",
                section="reading-writing",
                question_locator="boundary-clean-transfer",
                result="correct",
                provenance_type="simulated",
                time_seconds=20,
                confidence=5,
                provisional_skill="sentence_boundaries",
                abstract_context={"help_used": False},
            )
            self.assertEqual(len(clean["completed_review_ids"]), 1)
            self.assertEqual(service.get_session_start_context(learner_id)["due_review_count"], 0)
            self.assertEqual(service.get_on_demand_recommendations(learner_id)["recommendation_count"], 0)

    def test_due_review_without_recent_event_recommends_delayed_retrieval(self) -> None:
        result = recommend_on_demand_sessions(
            "650-690",
            [],
            [{
                "event_id": "old-event",
                "skill": "sentence_boundaries",
                "reason": "Review an earlier response",
                "due_at": "2026-08-30",
                "status": "open",
            }],
        )
        recommendation = result["recommendations"][0]
        self.assertEqual(recommendation["session_type"], "delayed_retrieval_and_transfer")
        self.assertEqual(recommendation["diagnostic_status"], "review_due")

    def test_service_exposes_recommendations_in_progress_summary(self) -> None:
        with tempfile.TemporaryDirectory(prefix="opensat-on-demand-") as directory:
            service = LabService(Path(directory) / "runtime")
            learner = service.initialize_learner(
                preferred_language="english",
                reading_writing_score=760,
                math_score=790,
            )
            learner_id = learner["learner"]["learner_id"]
            assessment = service.record_assessment(
                learner_id=learner_id,
                source="manual",
                assessment_type="daily-sprint",
                external_id="on-demand-assessment",
                is_official=False,
                reading_writing_score=760,
            )
            service.record_question_event(
                learner_id=learner_id,
                assessment_id=assessment["assessment"]["assessment_id"],
                event_key="slow-inference",
                section="reading-writing",
                question_locator="synthetic-slow-inference",
                result="correct_slow",
                provenance_type="simulated",
                time_seconds=100,
                confidence=5,
                provisional_skill="inference",
                abstract_context={"slow_threshold_seconds": 60},
            )
            session = service.build_daily_session(learner_id)
            service.record_activity_result(
                learner_id=learner_id,
                session_id=session["session_id"],
                activity_type="timed_precision_block",
                outcome="completed",
                actual_minutes=17,
            )
            completed = service.record_activity_result(
                learner_id=learner_id,
                session_id=session["session_id"],
                activity_type="review_reflection",
                outcome="completed",
                actual_minutes=3,
                completed=True,
            )
            self.assertIsNotNone(completed["on_demand_recommendations"])
            summary = service.get_progress_summary(learner_id)
            follow_up = summary["on_demand_recommendations"]
            self.assertEqual(follow_up["recommendation_count"], 1)
            self.assertEqual(
                follow_up["recommendations"][0]["session_type"],
                "timed_precision_and_retrieval",
            )

    def test_distant_assessment_event_is_not_reopened_without_current_evidence(self) -> None:
        with tempfile.TemporaryDirectory(prefix="opensat-on-demand-old-") as directory:
            service = LabService(Path(directory) / "runtime")
            learner = service.initialize_learner(
                preferred_language="english",
                reading_writing_score=680,
            )
            learner_id = learner["learner"]["learner_id"]
            assessment = service.record_assessment(
                learner_id=learner_id,
                source="manual",
                assessment_type="old-diagnostic",
                external_id="old-diagnostic-assessment",
                taken_at="2020-01-01",
                is_official=True,
                reading_writing_score=680,
            )
            service.record_question_event(
                learner_id=learner_id,
                assessment_id=assessment["assessment"]["assessment_id"],
                event_key="old-miss",
                section="reading-writing",
                question_locator="old-diagnostic-item",
                result="incorrect",
                provenance_type="official",
                confidence=5,
                provisional_skill="inference",
            )
            recommendations = service.get_on_demand_recommendations(learner_id)
            self.assertEqual(recommendations["recommendation_count"], 0)


if __name__ == "__main__":
    unittest.main()
