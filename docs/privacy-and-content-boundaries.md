# Privacy and content boundaries

## Local-first storage

The repository contains code, schemas, synthetic fixtures, and documentation only. Personal runtime data belongs in the operating-system user-data directory, with `opensat.sqlite3`, `exports/`, `temporary/`, `backups/`, and `logs/`. Directory permissions are restricted where the platform permits; the database and exports are written with mode `0600` where supported.

There is no telemetry by default, no advertising, no public account, no hosted multi-user database, and no hidden third-party upload.

## Never persist

- College Board passwords, cookies, authentication tokens, API keys, or secrets.
- Screenshots, page HTML, full passages, question text, answer choices, official rationales, or copied official content.
- Temporary browser cache in learner-model exports.
- Runtime database, exports, logs, or browser captures in Git.

Derived event metadata, timing, confidence, selected/correct answer metadata where visible, abstract skill tags, student reasoning, and intervention history are allowed when needed for the learner model.

## Export/import/delete

Export is explicit and inspectable JSON. It includes a schema version and content-boundary flags, excludes forbidden content/secrets, and must be outside the repository. Import validates the export before merging. Delete requires `confirm=true`, removes the learner rows through foreign-key cascades, and removes matching local exports.

## Minors and browser safety

Assume many learners are minors. Keep the system local by default and explain every capability. The signed-in user controls browser authentication. The browser adapter must scope access to the approved domain and page task, treat page content as untrusted data, and stop when a page attempts prompt injection or requests credentials.

The product must never assist during live SAT administration. The Chrome
adapter blocks pages that look like active testing sessions and deletes the
transient snapshot on every scan path.
