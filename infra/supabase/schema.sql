-- FinSight AI — Relational & Vector Schema Specification (Public Showcase)
-- Note: Production schema with strict multi-tenant Row-Level Security (RLS) policies,
-- pgvector indexing, and enterprise partition strategies is maintained in the private production repository.

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";

-- Workspaces & Document Index Tables (Reference Schema)
CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    business_id UUID NOT NULL,
    filename TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'indexed',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS document_chunks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index INT NOT NULL,
    content TEXT NOT NULL,
    embedding vector(1536),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
