-- Modül 1 şema referansı (SQLAlchemy create_all ile otomatik oluşur)

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    display_name VARCHAR(120),
    preferred_language VARCHAR(10) NOT NULL DEFAULT 'tr',
    is_active BOOLEAN NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS api_keys (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    provider VARCHAR(11) NOT NULL,  -- openrouter | elevenlabs | video
    key_encrypted TEXT NOT NULL,
    key_hint VARCHAR(8) NOT NULL DEFAULT '',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (user_id, provider)
);

CREATE TABLE IF NOT EXISTS credit_balances (
    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    balance INTEGER NOT NULL DEFAULT 0,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS credit_transactions (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    amount INTEGER NOT NULL,  -- + yükleme, - harcama
    reason VARCHAR(255) NOT NULL,
    reference_type VARCHAR(50),
    reference_id VARCHAR(100),
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_users_email ON users(email);
CREATE INDEX IF NOT EXISTS ix_api_keys_user_id ON api_keys(user_id);
CREATE INDEX IF NOT EXISTS ix_credit_transactions_user_id ON credit_transactions(user_id);

-- Modül 2
CREATE TABLE IF NOT EXISTS scenarios (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    language VARCHAR(10) NOT NULL DEFAULT 'tr',
    title VARCHAR(200),
    duration_seconds INTEGER NOT NULL DEFAULT 30,
    style VARCHAR(80) NOT NULL DEFAULT 'profesyonel',
    audience VARCHAR(200),
    raw_input TEXT NOT NULL,
    professional_script TEXT NOT NULL DEFAULT '',
    status VARCHAR(30) NOT NULL DEFAULT 'draft',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_scenarios_user_id ON scenarios(user_id);

-- Modül 3 / 4
CREATE TABLE IF NOT EXISTS video_jobs (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    scenario_id INTEGER NOT NULL REFERENCES scenarios(id) ON DELETE CASCADE,
    status VARCHAR(30) NOT NULL DEFAULT 'pending',
    script_snapshot TEXT NOT NULL DEFAULT '',
    audio_path VARCHAR(500),
    video_path VARCHAR(500),
    preview_path VARCHAR(500),
    error_message TEXT,
    is_mock BOOLEAN NOT NULL DEFAULT 0,
    revision INTEGER NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS job_revisions (
    id INTEGER PRIMARY KEY,
    job_id INTEGER NOT NULL REFERENCES video_jobs(id) ON DELETE CASCADE,
    revision INTEGER NOT NULL,
    instruction TEXT NOT NULL,
    changed_fields TEXT NOT NULL DEFAULT '[]',
    script_before TEXT NOT NULL DEFAULT '',
    script_after TEXT NOT NULL DEFAULT '',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_video_jobs_user_id ON video_jobs(user_id);
CREATE INDEX IF NOT EXISTS ix_video_jobs_scenario_id ON video_jobs(scenario_id);
CREATE INDEX IF NOT EXISTS ix_job_revisions_job_id ON job_revisions(job_id);
