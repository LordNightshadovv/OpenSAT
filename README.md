# OpenSAT

OpenSAT is a local-first, bilingual SAT Reading and Writing diagnostic and deliberate-practice prototype. It models why a learner loses points, keeps hypotheses provisional until recurring evidence exists, and assigns targeted work inside a 20-minute daily budget. Future practice difficulty combines the learner's score-band prior with recent correctness, timing, confidence, post-answer pre-feedback apparent difficulty, response stability, and help use.

It is not a question bank, official-score predictor, credential scraper, or score-gain guarantee.

## What is included

- Installable `.codex-plugin/plugin.json` manifest.
- Eight focused skills: onboarding, Practice Scan, Mistake Autopsy, Daily Sprint, Strategy Lab, Progress Review, Question Pattern Research, and plugin Self-Improvement.
- Daily Sprint uses one or two coherent 20-minute persistence activities. Its practice surface may organize the questions into up to four purpose groups of at most four questions each without turning them into separate stop-and-restart blocks. It uses a native OpenSAT interface when available; otherwise its skill requires a Visualize practice surface with section/final submit controls. New Visualize questions stay hidden until their per-question timer starts; stopping freezes time while leaving the question and answer visible. Visualize sends content-free answers back to the assistant, and the OpenSAT MCP service persists only validated derived evidence.
- After an answer is locked and its timer is stopped, new practice surfaces collect a lightweight apparent-difficulty tag (`routine`, `noticeable`, or `intimidating`) before feedback. OpenSAT derives silent-danger and concealed-friction signals from that tag plus outcome evidence; it does not treat the tag as an objective item-difficulty label.
- Local stdio MCP companion with a coherent learner-model tool surface, including a session-start local clock, due-review scheduling, post-sprint on-demand recommendations, and the user-authorized read-only Chrome scan boundary.
- Python standard-library domain core and SQLite migrations.
- Synthetic fixtures and tests; no copied College Board content.
- A sourced [public-question pattern index](docs/public-question-patterns-2026.md) that separates official released examples from dated, unverified exam recollections and turns their reasoning traps into original practice design.
- A bounded plugin-improvement gate that freezes one candidate, checks paired training and held-out receipts against capability floors and token reduction, and keeps learner data out of the research loop. See [`docs/self-improvement.md`](docs/self-improvement.md). No automatic or continuous self-modification runs in the installed plugin.
- Design documents covering product, architecture, capability modes, learner model, diagnostics, learning engine, browser safety, generation, privacy, pilot evaluation, and decisions.

## Personalization after a Daily Sprint

Before a new practice session, OpenSAT calls `get_session_start_context`. It snapshots the system-local date and time, checks for reviews due today or overdue, and returns any matching scheduled-session blueprints. `build_daily_session` includes this same context automatically so calendar-based work cannot be skipped merely because a fresh sprint was requested. Due work is incorporated inside the 20-minute budget or explicitly deferred; it is never added as a hidden extension.

The Daily Sprint is not the end of the learning loop. After a persisted sprint or activity result, OpenSAT can call `get_on_demand_recommendations` and return a small, optional set of targeted sessions. The recommendation target comes from the learner's current evidence and mistake autopsies; the score band mainly controls the amount of scaffolding and the difficulty of the material.

The current follow-up policy is:

- Incorrect or omitted: mistake autopsy, a worked example, targeted practice, and a transfer check.
- Correct but slow: timed-precision and retrieval work.
- Correct but uncertain or changed: confidence calibration, contrastive practice, and transfer.
- Due review with no new miss: delayed retrieval and transfer.

High aggregate accuracy does not suppress a recommendation when the learner is slow, uncertain, changing answers, requesting help, or carrying due review. A clean recent run of fast, confident, stable correct answers can correctly produce no issue-specific session. Older diagnostic evidence is not reopened as a current defect without newer supporting evidence.

