-- init_db.sql — AutoMark AI CRM Agent (ORCAST)
-- PostgreSQL + pgvector schema: conversation memory, leads, escalations, RAG chunks.

CREATE EXTENSION IF NOT EXISTS vector;

-- ─────────────────────────────────────────────────────────────────────────────
-- conversations — rolling-summary conversation memory, one row per user
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS conversations (
    user_id               TEXT        PRIMARY KEY,
    source                TEXT        NOT NULL DEFAULT 'unknown',
    status                TEXT        NOT NULL DEFAULT 'active',
    summary               TEXT,
    messages              JSONB       NOT NULL DEFAULT '[]',
    message_count         INTEGER     NOT NULL DEFAULT 0,
    summarization_cycles  INTEGER     NOT NULL DEFAULT 0,
    summary_updated_at    TIMESTAMPTZ,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─────────────────────────────────────────────────────────────────────────────
-- leads — progressively-collected lead qualification data
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS leads (
    user_id            TEXT        PRIMARY KEY
                       REFERENCES conversations(user_id) ON DELETE CASCADE,
    name               TEXT,
    email              TEXT,
    phone              TEXT,
    budget             TEXT,
    authority          TEXT,
    engagement_level   INTEGER,
    interest_level     INTEGER,
    pain_points        JSONB       NOT NULL DEFAULT '[]',
    lead_score         INTEGER,
    lead_temperature   TEXT,
    hubspot_contact_id TEXT,
    hubspot_deal_id    TEXT,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─────────────────────────────────────────────────────────────────────────────
-- escalations — human-handoff records
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS escalations (
    id              BIGSERIAL   PRIMARY KEY,
    user_id         TEXT        NOT NULL
                    REFERENCES conversations(user_id) ON DELETE CASCADE,
    reason          TEXT        NOT NULL,
    priority        TEXT        NOT NULL DEFAULT 'medium',
    status          TEXT        NOT NULL DEFAULT 'open',
    hubspot_note_id TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_escalations_user_id ON escalations(user_id);

-- ─────────────────────────────────────────────────────────────────────────────
-- document_chunks — hybrid RAG store (dense pgvector + sparse full-text)
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS document_chunks (
    id          BIGSERIAL    PRIMARY KEY,
    doc_id      TEXT         NOT NULL,
    source_file TEXT         NOT NULL,
    chunk_index INTEGER      NOT NULL,
    content     TEXT         NOT NULL,
    token_count INTEGER      NOT NULL DEFAULT 0,
    embedding   VECTOR(768),
    ts_content  TSVECTOR     GENERATED ALWAYS AS (to_tsvector('english', content)) STORED,
    metadata    JSONB        NOT NULL DEFAULT '{}',
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    UNIQUE (doc_id, chunk_index)
);

-- Dense vector search (HNSW, cosine distance)
CREATE INDEX IF NOT EXISTS idx_document_chunks_embedding
    ON document_chunks
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- Sparse full-text search
CREATE INDEX IF NOT EXISTS idx_document_chunks_ts_content
    ON document_chunks
    USING gin (ts_content);
