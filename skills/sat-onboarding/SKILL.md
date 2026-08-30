---
name: sat-onboarding
description: Set up or revise an OpenSAT learner profile for onboarding requests, including preferred language, separate Reading and Writing/Math score context, provisional score-band prior, test date, accessibility preferences, and local-versus-portable capability disclosure.
---

# SAT Onboarding

## Workflow

Read the shared learner-model contract in `../../docs/learner-model.md` when field-level decisions matter. Use `initialize_learner`, `update_learner_preferences`, and `get_capabilities` when the local MCP server is available; otherwise keep the setup explicitly temporary or offer a learner-model import/export.

1. Ask for interface language: English, 中文, or bilingual.
2. Ask for current score context, recording Reading and Writing and Math separately when available. Accept a score range or “unknown”; do not invent precision.
3. Ask for the next intended test date when known and record accessibility, session-length, and practice-presentation preferences. Practice preferences may include preferred purpose-group count, maximum questions per group, difficulty emphasis, and style constraints.
4. Explain that the score band is an instructional prior that will be revised from evidence, not a rigid curriculum or score prediction.
5. Offer authorized browser-assisted import, manual score import, or temporary no-import setup. State which capabilities are actually available.
6. Initialize one learner profile and return its learner id, prior band, explanation mode, storage mode, and next suggested workflow.

## Band interpretation

- Use `600–640`, `650–690`, `700–740`, and `750–800` as pilot priors.
- Treat the prior as subject- and skill-sensitive: a high overall score does not remove foundation needs.
- Keep Reading and Writing/Math evidence separate so future Math support can reuse the learner model.

## Safety

Never ask for a password, token, or authentication code. Never imply that a browser scan or official score import happened when it did not. Do not promise a score gain.
