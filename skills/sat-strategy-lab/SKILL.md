---
name: sat-strategy-lab
description: Design or run a SAT Strategy Lab trial when a learner wants to compare solving procedures; define applicable question types, paired conditions, benefits, downsides, exclusion conditions, and evidence thresholds for personalization within the 20-minute session.
---

# SAT Strategy Lab

## Workflow

Read `../../docs/learning-engine.md` and use `begin_strategy_trial`/`record_strategy_trial_result` when local MCP is available. A strategy is a hypothesis to test, not a universal trick.

1. Call `get_session_start_context` before beginning. If a due review is more urgent than the proposed comparison, surface that conflict; do not silently extend the 20-minute plan.
2. Define the strategy, applicable question types, exact procedure, proposed benefit, possible downside, and conditions where it should not be used.
3. Choose comparable synthetic or authorized practice items. Do not copy official content.
4. Define condition A and condition B, preferably paired or counterbalanced.
5. Run a 3–5 minute trial by replacing part of the daily sprint, not adding work.
6. Record accuracy, time, rereading, confidence, answer changes, and notable failure modes.
7. Keep the result inconclusive until both conditions have enough observations. The local service requires at least two observations per condition for a provisional comparison. Do not require a reflection; the learner may post comments in ordinary chat.
8. Personalize cautiously: recommend a method only when the evidence is consistent with the question type and downside conditions.

## Example cards

- Paraphrase the task before reading notes for rhetorical synthesis.
- Read answer options before notes when option comparison is the proposed advantage.
- Mark clause boundaries before punctuation decisions.
- Set a time threshold before moving on.
- Review flagged questions in a defined order.

Each card must include an exit condition and a way to detect when the strategy should not be used. Do not call one-item improvement a causal result. Report time/accuracy/confidence tradeoffs and keep the learner’s original workload visible.
