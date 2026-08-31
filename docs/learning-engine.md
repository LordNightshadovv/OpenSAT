# Learning engine

## Operational principles

- **Retrieval practice:** ask the learner to recover a method or guardrail before showing help.
- **Spacing:** schedule the next review using prior success, confidence, delay, help use, similarity, timing, recurrence, and test date.
- **Worked examples:** use explicit reasoning for new or weak skills, then fade one support at a time.
- **Contrastive examples:** compare two near-neighbor options or methods so the discriminating feature is visible.
- **Interleaving:** mix question types after the learner can recognize and execute the basic method.
- **Variable practice:** change surface form and context while preserving the target operation.
- **Near/far transfer:** move from a small surface change to a different passage or rhetorical context only when evidence supports it.
- **Metacognitive calibration:** capture confidence before answer reveal and compare it with evidence and result.
- **Targeted feedback:** name the mechanism and next guardrail; avoid generic “careless” feedback.
- **Deliberate practice:** every item has a diagnostic purpose, selection reason, success criterion, and exit condition.

Do not implement one universal memory curve. The local review heuristic is transparent and replaceable; it is not an efficacy claim.

## Future-practice difficulty

`get_difficulty_recommendation` combines the score-band prior and available per-skill stage with the most recent Reading and Writing correctness, item time relative to the manifest threshold, confidence, answer changes, fragile-correct outcomes, and help use. A band is the starting prior, not the final difficulty; a weak skill-stage signal can add a near scaffold inside an otherwise difficult set.

- Require at least four recent observations before evidence can move the centre tier.
- High accuracy plus fast, well-calibrated work may raise the centre tier.
- High accuracy plus fast work with a high-confidence miss increases the share of harder items while retaining a near-transfer calibration check.
- Repeated low accuracy, slowness, or help use can temporarily add scaffolding, but never below the band's safety floor.
- A single miss never confirms a weakness, and raw speed never overrides a calibration problem.

The returned `target_tier`, `stretch_tier`, and `stretch_share` control future item selection only. They do not mutate an already-issued sprint and are not an official score estimate.

## On-demand follow-up sessions

After a sprint or other response submission, call `get_on_demand_recommendations` to turn issue-specific evidence into optional session blueprints. This is a separate follow-up layer; it does not silently extend or mutate the daily 20-minute plan.

- Incorrect or omitted responses recommend a short mistake autopsy, mechanism-matched worked example, targeted practice, and near-transfer check.
- Correct-but-slow responses recommend retrieval plus timed precision practice and a near-miss review.
- Correct-but-uncertain or changed responses recommend confidence calibration and contrastive distractor work.
- Open review-queue entries without a recent response recommend delayed retrieval and near or mid transfer.

High overall accuracy must not suppress a recommendation when timing, confidence, answer changes, help use, or a due review indicates fragility. Clean, fast, calibrated responses with no open review appropriately produce no issue-specific session. Every recommendation states its evidence and remains provisional until an autopsy and recurring evidence support a broader diagnosis.

## Session-start clock and scheduled reviews

Every new practice session begins with one system-local clock snapshot through `get_session_start_context`. The snapshot records the checked local date, time, timezone label, and UTC offset, then resolves open review-queue entries whose `due_at` date is today or earlier. `build_daily_session` performs the same check automatically and returns the resulting context with the stored plan.

Due reviews are surfaced as scheduled-session recommendations. They may be embedded in the normal 20-minute sprint or chosen as the smallest on-demand intervention, but they must not silently extend the learner's planned workload. A future review remains closed until its date arrives, and an unfinished issued sprint is resumed rather than rewritten merely because the calendar changed. One due review is marked completed when a later same-skill response is clean, confident, help-free, and on time; that successful transfer remains evidence against the earlier provisional mechanism rather than proof of broad mastery.

## Twenty-minute session budget

The band-adaptive default is always exactly 20 planned minutes in one or two coherent persistence activities. Learning behaviors such as retrieval, calibration, and near-miss capture are embedded inside an activity rather than scheduled as separate context switches. The practice surface may label one to four purpose groups within those activities; these labels do not create extra timers, submissions, or stop-and-restart study blocks. Learner preferences control the group range, with a hard ceiling of four groups and four questions per group.

| Band | Default mix |
| --- | --- |
| 600–640 | 18 guided practice, 2 review/reflection |
| 650–690 | 18 targeted practice, 2 review/reflection |
| 700–740 | 18 interleaved transfer, 2 review/reflection |
| 750–800 | 17 timed precision, 3 review/reflection |

A Strategy Lab replaces the default with 14 minutes of focused diagnostic work and 6 minutes of strategy comparison plus reflection. It remains two persistence activities and stays inconclusive until both conditions have enough observations.

Optional extended sessions must be opt-in and must not make the daily plan secretly depend on extra hours.

## Progression

`Recognize` means identifying a question type or cue. `Explain` means articulating the reason. `Execute` means using the procedure. `Transfer` means handling a changed surface form. `Stabilize` requires delayed, varied, timed, and confidence-calibrated evidence; repeated immediate correctness is not enough.
