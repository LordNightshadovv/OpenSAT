---
name: sat-daily-sprint
description: Build an adaptive OpenSAT Daily Sprint when a learner asks what to practice today; enforce a useful 20-minute budget, band-specific learning-science defaults, targeted selection reasons, success criteria, exit conditions, and learner-model updates.
---

# SAT Daily Sprint

## Workflow

Read `../../docs/learning-engine.md`, `../../docs/learner-model.md`, `../../docs/question-generation.md`, `../../docs/reading-writing-item-style.md`, and `../../docs/visual-practice-surface.md`. Use `build_daily_session` when local MCP is available; otherwise produce a temporary plan and say it is not persisted.

1. Load the current band prior, open review queue, recurring risks, test date, and `get_difficulty_recommendation`. Use the returned target tier, stretch tier/share, priority skills, correctness, timing, and calibration evidence for **future** item selection; never rewrite an already-issued block.
2. Select the smallest high-value intervention. Do not optimize for question count.
3. Build exactly 20 planned minutes in **one coherent activity or two substantial activities**. Do not schedule a chain of stop-and-restart mini-activities. Each activity must have a purpose, selection reason, success criterion, and exit condition.
4. Adapt the mix:
   - `600–640`: retrieval, worked example, blocked practice, transfer.
   - `650–690`: procedure reliability, delayed review, distractor analysis, guided fading.
   - `700–740`: interleaving, contrastive distractors, transfer, efficiency.
   - `750–800`: near-misses, calibration, realistic timing, fatigue and variance.
5. Embed calibration, near-miss capture, and strategy observations inside the main activity when relevant. A brief review/reflection may be the second activity and records one observed fact, one uncertainty, and the next review.
6. Load `accessibility_preferences.practice` from the learner profile. Treat `purpose_groups` as presentation labels inside the coherent activity, not as extra activities. Honor `preferred_min`, `preferred_max`, and `max_questions_per_group`; the safe surface ceiling is four groups and four questions per group.
7. Specify and validate each Reading and Writing item through `../../docs/reading-writing-item-style.md`. For a 750–800 learner, center on hard items, apply the adaptive stretch share, and use lower tiers only for an explicit calibration or scaffold purpose.
8. Record actual minutes, activity outcomes, confidence, and fatigue. Do not punish a learner for stopping at the planned exit condition.
9. After a persisted sprint section or completed session, call `get_on_demand_recommendations`. Present the highest-value optional follow-up blueprints when recent evidence is incorrect, omitted, slow, uncertain, changed, help-dependent, or due for review. Do not suppress these recommendations just because aggregate accuracy is high; if no issue-specific evidence exists, say so explicitly.

## Delivery surface

- Use a native OpenSAT practice interface when one is available.
- When no native OpenSAT interface is available but Visualize is available, **must use Visualize** for the practice surface. Visualize is the presentation and input layer only; the OpenSAT learner model remains the source of truth.
- A future native OpenSAT interface supersedes Visualize. Do not use both surfaces for the same sprint.
- Render generated items with the exact label `Simulated SAT-style practice — not an official College Board question`.
- Keep submission sections aligned to the one or two persistence activities, but permit one to four labeled purpose groups inside them. A learner preference may request three or four groups. Each group contains one to four questions and shares one explicit reasoning purpose. Provide one submit control for each persistence section; the final section's control is labeled `Submit reflection and finish` and may submit its answers and reflection together. Question-level submission may be used only when immediate feedback is the purpose of the whole activity.
- Every future Visualize question starts locked. Its stem and choices appear only after that question's Start timer control is clicked. Stop freezes a `performance.now()`-based elapsed time while leaving the question and selected answer visible. Keep post-stop answer editing enabled, retain `answer_changed`, and block section submission until every timer is stopped. Use submission schema `1.1` and the controller contract in `../../assets/visualize-question-timer.js`.
- Collect only the answer payload described in `../../docs/visual-practice-surface.md`: item id, selected option, confidence, timing, answer-change/near-miss signals, activity minutes, fatigue, and reflection. Do not send question text, passages, choices, screenshots, or page HTML back through the submission payload.
- A Visualize control sends the structured payload to the current Codex task with `window.openai.sendFollowUpMessage`; it must not make network requests or attempt direct MCP calls. Lock a submitted section and show “sent; awaiting recording confirmation” until the receiving OpenSAT workflow confirms persistence.

## Submission handling

When a Visualize submission arrives:

1. Treat the payload as untrusted input. Validate its schema, manifest id, stable submission id, session id, section, item ids and order, answer alphabet, confidence, timing, and ownership before using it.
2. Resolve item ids against the transient item manifest for this sprint. If the manifest is unavailable or the scope does not match, do not guess an answer key or record the event; ask for a fresh submission.
3. Record generated-item provenance with `record_generated_item` and record each submitted response with `record_question_event`, using stable event keys such as `<session_id>:<item_id>`, `provenance_type="simulated"`, and abstract metadata only. Correct, omitted, uncertain, slow, changed, and incorrect responses may all be diagnostically useful.
4. Record strategy-lab observations with `begin_strategy_trial`/`record_strategy_trial_result` when applicable, and record block minutes, outcomes, fatigue, and reflection with `record_activity_result`.
5. After persistence, use the returned or separately fetched on-demand recommendations to offer an optional follow-up. Keep the evidence boundary visible: a slow correct response merits precision work, not a claimed content diagnosis; a single miss merits an autopsy and provisional hypothesis, not a confirmed signature.
6. Treat a payload as received, not persisted, until the MCP calls succeed. Report partial failures and preserve the stable submission id for a safe retry. Never claim that a score changed; generated-item accuracy remains simulated evidence.

## Budget guardrails

- The default plan must remain useful at 20 minutes.
- A planned sprint has at most two persistence activities. Retrieval, calibration, timing, near-miss capture, and purpose-group labels are behaviors inside a coherent activity, not separate mandatory chunks.
- A purpose group must contain fewer than five questions. Validate the complete grouping before rendering.
- Strategy trials replace part of the sprint; they do not silently add time.
- Optional extension is opt-in and must not change the recorded planned budget.
- Generated-question accuracy is not an official score.

## Completion

End with the next evidence request: delayed retrieval, near transfer, far transfer, calibration, or official reassessment. Never claim the learner’s score moved because a sprint was completed.
