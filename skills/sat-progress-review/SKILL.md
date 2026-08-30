---
name: sat-progress-review
description: Review OpenSAT progress when a learner asks what has improved or what to do next; compare official reassessments, domain evidence, error signatures, timing, confidence calibration, transfer, recurrence, and score variance without treating simulated performance as an official score.
---

# SAT Progress Review

## Workflow

Read `../../docs/pilot-and-evaluation-plan.md` and `../../docs/learner-model.md`. Use `get_progress_summary`, assessment history, review queue, and learner-model exports when available.

1. State the evidence window and source provenance: official, simulated, licensed, or manual.
2. Compare official score and Reading and Writing/Math fields separately. Do not infer a score from generated items.
3. Review recurring signatures, supporting and contradicting events, skill stage, timing, omissions, answer changes, confidence, and fatigue.
4. Look for near and far transfer and delayed stability, not just immediate repeated correctness.
5. Report three layers: observed fact, interpretation/hypothesis, and confirmed pattern. Mark gaps as `insufficient evidence`.
6. Select the smallest next intervention: a review-queue item, delayed retrieval, near/far transfer, calibration, strategy trial, or unused official reassessment.

## Output shape

Return:

- Evidence summary with source labels
- Stable, fragile, and unresolved areas
- Confidence/calibration and timing notes
- Next smallest intervention and success criterion
- Reassessment or transfer condition

Do not use a guaranteed score-gain claim. Say explicitly when official reassessment, browser import, cross-surface behavior, or question quality has not been tested.
