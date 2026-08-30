# OpenSAT product specification

## Product promise

OpenSAT is a free, bilingual Reading and Writing training laboratory for students who need to understand why they lose points. It is a diagnostic and deliberate-practice engine, not a question-volume counter, generic chatbot, question bank, or answer-explanation wrapper.

The system should help a learner move from an observed response to a cautious mechanism hypothesis, then to the smallest intervention worth testing. It must not guarantee a score increase. The long-term aspiration of a 50-point improvement is a product hypothesis to evaluate, not a claim to make.

## Scope

- Initial subject: SAT Reading and Writing.
- Future subject: Math plugs into the same learner, assessment, event, diagnosis, scheduling, and session contracts.
- Pilot instructional priors: `600–640`, `650–690`, `700–740`, and `750–800`.
- User-facing band labels may render as `600–650`, `650–700`, `700–750`, and `750–800`.
- English, 中文, and bilingual explanations are supported. Simulated SAT-style questions remain in English.

Bands are priors, not curricula. A learner can receive foundation support in one skill and precision work in another.

## Core loop

1. Establish a provisional learner model from score context and a small amount of evidence.
2. Use official material for diagnosis, calibration, reassessment, and transfer validation.
3. Use clearly labeled simulated material for targeted practice between official assessments.
4. Ask the smallest set of reasoning questions that reduces diagnostic uncertainty.
5. Record observed facts, hypotheses, recurring signatures, and contradicting evidence separately.
6. Assign a short intervention with a purpose, success criterion, and exit condition.
7. Revisit through spacing, transfer, timing, confidence calibration, and later official reassessment.

## Recognizable workflows

| Workflow | First-phase behavior |
| --- | --- |
| Onboarding | Capture language, separate Reading and Writing/Math context, test date, and provisional band. |
| Practice Scan | Specify a user-authorized, read-only Chrome flow; implement only manual/import-preview behavior in this slice. |
| Mistake Autopsy | Ask adaptive questions before explaining; keep diagnosis provisional when evidence is thin. |
| Daily Sprint | Produce a genuinely useful 20-minute plan whose minutes sum to 20. |
| Strategy Lab | Test methods in small paired or counterbalanced trials; do not declare a winner from one item. |
| Progress Review | Compare official evidence, transfer, timing, confidence, signatures, and variance. |

## Band defaults

- `600–640`: explicit teaching, bilingual clarification, worked examples, blocked practice, and slower fading.
- `650–690`: question-type recognition, reliable rule retrieval, distractor analysis, and procedure reliability.
- `700–740`: difficult distractor distinctions, interleaving, transfer, efficiency, vocabulary nuance, and strategy selection.
- `750–800`: misses, omissions, correct-but-uncertain/slow/changed responses, overconfidence, fatigue, rare traps, and variance reduction.

## Content boundary

Official SAT or Bluebook material is transient diagnostic context only. Persist derived metadata, not full passages, question text, answer choices, rationales, screenshots, or page HTML. Generated material must carry the exact label `Simulated SAT-style practice — not an official College Board question` and may never be treated as official or used to create an official-looking score.

## First-phase acceptance criteria

The local prototype is acceptable when another developer can install the plugin manifest, run the local MCP server, initialize a learner, record a manual assessment and synthetic event, represent a short autopsy, create a provisional signature, build a 20-minute session, export the model outside Git, and delete it only with explicit confirmation. Browser import, question quality, cross-surface parity, and score improvement remain unvalidated until tested independently.
