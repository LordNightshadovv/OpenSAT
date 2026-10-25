from __future__ import annotations

import unittest

from opensat.adaptation import recommend_practice_difficulty


def event(
    result: str,
    *,
    skill: str = "evidence_selection",
    seconds: float = 25,
    threshold: float = 60,
    confidence: int = 4,
    help_used: bool = False,
    apparent_difficulty: str | None = None,
) -> dict[str, object]:
    return {
        "result": result,
        "provisional_skill": skill,
        "time_seconds": seconds,
        "confidence": confidence,
        "answer_changed": False,
        "apparent_difficulty": apparent_difficulty,
        "abstract_context": {
            "slow_threshold_seconds": threshold,
            "help_used": help_used,
        },
    }


class DifficultyAdaptationTests(unittest.TestCase):
    def test_fast_high_accuracy_with_calibration_miss_raises_challenge_share(self) -> None:
        events = [event("correct") for _ in range(5)] + [
            event("incorrect", skill="sentence_boundaries", confidence=5, seconds=20, threshold=45)
        ]
        recommendation = recommend_practice_difficulty("750-800", events)
        self.assertEqual(recommendation["target_tier"], "hard")
        self.assertEqual(recommendation["stretch_tier"], "challenge")
        self.assertEqual(recommendation["stretch_share"], 0.5)
        self.assertEqual(recommendation["evidence_status"], "increase_challenge_mix_with_calibration")
        self.assertEqual(recommendation["priority_skills"], ["sentence_boundaries"])
        self.assertEqual(recommendation["high_confidence_misses"], 1)

    def test_fast_calibrated_accuracy_can_raise_centre_tier(self) -> None:
        recommendation = recommend_practice_difficulty(
            "700-740",
            [event("correct", confidence=4) for _ in range(6)],
        )
        self.assertEqual(recommendation["target_tier"], "hard")
        self.assertEqual(recommendation["evidence_status"], "ready_for_level_increase")

    def test_sparse_evidence_holds_band_prior(self) -> None:
        recommendation = recommend_practice_difficulty("750-800", [event("correct") for _ in range(3)])
        self.assertEqual(recommendation["target_tier"], "hard")
        self.assertEqual(recommendation["evidence_status"], "insufficient_recent_evidence")

    def test_recurring_struggle_scaffolds_but_respects_high_band_floor(self) -> None:
        recommendation = recommend_practice_difficulty(
            "750-800",
            [event("incorrect", seconds=80, help_used=True) for _ in range(5)],
        )
        self.assertEqual(recommendation["target_tier"], "upper-medium")
        self.assertEqual(recommendation["evidence_status"], "temporary_scaffold")

    def test_skill_stage_changes_targeted_transfer_without_lowering_whole_set(self) -> None:
        events = [event("correct") for _ in range(5)] + [
            event("incorrect", skill="sentence_boundaries", confidence=5)
        ]
        recommendation = recommend_practice_difficulty(
            "750-800",
            events,
            skill_stages={"sentence_boundaries": "explain"},
        )
        self.assertEqual(recommendation["target_tier"], "hard")
        self.assertEqual(
            recommendation["skill_overrides"]["sentence_boundaries"]["transfer"],
            "near_scaffolded",
        )

    def test_routine_high_confidence_miss_is_silent_danger(self) -> None:
        events = [event("correct", apparent_difficulty="routine") for _ in range(4)] + [
            event("incorrect", confidence=5, apparent_difficulty="routine")
        ]
        recommendation = recommend_practice_difficulty("750-800", events)
        self.assertEqual(recommendation["silent_danger_count"], 1)
        self.assertEqual(recommendation["routine_clean_correct_count"], 4)
        self.assertEqual(recommendation["routine_miscalibration_rate"], 0.2)
        self.assertEqual(recommendation["apparent_difficulty_distribution"]["routine"], 5)

    def test_routine_fragile_correct_is_concealed_friction(self) -> None:
        events = [event("correct", apparent_difficulty="routine") for _ in range(4)] + [
            event("correct_changed", apparent_difficulty="routine")
        ]
        recommendation = recommend_practice_difficulty("750-800", events)
        self.assertEqual(recommendation["silent_danger_count"], 0)
        self.assertEqual(recommendation["concealed_friction_count"], 1)
        self.assertNotEqual(recommendation["evidence_status"], "ready_for_level_increase")


if __name__ == "__main__":
    unittest.main()
