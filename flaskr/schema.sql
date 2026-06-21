CREATE TABLE IF NOT EXISTS throw_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    number TEXT NOT NULL,
    success_count INTEGER NOT NULL CHECK (success_count BETWEEN 0 AND 3),
    mode TEXT NOT NULL CHECK (mode IN ('normal', 'advanced', 'cricket')),
    bed TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_throw_results_user_id
ON throw_results (user_id);
