---
name: sat-onboarding
description: Set up or revise an OpenSAT learner profile for onboarding requests, including preferred language, separate Reading and Writing/Math score context, provisional score-band prior, test date, accessibility preferences, and local-versus-portable capability disclosure.
---

# SAT Onboarding

## Workflow

Read the shared learner-model contract in `../../docs/learner-model.md` when field-level decisions matter. Use `initialize_learner`, `update_learner_preferences`, and `get_capabilities` when the local MCP server is available; otherwise keep the setup explicitly temporary or offer a learner-model import/export.

1. Ask for interface language: English, 中文, or bilingual.
2. Ask for the learner's actual Reading and Writing score directly. Accept “unknown”; never infer it from total score or Math. Ask for Math and total separately only as optional context.
3. Invite recent missed, omitted, uncertain-correct, slow-correct, or changed-answer items first. Accept item metadata or the learner's own short descriptions; do not require copied question content. If none are available, offer an original calibration item or direct the learner to Bluebook practice or their own practice book. Never search, fetch, cache, mirror, copy, or replicate official College Board Student Question Bank or other official question-bank items. Ask whether the learner has a fully local, visually reviewed collection of reconstructed past-paper references for optional direct practice. Do not accept their separate hard-problem compilation as a direct-practice source or fidelity-calibration cohort.
4. First ask the learner which of their own goals, mistakes, or reasoning moves they want to work on. When no learner evidence is available, ask for their own goals or mistake descriptions, or offer an original calibration item before suggesting any mechanism. Do not invent personalized mechanisms. Once their own targets are recorded or calibration is complete, offer these seven reasoning mechanisms as an optional framework, in this order, with the full descriptions:
   1. **True-but-task-wrong evidence:** the choice is supported but does not answer the exact question.
   2. **Scope, strength, and causality:** a claim is too broad, too strong, or makes an unsupported causal leap.
   3. **Comparison, control, denominator, and direction:** the groups, baseline, quantity, or direction of a comparison is misread.
   4. **Rhetorical function versus content:** the choice repeats what a sentence says but misses what it does in the passage.
   5. **Cross-text overreaction:** a relationship between the texts is overstated or a real disagreement is flattened.
   6. **Rhetorical synthesis goal drift:** relevant facts are used but the requested purpose or audience goal is missed.
   7. **Syntactic proximity:** a nearby word or phrase is attached to the wrong clause, modifier, or relationship.
5. After the optional seven-mechanism framework, offer alternate organization by official domain/skill, error process, or timing/confidence. The learner may select or switch organization at any time, keep their own framing, or choose any explicit subset of the seven mechanisms. Persist explicit choices under learner practice preferences and preserve them when other preferences are updated.
6. Ask for the next intended test date when known and record accessibility, session-length, and practice-presentation preferences.
7. Explain that the score band is an instructional prior revised from R&W evidence, not a rigid curriculum or score prediction. If R&W is unknown, retain the neutral unknown-R&W prior regardless of total or Math score.
8. Offer an authorized, read-only import of score summaries only, manual score entry, or temporary no-import setup. Do not import or retain question text, answer choices, screenshots, or other item content. State which capabilities are actually available and do not imply an import occurred without authorization and a successful read. Initialize one learner profile and return its learner id, prior band, explanation mode, storage mode, focus choice, archive-practice preference, and next suggested workflow.

## Band interpretation

- Use `600–640`, `650–690`, `700–740`, and `750–800` as pilot priors.
- Use only the actual R&W score to choose the R&W prior. If it is unknown, use the neutral `650–690` prior; total and Math scores are context only.
- For an actual R&W score of 780–800, default to mistake-first work, then schedule evidence-supported weakness practice and delayed transfer, with mixed broad-skill work to detect emerging weaknesses. Let the learner's recent evidence select the focus subset.
- Retain the existing 750–770 precision and near-miss defaults; do not silently apply the 780–800 sequence solely because the stored broad band is `750–800`.
- Treat the prior as subject- and skill-sensitive: a high overall score does not remove foundation needs.
- Keep Reading and Writing/Math evidence separate so future Math support can reuse the learner model.

## Disabled source workflow

Do not search, fetch, cache, mirror, or replicate official College Board Student Question Bank or other official question-bank items, and do not compile hard problems from them. Use recent learner evidence, original calibration, Bluebook practice, the learner's own practice book, or fully local reviewed reconstructed past-paper references as described above. A separate hard-problem compilation is excluded from direct practice and fidelity calibration. Original OpenSAT items must be newly authored and must not be derived from an official question-bank item.

## Safety

Never ask for a password, token, or authentication code. Never imply that a browser scan or official score import happened when it did not. Do not promise a score gain.
