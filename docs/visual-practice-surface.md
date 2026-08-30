# Visual practice surface

OpenSAT has no native practice GUI in this prototype. When the Visualize capability is available, `sat-daily-sprint` uses it as a temporary interaction surface for generated practice. The surface is not a second learner model and does not persist answers by itself.

## Surface selection

1. Prefer a native OpenSAT interface when one exists in the host client.
2. Use Visualize when there is no native OpenSAT interface and the capability is available.
3. Use a plain text prompt only when neither surface is available, and state that answers are not persisted until the learner sends the required payload.

A future native OpenSAT interface replaces Visualize for the same sprint; the two surfaces must not be used concurrently.

## Interaction contract

The Visualize surface should:

- show the exact simulated-item label for every generated item;
- collect answers, confidence, timing, answer changes, and near-miss signals without collecting credentials or page content;
- keep one or two persistence sections, while allowing one to four labeled purpose groups inside them; purpose groups clarify why adjacent questions belong together and are not separate stop-and-restart activities;
- place one to four questions in each purpose group and validate the complete grouping before rendering;
- provide a section submit button by default, with question-level submission only where immediate feedback is the purpose of the whole block;
- lock a submitted section so retries cannot silently change the learner's evidence;
- provide a final reflection/finish control for one observed fact, one uncertainty, next review, actual minutes, and fatigue;
- send a structured follow-up to the current Codex task, rather than calling a network endpoint or MCP directly.

For every newly generated surface, each question uses a one-shot timer state machine: `locked -> running -> stopped`.

- While `locked`, do not insert the question stem or choices into the visible document. Show only the question number and its Start control.
- Clicking Start inserts that question, starts timing with `performance.now()`, and disables Start. There is no reset or pause control.
- Clicking Stop freezes the elapsed time but leaves the question and selected answer visible. Answer editing after Stop is allowed, but must not restart or change the frozen time; `answer_changed` continues to reflect edits.
- A section cannot submit while any included question is `locked` or `running`.
- Use the reusable controller in `assets/visualize-question-timer.js` or reproduce its state contract inline. Do not use a phone/manual-time field for new surfaces.

The assistant must not say that an answer was recorded merely because the button was clicked. It must confirm successful OpenSAT MCP writes first.

## Submission payload

The payload sent to Codex is intentionally content-free. The transient item manifest held by the assistant supplies the answer key, skill, and question type; the payload must not repeat question text or answer choices.

```json
{
  "schema_version": "1.1",
  "surface": "visualize",
  "manifest_id": "manifest_example",
  "session_id": "session_example",
  "submission_id": "session_example:diagnostic_core",
  "section": "diagnostic_core",
  "answers": [
    {
      "item_id": "daily-example-04",
      "selected_answer": "A",
      "confidence": 4,
      "time_seconds": 42,
      "answer_changed": false,
      "almost_choice": null,
      "help_used": false,
      "timing_source": "visualize_monotonic_timer",
      "timer_state": "stopped"
    }
  ],
  "actual_minutes": 7,
  "fatigue": "low",
  "reflection": null
}
```

`selected_answer` may be `null` for an omission. Confidence is 1–5; timing is positive and comes from the monotonic Visualize timer; `almost_choice` is `A`–`D` or `null`; and `submission_id` is the stable `<session_id>:<section>` key across safe retries. `manifest_id` binds the response to the transient answer-key and diagnostic metadata held outside the surface. The final section may submit its answers and a reflection object together. Version `1.0` remains accepted only so an already-issued legacy sprint can finish unchanged; all future surfaces use `1.1`.

New surfaces may continue using `diagnostic_core` and `strategy_and_reflection` as persistence sections for a two-activity strategy sprint. Purpose-group labels live inside those sections and do not require additional submissions. The final button is labeled `Submit reflection and finish`. The answer key is never embedded in the Visualize fragment.

## Persistence sequence

The receiving daily-sprint workflow calls the `record_visual_submission` MCP tool. Its service boundary uses `opensat.visualize.validate_visual_submission` to validate the untrusted payload against the learner-owned session and transient manifest, then atomically:

1. records each generated item's simulated provenance;
2. records each response with stable `<session_id>:<item_id>` event keys and no copied content;
3. records strategy-trial observations where applicable;
4. records the section's actual minutes, outcome, fatigue, and reflection through the session tools; and
5. returns `persisted: true` only after the SQLite transaction commits.

Safe retries reuse the stable submission ID and return `created: false`; a retry with different content is rejected. The final section is rejected until the core section has persisted. A legacy incomplete five-activity session with no results is consolidated to the two-block strategy plan at the first accepted submission.

The normal OpenSAT content boundary still applies: no passwords, cookies, tokens, screenshots, page HTML, passages, question text, choices, or official rationales are included in the payload or learner-model export.
