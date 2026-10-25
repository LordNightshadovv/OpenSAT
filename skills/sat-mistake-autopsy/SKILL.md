---
name: sat-mistake-autopsy
description: Analyze one SAT Reading and Writing mistake, omission, uncertain correct answer, slow response, or answer change by asking adaptive reasoning questions, separating observed facts from hypotheses, and creating only a provisional error signature when evidence is insufficient for recurrence.
---

# SAT Mistake Autopsy

## Workflow

Read `../../docs/diagnostic-taxonomy.md` and use the same learner id and question-event record as every other workflow. For a public-item comparison or a high-score near miss, consult `../../docs/public-question-patterns-2026.md` for possible mechanisms and source status. Ask questions before delivering an explanation.

1. Call `get_session_start_context` before beginning. Surface any due or overdue review that matches the event; do not silently add unrelated scheduled work to the autopsy.
2. Record the event’s provenance, result, timing, confidence, answer-change state, and provisional skill. Include correct-but-uncertain, slow, or changed events when diagnostically important.
3. Ask only the smallest set that reduces uncertainty:
   - What did you think the question was asking?
   - What evidence or grammatical structure did you use?
   - Were you deciding between two options?
   - How confident were you?
   - Did time pressure, rereading, or an answer change affect the decision?
   - For a two-choice near miss, which exact word, comparison, clause, or writerly goal separated your first choice from the final choice?
   - After you answered but before feedback, did the item feel routine, noticeable, or intimidating?
4. Label the response as an observed fact, diagnostic hypothesis, or confirmed recurring pattern.
5. Choose a named mechanism such as `scope_expansion`, `qualifier_omission`, `structural_misparse`, or `time_triggered_rushing` only when the evidence fits.
6. Record a provisional hypothesis and the smallest next intervention. Use `insufficient evidence to diagnose` when competing explanations remain plausible.
7. Confirm a signature only after recurring evidence and contradictory evidence have been considered.
8. After recording the autopsy evidence, use `get_on_demand_recommendations` to offer the smallest matching follow-up session: worked example plus near transfer for a miss, retrieval plus precision work for slow correctness, or calibration/contrast for uncertain or changed answers.

## Feedback format

Return a compact record:

- Observed fact
- Current hypothesis and confidence
- Evidence for and against
- Student-facing guardrail
- Next review/transfer condition

Never use “careless” as a terminal diagnosis, never infer a broad weakness from one mistake, and never persist official passage/question content.
An official or recalled example illustrates a possible trap; only the learner's observed answer and reasoning can support a learner-specific signature. Keep unverified recall keys out of scoring and feedback.
Treat a routine-looking high-confidence miss as a silent-danger event and a routine-looking fragile correct response as concealed friction. These are event labels, not proof that the item is objectively hard or that the learner has a confirmed weakness.
