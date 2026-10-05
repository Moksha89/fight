-- ============================================================================
-- SCHEMA MIGRATIONS TABLE
-- ============================================================================
-- Purpose: Track applied database schema migrations for version control
-- ============================================================================

CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    description TEXT NOT NULL,
    applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Record initial schema as version 1
INSERT INTO schema_migrations (version, description) VALUES
    ('1', 'Initial schema with core tables')
ON CONFLICT (version) DO NOTHING;
