# Decision log

## 2026-08-23 — Plugin container with focused skills

Use one installable plugin containing six task-specific skills and one local MCP companion. OpenAI’s current plugin guidance describes plugins as containers that can package skills and optional apps; skills remain the reusable workflow unit. This keeps discovery specific and avoids one giant SAT prompt.

Source checked: [Plugins in ChatGPT and Codex](https://help.openai.com/en/articles/20001256-plugins-in-codex/) and [Skills in ChatGPT](https://help.openai.com/en/articles/20001066).

## 2026-08-23 — Local MCP, no app integration yet

Use a local stdio MCP server for structured persistence and future browser/provider boundaries. Do not create a live app integration in this phase because the browser workflow must be user-authorized, read-only, and domain-scoped. The current package manifest follows the local plugin-creator contract and is validated locally.

## 2026-08-23 — Python standard library and SQLite

Choose Python and SQLite for a dependency-light vertical slice, explicit migrations, local file permissions, deterministic tests, and portability. A future hosted or multi-user architecture would require a separate security and privacy review.

## 2026-08-23 — No marketplace mutation or installation

The brief asked for a scaffold, not installation into the user’s personal marketplace. The repository is locally installable but the personal marketplace and Codex installation were left unchanged.

## 2026-08-23 — Browser scan specified, not claimed

Practice Scan is a first-class design with incremental/idempotent/resumable import records, preview-before-persist, manual fallback, and prompt-injection boundaries. No browser automation, sign-in, page inspection, or College Board content capture was implemented or validated.

## 2026-08-23 — Gemini module adapter only

Gemini is represented as a module-level provider stub. Targeted generated items stay inside the local engine because a complete module provider cannot safely replace individual-item selection.

## 2026-08-28 — Visualize fallback with assistant-mediated submission

When a native OpenSAT practice interface is unavailable, Daily Sprint must use Visualize as the temporary interaction surface. Each section has an explicit submit control, and the surface sends a content-free payload to the current Codex task; the OpenSAT MCP service remains the source of truth for response evidence, timing, confidence, strategy observations, and reflection. A future native interface replaces Visualize rather than running alongside it.
