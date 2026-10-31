# Visual practice surface

OpenSAT has no native practice GUI in this prototype. When the Visualize capability is available, `sat-daily-sprint` uses it as a temporary interaction surface for generated practice and, when supplied by the learner, a small number of reviewed local-source questions. The surface is not a second learner model and does not persist answers by itself.

## Surface selection

1. Prefer a native OpenSAT interface when one exists in the host client.
2. Use Visualize when there is no native OpenSAT interface and the capability is available.
3. Use a plain text prompt only when neither surface is available, and state that answers are not persisted until the learner sends the required payload.

A future native OpenSAT interface replaces Visualize for the same sprint; the two surfaces must not be used concurrently.

## Interaction contract

The Visualize surface should:

- show the exact simulated-item label for every generated item;
- show the verified provenance tier and source locator for every direct local-source item; a publisher reconstruction must never be labeled official; render every direct item intact, including its complete display, labels, notes, and options;
- collect answers, confidence, timing, apparent difficulty, answer changes, and near-miss signals without collecting credentials or page content;
- keep one or two persistence sections, while allowing one to four labeled purpose groups inside them; purpose groups clarify why adjacent questions belong together and are not separate stop-and-restart activities;
- place one to four questions in each purpose group and validate the complete grouping before rendering;
- provide a section submit button by default, with question-level submission only where immediate feedback is the purpose of the whole block;
- lock a submitted section so retries cannot silently change the learner's evidence;
- provide a final block/finish control with actual minutes and fatigue; reflections are optional, and comments are posted by the learner in ordinary chat after the block;
- send a structured follow-up to the current Codex task, rather than calling a network endpoint or MCP directly.

For every newly generated surface, each question uses a one-shot timer state machine: `locked -> running -> stopped`.

- While `locked`, do not insert the question stem or choices into the visible document. Show only the question number and its Start control.
- Clicking Start inserts that question, starts timing with `performance.now()`, and disables Start. There is no reset or pause control.
- Clicking Stop freezes the elapsed time but leaves the question and selected answer visible. Answer editing after Stop is allowed, but must not restart or change the frozen time; `answer_changed` continues to reflect edits.
- Treat the elapsed value as total response time—reading, display inspection, reasoning, and selection—not as reading time.
- After the learner locks the final answer and stops the timer, require one apparent-difficulty tag—`routine`, `noticeable`, or `intimidating`—before section submission. Collect it before showing correctness, a rationale, or any other feedback. The tag describes how the completed item felt, not an objective difficulty judgment.
- A section cannot submit while any included question is `locked` or `running`.
- Use the reusable controller in `assets/visualize-question-timer.js` or reproduce its state contract inline. Do not use a phone/manual-time field for new surfaces.

The assistant must not say that an answer was recorded merely because the button was clicked. It must confirm successful OpenSAT MCP writes first.

## Submission payload

The payload sent to Codex is intentionally content-free. The transient item manifest held by the assistant supplies the answer key, skill, question type, and provenance. Direct local-source items use `provenance_type`, `source_label`, and `source_locator` in that manifest. The payload must not repeat question text or answer choices.

```json
{
  "schema_version": "1.2",
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
      "apparent_difficulty": "routine",
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

`selected_answer` may be `null` for an omission. Confidence is 1–5; apparent difficulty is `routine`, `noticeable`, or `intimidating`; timing is positive and comes from the monotonic Visualize timer; `almost_choice` is `A`–`D` or `null`; and `submission_id` is the stable `<session_id>:<section>` key across safe retries. `manifest_id` binds the response to the transient answer-key and diagnostic metadata held outside the surface. The final section may submit answers with `reflection: null`; it may include a reflection object only when the learner explicitly chooses to provide one. Comments posted in chat stay outside the payload. Versions `1.0` and `1.1` remain accepted only so already-issued sprints can finish unchanged; all future surfaces use `1.2`.

New surfaces may continue using `diagnostic_core` and `strategy_and_reflection` as persistence sections for a two-activity sprint. Purpose-group labels live inside those sections and do not require additional submissions. The final button is labeled `Submit final block and finish`; a null reflection is valid and does not delay completion. The answer key is never embedded in the Visualize fragment.

## Persistence sequence

The receiving daily-sprint workflow calls the `record_visual_submission` MCP tool. Its service boundary uses `opensat.visualize.validate_visual_submission` to validate the untrusted payload against the learner-owned session and transient manifest, then atomically:

1. records generated items in the generated-item store, while preserving only the locator and provenance tier for direct local-source items;
2. records each response with stable `<session_id>:<item_id>` event keys and no copied content;
3. records strategy-trial observations where applicable;
4. records the section's actual minutes, outcome, and fatigue through the session tools, storing a reflection only if the learner supplied one; and
5. returns `persisted: true` only after the SQLite transaction commits.

Safe retries reuse the stable submission ID and return `created: false`; a retry with different content is rejected. The final section is rejected until the core section has persisted. A legacy incomplete five-activity session with no results is consolidated to the two-block strategy plan at the first accepted submission.

The normal OpenSAT content boundary still applies: no passwords, cookies, tokens, screenshots, page HTML, passages, question text, choices, or official rationales are included in the payload or learner-model export.
