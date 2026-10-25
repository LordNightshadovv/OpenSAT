-- Add the learner's post-answer, pre-feedback apparent-difficulty tag.
-- The runtime backs up the database before applying this migration.
ALTER TABLE question_events ADD COLUMN apparent_difficulty TEXT;
PRAGMA user_version = 2;
