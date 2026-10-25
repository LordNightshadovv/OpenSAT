# Bounded plugin self-improvement

This workflow applies to the **installable OpenSAT plugin**, not to a student's learner model. It adapts SoL-Pi's auto-research pattern: propose one mechanism, run paired trajectories, review the implementation, screen on training cases, and evaluate a frozen candidate on isolated held-out cases. It uses SoL-Pi's constrained-efficiency objective: save tokens only while predeclared capability checks and quality floors survive. Anthropic's account of recursive self-improvement motivates the research loop, but does not establish that this plugin improves itself or student outcomes.

Sources: [SoL-Pi method and validation](https://nvlabs.github.io/SoL-Pi/); [Anthropic, When AI builds itself](https://www.anthropic.com/institute/recursive-self-improvement).

## Scope and evidence

- Search only plugin mechanisms: skill instructions, item-validation workflow, learner-model policy, local tools, and context handling. Prefer a small change that addresses a measured repeated failure. Do not alter a learner's plan as an RSI experiment.
- Use public or purpose-built synthetic tasks and traces. Never feed the loop personal learner records, private browser captures, copied official SAT items, or credentials. Keep experiment artifacts in a temporary directory outside the repository and review them before any sharing.
- Record baseline quality and token counts for the same predeclared cases. Include cases across relevant score bands, correct-but-slow and fragile-correct evidence, single-miss provisional diagnosis, due-review scheduling, and content/privacy boundaries when the proposed change could affect them.
- Quality is a predeclared 0–1 task rubric. Its scorer and case set must be fixed before candidate runs. Tokens are measured model tokens from the same backend and instrumentation in both arms. Do not compare different models, effort settings, or tool availability as if they isolate a plugin mechanism.
- A static validator checks receipt structure, source binding, capability booleans, paired coverage, per-case quality floors, and aggregate token reduction. It does not execute Codex, verify that trace measurements are genuine, prove the scorer is valid, or show SAT efficacy. Inspect raw trace artifacts and run ordinary plugin tests before promotion.

## One-candidate loop

1. **Opportunity and proposal.** Write a short hypothesis linking a repeated observed cost or error to one plugin mechanism. Estimate whether it can matter. Discard speculative ideas before implementation.
2. **Predeclare.** Create a plan with disjoint `train_cases` and `heldout_cases`. Keep held-out tasks, rubrics, and results inaccessible to the implementation loop. Define capability checks that cover the affected contract. Set `max_quality_drop` and `min_token_reduction` before running the candidate. Avoid a permissive quality tolerance for privacy, official-content, or answer-validity failures; these are critical checks.
3. **Implement and review.** Change one mechanism in an isolated checkout. A reviewer other than the proposer checks the source diff, task contract, fixture construction, scorer, and possible shortcuts. A review receipt names the reviewer and binds to the frozen candidate digest. If an independent reviewer is unavailable, leave the candidate unpromoted.
4. **Screen.** Run baseline and candidate on each training case under the same settings. Preserve trace artifacts. Failed training cases can guide a new candidate, which must receive a new proposal ID and freeze.
5. **Final validation.** Run the frozen candidate on held-out cases once after training and review pass. Do not bring held-out feedback into the same search lineage after failure. Assess combined regressions against already promoted mechanisms before install.
6. **Promote or reject.** A passing receipt makes the change eligible for human/source review and normal tests. Record the decision and keep rejected/deferred evidence. To release, update the version with the plugin-creator cachebuster helper, reinstall `opensat@personal`, verify the installed files, and start a new Codex chat to load the updated skill definitions. Roll back by reinstalling the previous source/version if needed.

The loop is bounded by the experiment's declared cases and resource budget. It never runs continuously in the background, modifies its own acceptance rules mid-run, or automatically writes to learner data.

## Artifact contract

Place artifacts under a fresh local directory such as `/tmp/opensat-rsi/<proposal-id>/`. The commands below refer to an isolated candidate source tree. The assessor writes each split receipt once (`train-receipt.json`, `heldout-receipt.json`); keep that directory as a reviewable ledger. Deleting a receipt is possible, so this is an operational guard, not a tamper-proof seal.

`plan.json`:

```json
{
  "schema_version": 1,
  "proposal_id": "short-unique-id",
  "proposer": "agent-or-person-id",
  "hypothesis": "One concrete mechanism and its expected effect",
  "baseline_ref": "baseline-git-commit-or-source-digest",
  "candidate_files": ["skills/sat-daily-sprint/SKILL.md"],
  "train_cases": ["synthetic-train-a", "synthetic-train-b"],
  "heldout_cases": ["synthetic-holdout-a"],
  "capability_checks": ["answer_validity", "privacy_boundary", "official_content_boundary", "twenty_minute_budget", "provisional_diagnosis"],
  "max_quality_drop": 0.0,
  "min_token_reduction": 0.05
}
```

Freeze after implementation, before candidate measurements:

```bash
python3 scripts/self_improvement.py freeze --plan /tmp/opensat-rsi/example/plan.json --source-root /path/to/candidate/opensat --experiment-dir /tmp/opensat-rsi/example
```

Each run artifact is a JSON object with exactly `case_id`, `arm` (`baseline` or `candidate`), `source_ref` (the plan's baseline ref or the frozen candidate digest), `quality` (0–1), `tokens` (positive measured integer), and `checks` (Boolean result for every declared capability check). Store permitted raw traces separately and bind them to run artifacts in your experiment notes. The gate cannot independently reproduce a model run or authenticate the named reviewer.

`train-evidence.json` and `heldout-evidence.json` each contain a split and one paired entry per declared case. Paths resolve relative to the evidence file and must stay inside that directory:

```json
{
  "schema_version": 1,
  "split": "train",
  "runs": [
    {"case_id": "synthetic-train-a", "baseline": "runs/a-baseline.json", "candidate": "runs/a-candidate.json"},
    {"case_id": "synthetic-train-b", "baseline": "runs/b-baseline.json", "candidate": "runs/b-candidate.json"}
  ]
}
```

```bash
python3 scripts/self_improvement.py assess --experiment-dir /tmp/opensat-rsi/example --source-root /path/to/candidate/opensat --evidence /tmp/opensat-rsi/example/train-evidence.json --split train
```

After training passes, write `review.json` with `candidate_digest`, `reviewer`, and `passed: true`; the reviewer must differ from `proposer`. Then assess the held-out split with `--split heldout --evidence ... --review /tmp/opensat-rsi/example/review.json`. The assessor rejects duplicate or missing cases, source drift, failed checks, per-case quality regressions beyond the declared tolerance, and insufficient token reduction. A passing receipt is not a publication or deployment event.
