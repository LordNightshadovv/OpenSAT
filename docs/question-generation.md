# Synthetic question-generation pipeline

Generated items are targeted practice, not official content and not a score-conversion instrument.

Read `reading-writing-item-style.md` before specifying or generating a Reading and Writing item. That document translates College Board's public framework into an originality-preserving form, stem, and distractor contract.
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
- one or more substantive difficulty mechanisms;
- public style-reference identifiers, never copied source content;
- timing expectation;
- transfer distance from recent practice.

## Independent gates

Run these as separate logical stages, even if one model executes them in the first version:

1. Generate a candidate.
2. Solve independently without trusting the proposed key.
3. Check that exactly one option is defensible.
4. Inspect every distractor and its intended mechanism.
5. Check for unintended shortcuts.
6. Check wording and grammatical consistency.
7. Check the target skill blueprint and public stem family against `reading-writing-item-style.md`.
8. Check that the stated difficulty comes from the required reasoning rather than length, jargon, or obscurity alone.
9. For Rhetorical Synthesis, check that the hypothetical-student notes scenario and writerly goal are present; reject detached `Goal:` worksheet framing.
10. Check that the item is not a near-copy of stored or visible official or third-party material.
11. Approve, revise, or reject.
12. Label clearly as simulated.

The local `generation.pipeline` enforces the presence of these validation stages and returns `needs_revision` until all boolean checks pass. It also validates purpose-group layouts so a presentation group cannot silently grow past four questions. The first-phase tests use wholly synthetic placeholders.

## Provider boundary

Targeted item generation stays inside OpenSAT. A future Gemini/Princeton Review integration is represented as a module-level provider stub because it may return complete modules rather than selectable individual questions. It is not live and no API key is accepted by this repository.

## Required label

Every generated item must display: `Simulated SAT-style practice — not an official College Board question`.
