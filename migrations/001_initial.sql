-- Reference migration for the local SQLite schema.
-- The runtime applies the same idempotent schema in storage/database.py.
PRAGMA foreign_keys = ON;
PRAGMA user_version = 1;

-- Tables are created by the Python migration so this file remains a reviewable
-- migration marker for future schema versions without duplicating SQL here.
