# Learner model

The model is persistent, inspectable, provenance-aware, and designed for later Math support.

## Core entities

| Entity | Purpose | Important fields |
| --- | --- | --- |
| Learner | Identity and preferences | `learner_id`, language, explanation mode, separate score context, band prior, test date, accessibility, session preference, durable practice-presentation preferences under `accessibility_preferences.practice` |
| Assessment | Official or non-official summary | source, assessment type, external id, date, official flag, total/RW/Math scores, domain evidence, import provenance |
| Question event | Response evidence | assessment reference, section/module/locator, result, time and time source, confidence, flag/change state, selected/correct answer metadata, provisional skill, provenance |
| Reasoning response | Student explanation | event, targeted prompt id, response, confidence |
| Diagnostic hypothesis | Cautious interpretation | observed fact, mechanism hypothesis, confidence, supporting and contradicting evidence, status |
| Error signature | Recurring mechanism | code, status, evidence events, recurrence count, last seen, notes |
| Skill state | Learning stage | skill, `recognize` → `explain` → `execute` → `transfer` → `stabilize`, evidence, recurrence risk |
| Review queue | Next useful revisit | due date, reason, skill, recurrence risk, evidence strength, transfer distance |
| Strategy trial | Personalized method experiment | strategy, question type, conditions A/B, results, sample size, provisional conclusion |
| Generated item | Synthetic practice provenance | provider, target skill/signature, intended difficulty, validation status, version, simulated label, specification, exposure history |
| Session | Planned and observed work | planned/actual minutes, band, activities, outcomes, fatigue, completion |

## Evidence rules

- A correct response can be diagnostically important when it is slow, uncertain, changed, or overconfident.
- One mistake can produce a provisional hypothesis, never a broad confirmed weakness.
- A confirmed signature requires recurring evidence from at least two events in the local service.
- “Careless” is not a terminal diagnosis. Replace it with an observable mechanism and condition.
- Official and simulated provenance remain distinct in every assessment and event.
- Generated-item performance cannot become an official SAT score.

## Export contract

Exports are JSON with a schema version, learner profile, safe records, and content-boundary flags. They exclude page captures, official text, screenshots, credentials, API keys, and temporary cache. Export paths must be outside the repository and are written with restrictive local permissions where supported.
