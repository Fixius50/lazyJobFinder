-- schema.sql
-- Esquema unificado y canónico de base de datos para lazyJobFinder (SQLite 3.35+)
-- Integra deduplicación difusa (RapidFuzz), trazabilidad documental y canales independientes (UI y Telegram).

CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url_hash TEXT UNIQUE NOT NULL,
    content_fingerprint TEXT NOT NULL,
    description_hash TEXT,
    canonical_url TEXT NOT NULL,
    title TEXT NOT NULL,
    company TEXT NOT NULL,
    location TEXT,
    is_remote INTEGER DEFAULT 0,
    source TEXT NOT NULL,
    description TEXT,
    salary_min REAL,
    salary_max REAL,
    salary_currency TEXT,
    date_posted TEXT,
    created_at TEXT DEFAULT (datetime('now', 'localtime')),
    updated_at TEXT DEFAULT (datetime('now', 'localtime')),
    status TEXT DEFAULT 'discovered',
    duplicate_of_id INTEGER REFERENCES jobs(id) ON DELETE SET NULL,
    similarity_score REAL,
    alternate_sources TEXT DEFAULT '[]',
    telegram_notified INTEGER DEFAULT 0,
    ui_saved INTEGER DEFAULT 1,
    contract_type TEXT,
    schedule TEXT,
    education_level TEXT
);

CREATE INDEX IF NOT EXISTS idx_jobs_url_hash ON jobs(url_hash);
CREATE INDEX IF NOT EXISTS idx_jobs_fingerprint ON jobs(content_fingerprint);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON jobs(created_at);
CREATE INDEX IF NOT EXISTS idx_jobs_duplicate_of ON jobs(duplicate_of_id);
CREATE INDEX IF NOT EXISTS idx_jobs_notification_channels ON jobs(telegram_notified, ui_saved);

CREATE TABLE IF NOT EXISTS evaluations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    score INTEGER NOT NULL,
    fit_level TEXT NOT NULL,
    matched_skills TEXT,
    missing_skills TEXT,
    strengths TEXT,
    gaps TEXT,
    reasoning TEXT NOT NULL,
    should_apply INTEGER NOT NULL,
    created_at TEXT DEFAULT (datetime('now', 'localtime')),
    UNIQUE(job_id)
);

CREATE INDEX IF NOT EXISTS idx_evaluations_score ON evaluations(score);

CREATE TABLE IF NOT EXISTS generated_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    cv_pdf_path TEXT,
    cv_md_path TEXT,
    letter_pdf_path TEXT,
    letter_md_path TEXT,
    diff_summary TEXT,
    created_at TEXT DEFAULT (datetime('now', 'localtime')),
    UNIQUE(job_id)
);

CREATE TABLE IF NOT EXISTS pipeline_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT DEFAULT (datetime('now', 'localtime')),
    finished_at TEXT,
    trigger_type TEXT NOT NULL, -- 'scheduled', 'manual', 'catch_up'
    status TEXT NOT NULL,       -- 'running', 'completed', 'failed', 'interrupted', 'skipped'
    total_found INTEGER DEFAULT 0,
    new_jobs INTEGER DEFAULT 0,
    relevant_jobs INTEGER DEFAULT 0,
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_pipeline_runs_started ON pipeline_runs(started_at);

CREATE TABLE IF NOT EXISTS system_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT DEFAULT (datetime('now', 'localtime')),
    level TEXT NOT NULL,        -- 'INFO', 'WARNING', 'ERROR', 'CRITICAL'
    source TEXT NOT NULL,       -- 'pipeline', 'evaluator', 'tailoring', 'telegram', 'docker', 'cv'
    message TEXT NOT NULL,
    details TEXT
);

CREATE INDEX IF NOT EXISTS idx_system_logs_timestamp ON system_logs(timestamp);
