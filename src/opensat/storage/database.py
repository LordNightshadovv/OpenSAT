"""SQLite initialization with backup-before-migration semantics."""

from __future__ import annotations

import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from ..privacy.paths import DataPaths, ensure_data_layout


LATEST_SCHEMA_VERSION = 1


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS learners (
    learner_id TEXT PRIMARY KEY,
    preferred_language TEXT NOT NULL,
    explanation_mode TEXT NOT NULL,
    score_context_json TEXT NOT NULL,
    score_band_prior TEXT NOT NULL,
    test_date TEXT,
    accessibility_preferences_json TEXT NOT NULL,
    session_length_preference INTEGER NOT NULL DEFAULT 20,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS assessments (
    assessment_id TEXT PRIMARY KEY,
    learner_id TEXT NOT NULL REFERENCES learners(learner_id) ON DELETE CASCADE,
    source TEXT NOT NULL,
    assessment_type TEXT NOT NULL,
    external_id TEXT NOT NULL,
    taken_at TEXT,
    is_official INTEGER NOT NULL,
    total_score INTEGER,
    reading_writing_score INTEGER,
    math_score INTEGER,
    domain_evidence_json TEXT NOT NULL,
    import_provenance_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(learner_id, source, external_id)
);

CREATE TABLE IF NOT EXISTS question_events (
    event_id TEXT PRIMARY KEY,
    learner_id TEXT NOT NULL REFERENCES learners(learner_id) ON DELETE CASCADE,
    assessment_id TEXT REFERENCES assessments(assessment_id) ON DELETE CASCADE,
    event_key TEXT NOT NULL,
    section TEXT NOT NULL,
    module TEXT,
    question_locator TEXT NOT NULL,
    result TEXT NOT NULL,
    time_seconds REAL,
    time_source TEXT,
    confidence INTEGER,
    flagged INTEGER NOT NULL DEFAULT 0,
    answer_changed INTEGER NOT NULL DEFAULT 0,
    selected_answer TEXT,
    correct_answer TEXT,
    provisional_skill TEXT,
    provenance_type TEXT NOT NULL,
    content_fingerprint TEXT,
    abstract_context_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(learner_id, assessment_id, event_key)
);

CREATE TABLE IF NOT EXISTS reasoning_responses (
    response_id TEXT PRIMARY KEY,
    learner_id TEXT NOT NULL REFERENCES learners(learner_id) ON DELETE CASCADE,
    event_id TEXT NOT NULL REFERENCES question_events(event_id) ON DELETE CASCADE,
    prompt_id TEXT NOT NULL,
    response_text TEXT NOT NULL,
    confidence INTEGER,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS diagnostic_hypotheses (
    hypothesis_id TEXT PRIMARY KEY,
    learner_id TEXT NOT NULL REFERENCES learners(learner_id) ON DELETE CASCADE,
    event_id TEXT REFERENCES question_events(event_id) ON DELETE SET NULL,
    observed_fact TEXT NOT NULL,
    hypothesis TEXT NOT NULL,
    confidence REAL NOT NULL,
    status TEXT NOT NULL,
    supporting_event_ids_json TEXT NOT NULL,
    contradicting_evidence_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS error_signatures (
    signature_id TEXT PRIMARY KEY,
    learner_id TEXT NOT NULL REFERENCES learners(learner_id) ON DELETE CASCADE,
    code TEXT NOT NULL,
    status TEXT NOT NULL,
    evidence_event_ids_json TEXT NOT NULL,
    recurrence_count INTEGER NOT NULL DEFAULT 1,
    last_seen TEXT NOT NULL,
    notes TEXT,
    updated_at TEXT NOT NULL,
    UNIQUE(learner_id, code)
);

CREATE TABLE IF NOT EXISTS skill_states (
    skill_state_id TEXT PRIMARY KEY,
    learner_id TEXT NOT NULL REFERENCES learners(learner_id) ON DELETE CASCADE,
    skill TEXT NOT NULL,
    stage TEXT NOT NULL,
    evidence_json TEXT NOT NULL,
    recurrence_risk REAL NOT NULL DEFAULT 0.5,
    updated_at TEXT NOT NULL,
    UNIQUE(learner_id, skill)
);

CREATE TABLE IF NOT EXISTS review_queue (
    review_id TEXT PRIMARY KEY,
    learner_id TEXT NOT NULL REFERENCES learners(learner_id) ON DELETE CASCADE,
    event_id TEXT REFERENCES question_events(event_id) ON DELETE SET NULL,
    skill TEXT,
    reason TEXT NOT NULL,
    due_at TEXT NOT NULL,
    recurrence_risk REAL NOT NULL,
    evidence_strength REAL NOT NULL,
    transfer_distance TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS strategy_trials (
    trial_id TEXT PRIMARY KEY,
    learner_id TEXT NOT NULL REFERENCES learners(learner_id) ON DELETE CASCADE,
    strategy TEXT NOT NULL,
    question_type TEXT NOT NULL,
    condition_a_json TEXT NOT NULL,
    condition_b_json TEXT NOT NULL,
    results_json TEXT NOT NULL,
    sample_size INTEGER NOT NULL DEFAULT 0,
    provisional_conclusion TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS generated_items (
    item_id TEXT PRIMARY KEY,
    learner_id TEXT REFERENCES learners(learner_id) ON DELETE CASCADE,
    provider TEXT NOT NULL,
    target_skill TEXT NOT NULL,
    target_error_signature TEXT,
    intended_difficulty TEXT NOT NULL,
    validation_status TEXT NOT NULL,
    item_version TEXT NOT NULL,
    simulated_label TEXT NOT NULL,
    specification_json TEXT NOT NULL,
    exposure_history_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    learner_id TEXT NOT NULL REFERENCES learners(learner_id) ON DELETE CASCADE,
    planned_minutes INTEGER NOT NULL,
    actual_minutes INTEGER,
    band TEXT NOT NULL,
    activities_json TEXT NOT NULL,
    results_json TEXT NOT NULL,
    fatigue TEXT,
    completed INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS practice_imports (
    import_id TEXT PRIMARY KEY,
    learner_id TEXT NOT NULL REFERENCES learners(learner_id) ON DELETE CASCADE,
    source TEXT NOT NULL,
    external_id TEXT NOT NULL,
    cursor TEXT,
    status TEXT NOT NULL,
    preview_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(learner_id, source, external_id)
);
"""


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _backup_before_migration(paths: DataPaths, current_version: int) -> None:
    if not paths.database.exists() or current_version >= LATEST_SCHEMA_VERSION:
        return
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = paths.backups / f"opensat_pre_migration_v{current_version}_{stamp}.sqlite3"
    shutil.copy2(paths.database, target)


def connect(data_dir: Path | None = None) -> tuple[sqlite3.Connection, DataPaths]:
    paths = ensure_data_layout(data_dir)
    connection = sqlite3.connect(paths.database)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    current_version = int(connection.execute("PRAGMA user_version").fetchone()[0])
    _backup_before_migration(paths, current_version)
    if current_version < 1:
        connection.executescript(SCHEMA_SQL)
        connection.execute("PRAGMA user_version = 1")
    connection.commit()
    try:
        paths.database.chmod(0o600)
    except OSError:
        pass
    return connection, paths
