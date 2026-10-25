---
name: sat-self-improvement
description: Run a bounded, evidence-backed improvement experiment on the OpenSAT plugin when the user asks for recursive self-improvement or evaluated plugin optimization; do not use for an individual learner's study plan.
---

# OpenSAT Self-Improvement

Read `../../docs/self-improvement.md` before proposing an OpenSAT plugin change. This is a plugin-development workflow, separate from a learner's Strategy Lab trial.

1. Start from the installable plugin source shown by `codex plugin list`. Keep experiments outside the repository and exclude learner profiles, runtime SQLite, browser captures, official question content, credentials, and private trajectories.
2. Identify one recurring failure or wasted step from permitted synthetic/public traces. Record the observed baseline, competing causes, one mechanism hypothesis, expected capability impact, and a token-efficiency target. Reject an idea with no measurable opportunity before spending rollout effort.
3. Predeclare disjoint training and held-out case IDs, capability checks, a per-case quality tolerance, and a minimum token reduction. Use representative SAT bands and failure modes; the 20-minute budget, content boundary, provenance labels, and cautious diagnosis are required checks. Freeze the plan and candidate source fingerprint with `scripts/self_improvement.py freeze`.
4. Implement one candidate in an isolated checkout. Run paired baseline/candidate cases and retain machine-readable trace artifacts. Review the diff and behavioral contract independently. Iterate only on training evidence; freeze a revised candidate as a new proposal.
5. Run `scripts/self_improvement.py assess --split train`. After a passing training receipt and an independent review bound to the candidate digest, run the held-out assessment once. Do not use held-out results to repair and retest the same lineage. A failed or invalid held-out result rejects that candidate.
6. Only promote a passing candidate after reviewing its source diff, ordinary tests, and combined behavior with earlier promoted changes. Preserve the old plugin version for rollback, cache-bust and reinstall from the registered marketplace, and verify the installed copy. A gate receipt is evidence of the declared cases and metrics, not proof of learner score gains or general recursive improvement.

For the artifact format, exact commands, claim limits, and rollback process, use `../../docs/self-improvement.md`.
