-- Migration: 008_conversations
-- The AI conversations, kept (no automatic deletion; a retention policy comes later). A
-- conversation belongs to one user and one site and holds the raw Messages-API history the agent
-- loop continues from (append-only, thinking blocks included). Each question and its answer is
-- one turn: what the AI read (tool calls with their arguments, never the values), the tokens it
-- used, and the user's feedback. A user who asked is disabled, not deleted, so their
-- conversations stay (no ON DELETE CASCADE from users).

CREATE TABLE ai_conversations (
    conversation_id TEXT PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users (id),
    site_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    messages JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX ai_conversations_user_idx ON ai_conversations (user_id, site_id, updated_at DESC);

CREATE TABLE ai_turns (
    turn_id BIGSERIAL PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES ai_conversations (conversation_id) ON DELETE CASCADE,
    -- 0 for the conversation's first question.
    position INTEGER NOT NULL,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    model TEXT,
    stop_reason TEXT NOT NULL,
    iterations INTEGER NOT NULL,
    -- [{name, args, summary, duration_ms, is_error}]: what the AI read, not the values.
    tool_calls JSONB NOT NULL,
    input_tokens INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    cache_read_input_tokens INTEGER NOT NULL,
    cache_creation_input_tokens INTEGER NOT NULL,
    duration_ms DOUBLE PRECISION NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    -- The site's local time when asked (ISO 8601 with its offset), as the AI was told.
    site_local_time TEXT NOT NULL,
    feedback TEXT CHECK (feedback IN ('up', 'down')),
    feedback_comment TEXT,
    feedback_at TIMESTAMPTZ,
    UNIQUE (conversation_id, position)
);
