from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from self_improvement import assess, freeze


CHECKS = ["answer_validity", "privacy_boundary", "official_content_boundary", "twenty_minute_budget", "provisional_diagnosis"]


class SelfImprovementGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="opensat-rsi-test-")
        self.root = Path(self.temp.name)
        self.source = self.root / "source"
        (self.source / "skills" / "example").mkdir(parents=True)
        (self.source / "skills" / "example" / "SKILL.md").write_text("candidate")
        self.exp = self.root / "experiment"
        self.exp.mkdir()
        self.plan = {
            "schema_version": 1,
            "proposal_id": "p1",
            "proposer": "author",
            "hypothesis": "Remove repeated instructions",
            "baseline_ref": "baseline-commit",
            "candidate_files": ["skills/example/SKILL.md"],
            "train_cases": ["t1", "t2"],
            "heldout_cases": ["h1"],
            "capability_checks": CHECKS,
            "max_quality_drop": 0.0,
            "min_token_reduction": 0.05,
        }
        self.plan_path = self.exp / "plan.json"
        self.write(self.plan_path, self.plan)

    def tearDown(self) -> None:
        self.temp.cleanup()

    @staticmethod
    def write(path: Path, value: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value))

    def evidence(self, split: str, digest: str, candidate_quality: float = 1.0, candidate_tokens: int = 80) -> Path:
        cases = self.plan[f"{split}_cases"]
        rows = []
        for case in cases:
            base_path = f"runs/{case}-baseline.json"
            cand_path = f"runs/{case}-candidate.json"
            self.write(self.exp / base_path, {"case_id": case, "arm": "baseline", "source_ref": "baseline-commit", "quality": 1.0, "tokens": 100, "checks": {name: True for name in CHECKS}})
            self.write(self.exp / cand_path, {"case_id": case, "arm": "candidate", "source_ref": digest, "quality": candidate_quality, "tokens": candidate_tokens, "checks": {name: True for name in CHECKS}})
            rows.append({"case_id": case, "baseline": base_path, "candidate": cand_path})
        path = self.exp / f"{split}-evidence.json"
        self.write(path, {"schema_version": 1, "split": split, "runs": rows})
        return path

    def test_paired_train_and_one_shot_heldout_pass(self) -> None:
        digest = freeze(self.plan_path, self.source, self.exp)["candidate_digest"]
        train = assess(self.exp, self.source, self.evidence("train", digest), "train")
        self.assertEqual(train["status"], "pass")
        review = self.exp / "review.json"
        self.write(review, {"candidate_digest": digest, "reviewer": "independent-reviewer", "passed": True})
        heldout = assess(self.exp, self.source, self.evidence("heldout", digest), "heldout", review)
        self.assertEqual(heldout["status"], "pass")
        self.assertAlmostEqual(heldout["token_reduction"], 0.2)
        with self.assertRaisesRegex(ValueError, "already assessed"):
            assess(self.exp, self.source, self.exp / "heldout-evidence.json", "heldout", review)

    def test_quality_regression_rejects_even_with_token_savings(self) -> None:
        digest = freeze(self.plan_path, self.source, self.exp)["candidate_digest"]
        result = assess(self.exp, self.source, self.evidence("train", digest, candidate_quality=0.8, candidate_tokens=50), "train")
        self.assertEqual(result["status"], "reject")
        self.assertFalse(result["quality_floor_passed"])

    def test_freeze_rejects_overlapping_splits(self) -> None:
        self.plan["heldout_cases"] = ["t1"]
        self.write(self.plan_path, self.plan)
        with self.assertRaisesRegex(ValueError, "disjoint"):
            freeze(self.plan_path, self.source, self.exp)

    def test_source_drift_blocks_assessment(self) -> None:
        digest = freeze(self.plan_path, self.source, self.exp)["candidate_digest"]
        evidence = self.evidence("train", digest)
        (self.source / "skills" / "example" / "SKILL.md").write_text("changed")
        with self.assertRaisesRegex(ValueError, "changed after freeze"):
            assess(self.exp, self.source, evidence, "train")

    def test_failed_critical_check_invalidates_evidence(self) -> None:
        digest = freeze(self.plan_path, self.source, self.exp)["candidate_digest"]
        evidence = self.evidence("train", digest)
        path = self.exp / "runs" / "t1-candidate.json"
        run = json.loads(path.read_text())
        run["checks"]["privacy_boundary"] = False
        self.write(path, run)
        with self.assertRaisesRegex(ValueError, "Capability check failed"):
            assess(self.exp, self.source, evidence, "train")


if __name__ == "__main__":
    unittest.main()