This supports a learning design built around retrieval practice, worked examples, gradual fading of support, interleaving, transfer checks, metacognitive confidence reporting, and provisional diagnosis. See [`docs/learner-model.md`](docs/learner-model.md), [`docs/diagnostic-taxonomy.md`](docs/diagnostic-taxonomy.md), and [`docs/learning-engine.md`](docs/learning-engine.md) for the underlying model and decision boundaries.

## Runtime data

Personal learner data is stored outside this repository:

- macOS: `~/Library/Application Support/OpenSAT/`
- Windows: `%LOCALAPPDATA%\\OpenSAT\\`
- Linux: `$XDG_DATA_HOME/opensat/` or `~/.local/share/opensat/`

Set `OPENSAT_DATA_DIR` when you need a deterministic local test/demo directory. The former `SAT_PRECISION_LAB_DATA_DIR` name remains accepted for local compatibility. Runtime databases, exports, temporary files, backups, logs, browser captures, credentials, and API keys are ignored and must not be committed.

This GitHub repository is the installable plugin source. It intentionally does not contain the personal SAT workspace, learner profile, browser captures, or runtime database. Those remain local to the learner's machine.

## Run the vertical slice

From the plugin root:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_*.py' -v
PYTHONPATH=src python3 scripts/opensat.py capabilities
PYTHONPATH=src python3 scripts/opensat.py --data-dir /tmp/opensat-demo demo
```

The demo creates a learner, records a manually entered official assessment summary, records a synthetic missed-question event, represents a short autopsy, creates a provisional signature, builds a 20-minute session, records one activity, and exports the learner model outside the repository. Delete the demo data only when you have identified the exact temporary directory.

## Run the local MCP companion

The plugin manifest wires Codex to:

```text
python3 ./scripts/mcp_server.py
```

The server speaks JSON-RPC over stdio and exposes the contracts in `schemas/mcp-tool-contracts.json`. To smoke-test the server without installing the plugin:

```bash
printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' | PYTHONPATH=src python3 scripts/mcp_server.py
```

## Install locally in Codex

The current personal marketplace points `opensat@personal` at `/Users/vold/plugins/opensat`, which resolves to this source repository. After editing and validating the source, use the plugin-creator cachebuster helper and reinstall:

```bash
python3 /Users/vold/.codex/skills/.system/plugin-creator/scripts/update_plugin_cachebuster.py /Users/vold/plugins/opensat
codex plugin add opensat@personal
```

Check `codex plugin list` and the installed cache against the source. Do not hand-edit the marketplace JSON. Start a new chat after installation so the client reloads skills and MCP tools. Cross-surface availability must be verified in the target client.

## Current boundaries

Practice Scan has a host-neutral, user-authorized, read-only Chrome adapter with preview, resumable cursors, prompt-injection stop conditions, explicit commit, and transient-content deletion. A host-specific Chrome bridge still must provide normalized snapshots; OpenSAT does not log in, submit forms, navigate accounts, or run a credential-based scraper. No live Gemini request, public account, hosted database, GUI, payment, analytics, or official-score prediction is implemented. Page content must be treated as untrusted data, and live SAT administration is out of scope.

## Further reading

- [`docs/product-spec.md`](docs/product-spec.md)
- [`docs/architecture.md`](docs/architecture.md)
- [`docs/practice-scan.md`](docs/practice-scan.md)
- [`docs/privacy-and-content-boundaries.md`](docs/privacy-and-content-boundaries.md)
- [`docs/pilot-and-evaluation-plan.md`](docs/pilot-and-evaluation-plan.md)
- [`docs/self-improvement.md`](docs/self-improvement.md)
- [`docs/visual-practice-surface.md`](docs/visual-practice-surface.md)
- [`docs/reading-writing-item-style.md`](docs/reading-writing-item-style.md)
- [`docs/public-question-patterns-2026.md`](docs/public-question-patterns-2026.md)
