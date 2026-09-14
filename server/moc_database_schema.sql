-- ============================================================================
-- MATCH OPERATIONS CENTER (MOC) - Database Schema
-- ============================================================================
-- Purpose: Dedicated operator dashboard for match control & external API feed
-- Created: 2026-09-14
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. MOC OPERATORS TABLE
-- Dedicated operator accounts (separate from admin/players)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS moc_operators (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    password_salt TEXT NOT NULL,
    password_iterations INTEGER NOT NULL DEFAULT 600000,
    display_name TEXT NOT NULL,
    email TEXT,
    role TEXT NOT NULL DEFAULT 'operator',
        -- 'super_admin': Full system access, manage operators
        -- 'operator': Create matches, control lifecycle, declare results
        -- 'monitor': Read-only access, no control permissions
        -- 'technician': Stream management only
    active INTEGER DEFAULT 1,
    mfa_secret TEXT,
    mfa_enabled INTEGER DEFAULT 0,
    last_login_at TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_moc_operators_username ON moc_operators(username);
CREATE INDEX IF NOT EXISTS idx_moc_operators_active ON moc_operators(active);

-- ----------------------------------------------------------------------------
-- 2. MOC MATCHES TABLE
-- Manual matches controlled by operators
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS moc_matches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id TEXT UNIQUE NOT NULL,
        -- Format: 'MOC-42', 'MOC-43', etc.
    fight_number INTEGER NOT NULL,
    arena TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    
    -- Lifecycle status
    status TEXT NOT NULL DEFAULT 'DRAFT',
        -- 'DRAFT': Created but not published
        -- 'SCHEDULED': Published, visible to players
        -- 'BETTING_OPEN': Accepting bets
        -- 'BETTING_CLOSED': Bets closed, fight in progress
        -- 'LIVE': Fight in progress (after betting closed)
        -- 'AWAITING_RESULT': Fight finished, result pending
        -- 'COMPLETED': Result declared and settled
        -- 'CANCELLED': Match cancelled, bets refunded
    
    -- Timing
    betting_opens_at TEXT,
    betting_closes_at TEXT,
    scheduled_at TEXT,
    started_at TEXT,
    completed_at TEXT,
    
    -- Outcomes and odds
    red_name TEXT DEFAULT 'Meron',
    red_odds REAL DEFAULT 1.85,
    blue_name TEXT DEFAULT 'Wala',
    blue_odds REAL DEFAULT 1.85,
    draw_odds REAL DEFAULT 6.00,
    
    -- Result
    result TEXT,
        -- 'red': Red corner wins
        -- 'blue': Blue corner wins
        -- 'draw': Draw
        -- 'cancelled': Match cancelled
    result_declared_at TEXT,
    result_declared_by INTEGER,
        -- operator_id who declared result
    settled_at TEXT,
    
    -- Stream details
    stream_type TEXT DEFAULT 'HLS',
        -- 'HLS', 'YOUTUBE', 'VIDEO', 'WHEP', 'OFFLINE'
    stream_url TEXT,
    stream_health TEXT DEFAULT 'UNKNOWN',
        -- 'LIVE', 'OFFLINE', 'ERROR', 'UNKNOWN'
    
    -- Statistics (updated in real-time)
    total_bets INTEGER DEFAULT 0,
    total_stakes REAL DEFAULT 0.0,
    red_bets INTEGER DEFAULT 0,
    red_stakes REAL DEFAULT 0.0,
    blue_bets INTEGER DEFAULT 0,
    blue_stakes REAL DEFAULT 0.0,
    draw_bets INTEGER DEFAULT 0,
    draw_stakes REAL DEFAULT 0.0,
    total_payout REAL DEFAULT 0.0,
    
    -- Metadata
    visible INTEGER DEFAULT 1,
    featured INTEGER DEFAULT 0,
    created_by INTEGER NOT NULL,
        -- operator_id who created match
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (created_by) REFERENCES moc_operators(id),
    FOREIGN KEY (result_declared_by) REFERENCES moc_operators(id)
);

