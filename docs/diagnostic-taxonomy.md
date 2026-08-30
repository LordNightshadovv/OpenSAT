# Diagnostic taxonomy

## Three evidence layers

Every autopsy and progress review must label:

1. **Observed fact** — what the response, timing, confidence, or student explanation directly shows.
2. **Diagnostic hypothesis** — a mechanism that could explain the fact, with confidence and evidence limits.
3. **Confirmed recurring pattern** — a signature supported across events and not contradicted by later evidence.

When the evidence does not discriminate among mechanisms, write `insufficient evidence to diagnose` and collect the smallest next observation.

## Error signatures

| Code | Mechanism |
| --- | --- |
| `qualifier_omission` | Misses a limiting word or condition. |
| `unsupported_strengthening` | Chooses a stronger claim than the evidence supports. |
| `scope_expansion` | Broadens a local claim beyond the task. |
| `task_goal_drift` | Solves a nearby task rather than the exact goal. |
| `structural_misparse` | Misreads clause, modifier, sentence, or passage structure. |
| `premature_answer_selection` | Commits before comparing stem, evidence, and options. |
| `weak_evidence_threshold` | Accepts plausible language without enough evidence. |
| `unsupported_answer_change` | Changes a defensible answer without stronger evidence. |
| `time_triggered_rushing` | Accuracy changes after a time or fatigue threshold. |
| `overconfidence` | Confidence exceeds evidence quality or stability. |
| `attention_lapse` | A repeatable attention failure appears in a specified condition. |
| `vocabulary_neighbor_confusion` | Confuses a contextual near-synonym. |

## Status transitions

```text
provisional -> supported -> confirmed
       |           |             |
       +---------> rejected <---+
rejected -> provisional when new evidence warrants reopening
```

The service blocks unsupported jumps and requires at least two evidence events for `confirmed`.

## Autopsy prompts

Choose rather than dump prompts. Start with the task interpretation, then ask for evidence or grammatical structure. Add confidence, answer-change, or time-pressure prompts only when those fields reduce uncertainty. Do not reveal the answer and immediately ask the student to agree with an explanation.
