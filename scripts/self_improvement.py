#!/usr/bin/env python3
"""Freeze and assess one evidence-backed OpenSAT plugin improvement candidate.

This gate validates artifacts and arithmetic. It does not run Codex, establish
learner efficacy, or make the evidence tamper-proof.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def _read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def _write_once(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _safe_file(root: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise ValueError("Artifact path must be relative")
    path = root / relative
    if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root.resolve()):
        raise ValueError(f"Artifact path must be a regular file inside {root}: {relative}")
    return path


def _candidate_digest(root: Path, paths: list[str]) -> str:
    entries = []
    for relative in paths:
        path = _safe_file(root, relative)
        entries.append([relative, _sha256(path.read_bytes())])
    return _sha256(_canonical(entries))


def _valid_plan(plan: dict) -> None:
    if plan.get("schema_version") != 1:
        raise ValueError("Unsupported plan schema_version")
    for key in ("proposal_id", "proposer", "hypothesis", "baseline_ref"):
        if not isinstance(plan.get(key), str) or not plan[key].strip():
            raise ValueError(f"Missing {key}")
    for key in ("candidate_files", "train_cases", "heldout_cases", "capability_checks"):
        values = plan.get(key)
        if not isinstance(values, list) or not values or not all(isinstance(x, str) and x for x in values):
            raise ValueError(f"{key} must be a nonempty list of strings")
        if len(values) != len(set(values)):
            raise ValueError(f"Duplicate entries in {key}")
    if set(plan["train_cases"]) & set(plan["heldout_cases"]):
        raise ValueError("Training and held-out case IDs must be disjoint")
    required_checks = {"answer_validity", "privacy_boundary", "official_content_boundary", "twenty_minute_budget", "provisional_diagnosis"}
    if not required_checks.issubset(plan["capability_checks"]):
        raise ValueError(f"capability_checks must include {sorted(required_checks)}")
    for key in ("max_quality_drop", "min_token_reduction"):
        value = plan.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value < 1:
            raise ValueError(f"{key} must be in [0, 1)")


def freeze(plan_path: Path, source_root: Path, experiment_dir: Path) -> dict:
    if experiment_dir.resolve().is_relative_to(source_root.resolve()):
        raise ValueError("Experiment artifacts must stay outside the plugin source")
    plan = _read_json(plan_path)
    _valid_plan(plan)
    # Only plugin source files belong in the candidate fingerprint.
    for relative in plan["candidate_files"]:
        parts = Path(relative).parts
        if parts[0] not in {"src", "scripts", "skills", "schemas", "docs", "tests", ".codex-plugin"}:
            raise ValueError(f"Not a plugin source path: {relative}")
    frozen = {
        "plan": plan,
        "plan_sha256": _sha256(_canonical(plan)),
        "candidate_digest": _candidate_digest(source_root, plan["candidate_files"]),
    }
    _write_once(experiment_dir / "frozen.json", frozen)
    return frozen


def _run(artifact_root: Path, relative: str, case_id: str, arm: str, source_ref: str, checks: list[str]) -> tuple[dict, str]:
    path = _safe_file(artifact_root, relative)
    raw = path.read_bytes()
    run = json.loads(raw)
    if not isinstance(run, dict) or run.get("case_id") != case_id or run.get("arm") != arm:
        raise ValueError(f"Run identity mismatch: {relative}")
    if set(run) != {"case_id", "arm", "source_ref", "quality", "tokens", "checks"}:
        raise ValueError(f"Run artifact has unexpected fields: {relative}")
    if run.get("source_ref") != source_ref:
        raise ValueError(f"Source reference mismatch: {relative}")
    quality = run.get("quality")
    tokens = run.get("tokens")
    if isinstance(quality, bool) or not isinstance(quality, (int, float)) or not 0 <= quality <= 1:
        raise ValueError(f"Invalid quality in {relative}")
    if isinstance(tokens, bool) or not isinstance(tokens, int) or tokens <= 0:
        raise ValueError(f"Invalid token count in {relative}")
    if not isinstance(run.get("checks"), dict) or any(run["checks"].get(check) is not True for check in checks):
        raise ValueError(f"Capability check failed or missing in {relative}")
    return run, _sha256(raw)


def assess(experiment_dir: Path, source_root: Path, evidence_path: Path, split: str, review_path: Path | None = None) -> dict:
    if experiment_dir.resolve().is_relative_to(source_root.resolve()):
        raise ValueError("Experiment artifacts must stay outside the plugin source")
    if split not in {"train", "heldout"}:
        raise ValueError("Split must be train or heldout")
    output = experiment_dir / f"{split}-receipt.json"
    if output.exists():
        raise ValueError(f"Split already assessed: {split}")
    frozen = _read_json(experiment_dir / "frozen.json")
    plan = frozen["plan"]
    _valid_plan(plan)
    if frozen["plan_sha256"] != _sha256(_canonical(plan)):
        raise ValueError("Frozen plan changed")
    digest = _candidate_digest(source_root, plan["candidate_files"])
    if digest != frozen["candidate_digest"]:
        raise ValueError("Candidate changed after freeze")
    if split == "heldout":
        train = _read_json(experiment_dir / "train-receipt.json")
        if train.get("status") != "pass" or train.get("candidate_digest") != digest:
            raise ValueError("Passing training receipt is required")
        if review_path is None:
            raise ValueError("Independent review receipt is required")
        review = _read_json(review_path)
        if (review.get("candidate_digest") != digest or review.get("passed") is not True
                or not isinstance(review.get("reviewer"), str) or not review["reviewer"].strip()
                or review["reviewer"] == plan["proposer"]):
            raise ValueError("Review must pass, bind to this candidate, and name a different reviewer")
    evidence = _read_json(evidence_path)
    if evidence.get("schema_version") != 1 or evidence.get("split") != split:
        raise ValueError("Evidence schema or split mismatch")
    runs = evidence.get("runs")
    expected = set(plan[f"{split}_cases"])
    if not isinstance(runs, list) or {row.get("case_id") for row in runs if isinstance(row, dict)} != expected or len(runs) != len(expected):
        raise ValueError("Evidence must cover each predeclared case exactly once")
    baseline_tokens = candidate_tokens = 0
    baseline_quality = candidate_quality = 0.0
    artifacts = []
    for row in runs:
        case_id = row["case_id"]
        baseline, baseline_hash = _run(evidence_path.parent, row["baseline"], case_id, "baseline", plan["baseline_ref"], plan["capability_checks"])
        candidate, candidate_hash = _run(evidence_path.parent, row["candidate"], case_id, "candidate", digest, plan["capability_checks"])
        if candidate["quality"] + plan["max_quality_drop"] < baseline["quality"]:
            quality_regression = True
        else:
            quality_regression = False
        artifacts.append({"case_id": case_id, "baseline_sha256": baseline_hash, "candidate_sha256": candidate_hash, "quality_regression": quality_regression})
        baseline_tokens += baseline["tokens"]
        candidate_tokens += candidate["tokens"]
        baseline_quality += baseline["quality"]
        candidate_quality += candidate["quality"]
    reduction = 1 - candidate_tokens / baseline_tokens
    quality_ok = all(not row["quality_regression"] for row in artifacts) and candidate_quality + len(runs) * plan["max_quality_drop"] >= baseline_quality
    status = "pass" if quality_ok and reduction >= plan["min_token_reduction"] else "reject"
    receipt = {
        "schema_version": 1,
        "proposal_id": plan["proposal_id"],
        "split": split,
        "status": status,
        "candidate_digest": digest,
        "plan_sha256": frozen["plan_sha256"],
        "evidence_sha256": _sha256(evidence_path.read_bytes()),
        "case_artifacts": artifacts,
        "baseline_quality_mean": baseline_quality / len(runs),
        "candidate_quality_mean": candidate_quality / len(runs),
        "baseline_tokens": baseline_tokens,
        "candidate_tokens": candidate_tokens,
        "token_reduction": reduction,
        "quality_floor_passed": quality_ok,
    }
    _write_once(output, receipt)
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    freeze_parser = sub.add_parser("freeze")
    freeze_parser.add_argument("--plan", type=Path, required=True)
    freeze_parser.add_argument("--source-root", type=Path, required=True)
    freeze_parser.add_argument("--experiment-dir", type=Path, required=True)
    assess_parser = sub.add_parser("assess")
    assess_parser.add_argument("--experiment-dir", type=Path, required=True)
    assess_parser.add_argument("--source-root", type=Path, required=True)
    assess_parser.add_argument("--evidence", type=Path, required=True)
    assess_parser.add_argument("--split", choices=["train", "heldout"], required=True)
    assess_parser.add_argument("--review", type=Path)
    args = parser.parse_args()
    if args.command == "freeze":
        result = freeze(args.plan, args.source_root, args.experiment_dir)
    else:
        result = assess(args.experiment_dir, args.source_root, args.evidence, args.split, args.review)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