CREATE INDEX IF NOT EXISTS idx_moc_matches_match_id ON moc_matches(match_id);
CREATE INDEX IF NOT EXISTS idx_moc_matches_status ON moc_matches(status);
CREATE INDEX IF NOT EXISTS idx_moc_matches_fight_number ON moc_matches(fight_number);
CREATE INDEX IF NOT EXISTS idx_moc_matches_scheduled_at ON moc_matches(scheduled_at);
CREATE INDEX IF NOT EXISTS idx_moc_matches_created_by ON moc_matches(created_by);

-- ----------------------------------------------------------------------------
-- 3. MOC AUDIT LOG
-- Complete audit trail of all operator actions
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS moc_audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    operator_id INTEGER NOT NULL,
    operator_username TEXT NOT NULL,
    match_id TEXT,
    action TEXT NOT NULL,
        -- 'LOGIN', 'LOGOUT'
        -- 'CREATE_MATCH', 'UPDATE_MATCH', 'DELETE_MATCH'
        -- 'OPEN_BETTING', 'CLOSE_BETTING'
        -- 'DECLARE_RESULT', 'SETTLE_MATCH'
        -- 'CANCEL_MATCH'
        -- 'UPDATE_STREAM', 'TEST_STREAM'
        -- 'CREATE_OPERATOR', 'UPDATE_OPERATOR', 'DELETE_OPERATOR'
        -- 'CREATE_API_KEY', 'REVOKE_API_KEY'
    details TEXT,
        -- JSON with action-specific details
    ip_address TEXT,
    user_agent TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (operator_id) REFERENCES moc_operators(id)
);

CREATE INDEX IF NOT EXISTS idx_moc_audit_log_operator_id ON moc_audit_log(operator_id);
CREATE INDEX IF NOT EXISTS idx_moc_audit_log_match_id ON moc_audit_log(match_id);
CREATE INDEX IF NOT EXISTS idx_moc_audit_log_action ON moc_audit_log(action);
CREATE INDEX IF NOT EXISTS idx_moc_audit_log_created_at ON moc_audit_log(created_at);

-- ----------------------------------------------------------------------------
-- 4. MOC API KEYS
-- API keys for external platforms to consume MOC feed
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS moc_api_keys (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key_id TEXT UNIQUE NOT NULL,
        -- Format: 'moc_key_<random>'
    api_key TEXT UNIQUE NOT NULL,
        -- Full API key: 'moc_sk_<64-char-hex>'
    key_hash TEXT NOT NULL,
        -- SHA256 hash of api_key for validation
    
    -- Owner details
    platform_name TEXT NOT NULL,
        -- e.g., 'Partner Casino App', 'Affiliate Platform'
    platform_url TEXT,
    contact_email TEXT,
    
    -- Permissions
    permissions TEXT DEFAULT 'read',
        -- JSON array: ['read', 'write', 'admin']
        -- 'read': Access feed API only
        -- 'write': Create matches via API (future)
        -- 'admin': Full API access (internal only)
    
    -- Rate limiting
    rate_limit INTEGER DEFAULT 100,
        -- Requests per minute
    rate_window_seconds INTEGER DEFAULT 60,
    
    -- Access control
    allowed_ips TEXT,
        -- JSON array of allowed IP addresses
    allowed_origins TEXT,
        -- JSON array of allowed CORS origins
    
    -- Status
    active INTEGER DEFAULT 1,
    expires_at TEXT,
        -- NULL = no expiration
    last_used_at TEXT,
    usage_count INTEGER DEFAULT 0,
    
    -- Metadata
    created_by INTEGER NOT NULL,
        -- operator_id who created this key
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    revoked_at TEXT,
    revoked_by INTEGER,
    revoked_reason TEXT,
    
    FOREIGN KEY (created_by) REFERENCES moc_operators(id),
    FOREIGN KEY (revoked_by) REFERENCES moc_operators(id)
);

