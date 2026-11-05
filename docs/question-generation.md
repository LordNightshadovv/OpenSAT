# Synthetic question-generation pipeline

Generated items are targeted practice, not official content and not a score-conversion instrument.

Read `reading-writing-item-style.md` and `item-fidelity.md` before specifying or generating a Reading and Writing item. Together they define an originality-preserving form, distractor, and reading-to-answer load contract.
Use `public-question-patterns-2026.md` only to choose a source-backed *abstract* trap mechanism. Do not use its linked official or recalled examples as item text, answer keys, or difficulty labels.

## Item specification

Start with a structured specification containing:

- SAT domain, skill, and subskill;
- question type and College Board-aligned public stem family;
- target instructional band and intended difficulty;
- cognitive operation;
- target error signature;
- passage/stimulus constraints;
- correct-answer rationale;
- distractor mechanisms;
- for each wrong choice, the plausible misreading and minimum sufficient passage constraint that defeats it;
- one or more substantive difficulty mechanisms;
- public style-reference identifiers, never copied source content;
- timing expectation;
- calibration cohort and multi-proxy fidelity targets for a cohort-calibrated hard item;
- transfer distance from recent practice.

## Independent gates

For hard items, build a pool of plausible wrong choices before selecting the final three:

1. Extract abstract trap mechanisms from reviewed same-family questions. Record each wrong choice's semantic mutation and the exact word, relation, scope, or comparison that defeats it. Never transfer source wording.
2. Make near-neighbors by changing one semantic feature of the key, such as degree, agent, direction, time, or comparison group. Verify the change actually makes the choice wrong under the stem.
3. Simulate a plausible fast-reader mistake, such as overlooking a pivot or confusing two referents, and draft the answer that mistake would produce. This generates candidates; it does not show that a real learner would pick them.
4. Find the *minimum sufficient constraint* that defeats each candidate. Remove each cited fact in turn; if the choice still fails, that fact was unnecessary. The closest wrong choice should survive gist reading and fail on a small, decisive distinction. Reject any item with two defensible keys.
5. Have a fresh solver answer the complete item without its key and give brief reasons for eliminations. Prefer a different model or context when available. Fast dismissal, uncertainty, and long reasoning prioritize review, but model confidence and latency are not student difficulty measures.
6. Inspect the choices alone. If length, tone, grammar, specificity, or qualification reveals the likely key, rewrite them, then repeat the full-item solve.

**Stimulus non-disclosure rule:** Present facts, evidence, and relationships naturally. Do not tell the learner which interpretation to reject, what the author does not claim, why a tempting alternative fails, or what inference a fact cannot support. Do not add editorial caveats, self-justifications, or defensive clarification to protect the intended key. Only a concise definition of a niche term needed for understanding may clarify the stimulus. Preserve qualifications that genuinely belong to the proposition without spelling out the answer. Run `profile_item_load` on the final displayed text; a nonempty `body.stimulus_disclosure_flags` blocks approval until revision. The required `stimulus_non_disclosure_check` is a separate review because pattern screening misses subtler disclosures.

Run these as separate logical stages, even if one model executes them in the first version:

1. Generate a candidate.
2. Solve independently without trusting the proposed key.
3. Check that exactly one option is defensible.
4. Inspect every distractor and its intended mechanism.
5. For a hard item, identify one dominant near-neighbor distractor. Confirm that it remains plausible after a gist-level reading, preserves most relevant facts, and fails exactly one decisive constraint. Match it to the correct answer in grammar, length, specificity, and polish.
6. Reject obvious-opposite or unrelated filler choices. The other two distractors must be locally plausible even if they are easier to eliminate than the dominant distractor.
7. Check for unintended shortcuts, including a correct option that is uniquely cautious, detailed, qualified, comprehensive, or syntactically different.
8. Check wording and grammatical consistency.
9. Check the target skill blueprint and public stem family against `reading-writing-item-style.md`.
10. Check that the stated difficulty comes from the required reasoning rather than length, jargon, or obscurity alone.
11. For Rhetorical Synthesis, check that the hypothetical-student notes scenario and writerly goal are present; reject detached `Goal:` worksheet framing.
12. Check that the item is not a near-copy of stored or visible official or third-party material.
13. Require an independent solver to name both the key and the smallest fact that defeats the dominant distractor. If two choices remain defensible under the exact task, revise or reject; ambiguity is not desirable difficulty.
14. For a cohort-calibrated hard item, compare body, display, reasoning, options, and expected total-response-time proxies with at least three visually reviewed questions in the same family. Reject underloading and cosmetic padding.
15. Approve, revise, or reject.
16. Label clearly as simulated.

## Direct local-source exception

The generation pipeline remains originality-only. A Daily Sprint may separately display one or two direct questions from a learner-supplied local archive when the daily-sprint workflow has visually checked the question and publisher key, checked prior exposure, and labeled provenance precisely. Render the complete body, display, labels, notes, and answer choices. If anything is shortened or reconstructed, it is not a direct archive question. Direct content is transient source material: do not store it in this repository, the learner model, exports, or response payloads.

The local `generation.pipeline` enforces the presence of these validation stages and returns `needs_revision` until all boolean checks pass. When `fidelity_targets` are declared, it checks the submitted surface/reasoning profile against those rules. It also validates purpose-group layouts so a presentation group cannot silently grow past four questions. The tests use wholly synthetic placeholders.

## Provider boundary

Targeted item generation stays inside OpenSAT. A future Gemini/Princeton Review integration is represented as a module-level provider stub because it may return complete modules rather than selectable individual questions. It is not live and no API key is accepted by this repository.

## Required label

Every generated item must display: `Simulated SAT-style practice — not an official College Board question`.
