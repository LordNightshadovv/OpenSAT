# Item-fidelity calibration

Item fidelity means matching the reading-to-answer work of a reviewed question family without copying its content. It is not a claim of equal psychometric difficulty or evidence of score improvement.

## Candidate watchlists are not universal diagnoses

A learner-supplied taxonomy—such as seven focus types—and its past-paper or hard-set references is a useful candidate watchlist. It can organize archive review, seed mixed calibration, and identify mechanisms worth testing. It must not become every learner's default curriculum.

Promote a watchlist type to a recurring learner focus only when item-level evidence supports it: errors or omissions, slow correct responses, low confidence, answer changes, help dependence, apparent-difficulty mismatch, or weak near/far transfer. Keep the type provisional when evidence is sparse or comes from one item.

## Calibration cohort

Before declaring a hard simulation fidelity-calibrated, visually review at least three source questions from the same skill and display family. Record only abstract measurements and source locators; never copy source text, choices, displays, or rationales into the plugin repository. Calibrate to the cohort, not one question, and keep provenance tiers separate.

## Multi-proxy profile

Use several proxies because word count alone is easy to game and does not measure comprehension difficulty.

- Body: total/content tokens, sentences, and reviewer-annotated finite clauses, subordinate clauses, propositions, and relations.
- Display: rows, columns, cells, nonempty/numeric cells, unit labels, legends, notes, and footnotes.
- Reasoning: comparisons, variables, direction checks, basis changes, and the smallest decisive constraint.
- Options: locally plausible distractors, whether the dominant near-neighbor fails exactly one constraint, and its content-length ratio to the key.
- Timing: expected total response-time band and, when available, the cohort median and interquartile range.

`profile_surface_load` computes deterministic body, table, and option proxies. Manual annotations supply reasoning and clause structure. Its output must retain `surface-load proxies; not comprehension difficulty`.

For hard cohort-calibrated simulations:

- body content tokens should normally be at least the greater of cohort P25 and 80% of its median, and no more than 125% of its median unless justified;
- sentence, proposition, relation, and display dimensions should not fall below the declared cohort floor;
- quantitative items must preserve the task-relevant comparisons, variables, direction checks, and display fields required by the family;
- require three locally plausible distractors, one dominant distractor failing exactly one decisive constraint, and a dominant/key content-token ratio of 0.75–1.33;
- reject padding: prose, cells, jargon, or arithmetic that does not participate in the reasoning cannot repair an underloaded item.

Tables, graphs, paired texts, notes sets, and prose-only questions need family-specific floors.

## Direct-source integrity and timing

A direct local-source question must be rendered intact after visual review: full body, complete display, all labels and notes, exact options, and a verified key. If anything is shortened or reconstructed, present it as a simulation and apply originality and fidelity gates.

The current timer measures total response time from reveal to Stop: reading, display inspection, reasoning, and selection. Never call it reading time. A single learner's times can motivate an audit but cannot set a universal threshold.

A future surface may pilot an optional `Reading complete` event. Do not add it to the learner model yet: it is subjective, changes behavior, and may create reactivity. Validate it first and keep pilot data transient.

## Implementation contract

Generated hard items may declare `fidelity_targets`. Targets must identify a cohort with at least three reviewed sources and may set minimum, maximum, or exact rules over `fidelity_profile`. `validate_candidate` returns `needs_revision` when the profile is missing or a rule fails. These gates validate declared artifacts and arithmetic only—not official difficulty, efficacy, or score gains.
