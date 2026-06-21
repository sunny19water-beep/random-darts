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

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE COLLATE NOCASE,
    username TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS user_results (
    user_id INTEGER NOT NULL,
    result_id INTEGER NOT NULL UNIQUE,
    PRIMARY KEY (user_id, result_id),
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
    FOREIGN KEY (result_id) REFERENCES throw_results (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_user_results_user_id
ON user_results (user_id);