CREATE INDEX IF NOT EXISTS idx_moc_api_keys_key_hash ON moc_api_keys(key_hash);
CREATE INDEX IF NOT EXISTS idx_moc_api_keys_active ON moc_api_keys(active);
CREATE INDEX IF NOT EXISTS idx_moc_api_keys_platform_name ON moc_api_keys(platform_name);

-- ----------------------------------------------------------------------------
-- 5. MOC API KEY USAGE LOG
-- Track API key usage for monitoring and billing
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS moc_api_key_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    api_key_id INTEGER NOT NULL,
    endpoint TEXT NOT NULL,
        -- e.g., '/api/moc-feed/current-match'
    method TEXT NOT NULL,
        -- 'GET', 'POST', etc.
    status_code INTEGER NOT NULL,
    response_time_ms INTEGER,
    ip_address TEXT,
    user_agent TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (api_key_id) REFERENCES moc_api_keys(id)
);

CREATE INDEX IF NOT EXISTS idx_moc_api_key_usage_api_key_id ON moc_api_key_usage(api_key_id);
CREATE INDEX IF NOT EXISTS idx_moc_api_key_usage_created_at ON moc_api_key_usage(created_at);
CREATE INDEX IF NOT EXISTS idx_moc_api_key_usage_endpoint ON moc_api_key_usage(endpoint);

-- ----------------------------------------------------------------------------
-- 6. MOC SETTINGS
-- System-wide MOC configuration
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS moc_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    description TEXT,
    updated_by INTEGER,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (updated_by) REFERENCES moc_operators(id)
);

-- Default settings
INSERT OR IGNORE INTO moc_settings (key, value, description) VALUES
    ('enabled', 'false', 'Enable/disable MOC system'),
    ('auto_increment_fight_number', 'true', 'Auto-increment fight numbers'),
    ('next_fight_number', '1', 'Next fight number to use'),
    ('default_red_odds', '1.85', 'Default odds for red corner'),
    ('default_blue_odds', '1.85', 'Default odds for blue corner'),
    ('default_draw_odds', '6.00', 'Default odds for draw'),
    ('require_password_for_result', 'true', 'Require operator password when declaring results'),
    ('two_operator_approval_threshold', '100000', 'Amount threshold requiring two-operator approval'),
    ('feed_poll_interval_seconds', '3', 'How often main platform polls MOC feed'),
    ('max_concurrent_matches', '5', 'Maximum concurrent live matches'),
    ('audit_log_retention_days', '365', 'Days to retain audit logs'),
    ('api_rate_limit_default', '100', 'Default API rate limit per minute'),
    ('moc_category_slug', 'moc-feed', 'Category slug for MOC matches in main platform');

-- ============================================================================
-- INITIAL DATA - Create default super admin operator
-- ============================================================================
-- Default credentials:
-- Username: moc_admin
-- Password: MOCAdmin@2026
-- IMPORTANT: Change this password immediately after first login!

-- Generate password hash for MOCAdmin@2026
-- Using PBKDF2-HMAC-SHA256 with 600,000 iterations
INSERT OR IGNORE INTO moc_operators (
    id,
    username,
    password_hash,
    password_salt,
    password_iterations,
    display_name,
    email,
    role,
    active
) VALUES (
    1,
    'moc_admin',
    '5020b6fe4c2620ec4e41d1fdc3214286b55d026232844c58af126d4e62e0bfc2',
    'b24abd90e97961437258170075fa4a936389578c0a06572c76ec85ae78b7bd5d',
    600000,
    'MOC Super Admin',
    'admin@roosterrun.local',
    'super_admin',
    1
);

-- ============================================================================
-- END OF SCHEMA
-- ============================================================================
