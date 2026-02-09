-- Learning Assistant DDL
-- Run: psql -U postgres -d learning_assistant -f db/init.sql

CREATE TABLE IF NOT EXISTS sessions (
    session_id  SERIAL PRIMARY KEY,
    started_at  TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS messages (
    id          SERIAL PRIMARY KEY,
    session_id  INTEGER NOT NULL REFERENCES sessions(session_id),
    role        VARCHAR(20) NOT NULL,  -- 'user' | 'assistant' | 'system'
    content     TEXT NOT NULL,
    created_at  TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS topics (
    topic_id    SERIAL PRIMARY KEY,
    name        VARCHAR(255) NOT NULL UNIQUE,
    tags        TEXT[]  -- e.g. {'python', 'advanced'}
);

CREATE TABLE IF NOT EXISTS study_plan (
    plan_id     SERIAL PRIMARY KEY,
    title       VARCHAR(255) NOT NULL,
    created_at  TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS plan_items (
    item_id     SERIAL PRIMARY KEY,
    plan_id     INTEGER NOT NULL REFERENCES study_plan(plan_id),
    topic_id    INTEGER REFERENCES topics(topic_id),
    title       VARCHAR(255) NOT NULL,
    status      VARCHAR(20) NOT NULL DEFAULT 'pending',  -- 'pending' | 'in_progress' | 'done'
    due_date    DATE,
    notes       TEXT
);

CREATE TABLE IF NOT EXISTS quiz_attempts (
    attempt_id  SERIAL PRIMARY KEY,
    topic_id    INTEGER REFERENCES topics(topic_id),
    question    TEXT NOT NULL,
    user_answer TEXT,
    score       REAL,        -- 0.0 to 1.0
    feedback    TEXT,
    created_at  TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS flashcards (
    card_id         SERIAL PRIMARY KEY,
    topic_id        INTEGER REFERENCES topics(topic_id),
    front           TEXT NOT NULL,
    back            TEXT NOT NULL,
    last_seen       TIMESTAMP,
    ease_factor     REAL NOT NULL DEFAULT 2.5,
    next_review_at  TIMESTAMP
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);
CREATE INDEX IF NOT EXISTS idx_plan_items_plan   ON plan_items(plan_id);
CREATE INDEX IF NOT EXISTS idx_quiz_topic        ON quiz_attempts(topic_id);
CREATE INDEX IF NOT EXISTS idx_flashcards_review ON flashcards(next_review_at);
