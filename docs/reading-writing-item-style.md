# Reading and Writing item-style contract

This contract governs wholly original OpenSAT items. It uses College Board's public framework to match the assessed operation, stimulus form, stem family, and distractor logic. It does **not** authorize copying, lightly paraphrasing, or storing official questions. Third-party difficult-question collections may inform abstract difficulty mechanisms only.

For inspectable examples of these operations and their plausible wrong-answer mechanisms, read [`public-question-patterns-2026.md`](public-question-patterns-2026.md). Its recalled-item leads are unverified and cannot supply an answer key. Transfer only the abstract constraint into a new item.

## Authoritative public references

- [College Board Student Question Bank: Reading and Writing question stems](https://satsuite.collegeboard.org/practice/student-question-bank/reading-writing)
- [College Board Reading and Writing section overview](https://satsuite.collegeboard.org/sat/whats-on-the-test/reading-writing)
- [College Board SAT Suite content domains](https://satsuite.collegeboard.org/higher-ed-professionals/sat-validity/content-domains)
- [College Board Educator Question Bank help and filters](https://satsuiteeducatorquestionbank.collegeboard.org/help)
- [College Board report on cognitively complex digital SAT questions](https://satsuite.collegeboard.org/media/pdf/digital-sat-cognitive-lab-report.pdf)

Recheck these public sources when the specification changes. Record only reference identifiers and derived design rules in item metadata, never official prompts, passages, choices, or rationales.

## Global form

- Use one short stimulus or a related pair followed by one four-option multiple-choice question.
- Keep prose within the digital SAT's public 25–150-word passage range unless the item type is a notes set or an informational graphic.
- Draw contexts from literature, history and social studies, the humanities, and science. The context should be self-contained and should not reward outside knowledge.
- Use the public College Board stem family for the target skill. Do not invent a casual worksheet instruction when the assessment uses a stable testing convention.
- Make all four options grammatically compatible with the stem and locally plausible. Exactly one option must perform the requested operation.

## Skill blueprints

| Domain and skill | Stimulus and stem family | Hard-item construction |
| --- | --- | --- |
| Information and Ideas — Central Ideas and Details | A short literary or informational text; ask for the main idea or a supported detail. | Include several accurate local details, but only one option captures the text's governing relationship without adding scope or causality. |
| Information and Ideas — Command of Evidence, textual | State or imply a claim and ask which finding, quotation, or detail would most directly support or weaken it. | Make distractors relevant to the topic but insufficient for the exact claim, direction, comparison group, or boundary. |
| Information and Ideas — Command of Evidence, quantitative | Pair a text with a small table, bar graph, or line graph and ask which choice uses the data to complete or support the claim. | Require the decisive comparison or endpoint; avoid arithmetic for its own sake. Distractors should cite real values but perform the wrong comparison. |
| Information and Ideas — Inferences | Present enough facts for one warranted extension and ask which choice most logically completes the text. | Require a non-obvious but necessary inferential bridge. Reject choices that add a motive, mechanism, certainty, or population not licensed by the stimulus. |
| Craft and Structure — Words in Context | Use a blank or ask for the contextual meaning of a word. | Use high-utility academic near-neighbors that fit the syntax; only one must fit the precise logical relationship and connotation. Obscurity alone is not difficulty. |
| Craft and Structure — Text Structure and Purpose | Mark a portion or ask about the text's overall purpose. | Test the portion's functional contribution to the whole, not mere topic recognition. Distractors may describe nearby details but must misstate the rhetorical role. |
| Craft and Structure — Cross-Text Connections | Use two concise texts on the same topic; ask how one author would respond to the other or what both would accept. | Build a qualified relation such as refinement, boundary condition, or model revision. Distractors should confuse agreement on facts with agreement on interpretation. |
| Expression of Ideas — Transitions | Present two claims or sentences joined at a blank; ask for the most logical transition. | Make several transitions syntactically possible while only one encodes the exact contrast, continuation, cause, example, or concession. |
| Expression of Ideas — Rhetorical Synthesis | A hypothetical student researching a topic has taken bulleted notes and wants to accomplish a specified writerly goal; ask which choice most effectively uses relevant information from the notes to accomplish that goal. | Every option may be factually supported by the notes, but only one should select and arrange the information required by the goal. Never replace the scenario with a detached `Goal:` label. |
| Standard English Conventions — Boundaries | A sentence or short passage with a blank; options differ primarily in punctuation. | Use realistic clause and modifier structure so the learner must identify sentence boundaries. Do not add unrelated vocabulary traps. |
| Standard English Conventions — Form, Structure, and Sense | A sentence or short passage with a blank; options vary in words or sentence structure. | Test one primary convention such as agreement, verb form, pronoun clarity, modifier placement, or parallel structure while maintaining natural prose. |

## Difficulty contract for a 750–800 learner

Center future Reading and Writing practice on `hard`. A smaller `challenge` share may be added by the adaptive difficulty recommendation. Easy or medium items are permitted only as explicit calibration, prerequisite checks, or recovery after repeated evidence—not as filler.

A hard item must name at least one real difficulty mechanism in its specification:

- `scope_or_strength_discrimination`
- `non_obvious_inferential_bridge`
- `exact_evidence_direction`
- `multi_group_or_endpoint_comparison`
- `cross_text_relation`
- `local_function_with_global_role`
- `rhetorical_goal_information_selection`
- `clause_structure_disambiguation`
- `near_neighbor_semantic_precision`

Passage length, jargon, and rare vocabulary do not count as difficulty mechanisms by themselves.

## Originality and quality gates

Before approval, independently solve the item, verify exactly one defensible answer, inspect each distractor's mechanism, and run the existing shortcut, wording, difficulty, and originality checks. Also require:

- `college_board_style_check`: the item follows the target blueprint and public stem family;
- `difficulty_mechanism_check`: the claimed difficulty is visible in the reasoning, not cosmetic;
- `rhetorical_synthesis_scenario_check` for Rhetorical Synthesis items: the student-notes scenario and writerly goal are both present.

If any gate fails, revise or reject the item. Always display the OpenSAT simulated-item label.
