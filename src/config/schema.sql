-- LiteLLM Control Plane Database Schema
-- SQLite Dialect

PRAGMA foreign_keys = ON;

-- Nodes Registry
CREATE TABLE IF NOT EXISTS nodes (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    host TEXT NOT NULL,
    port INTEGER NOT NULL,
    region TEXT NOT NULL,
    role TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active'
);

-- Providers Registry
CREATE TABLE IF NOT EXISTS providers (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    type TEXT NOT NULL
);

-- Models & Capabilities Registry
CREATE TABLE IF NOT EXISTS models (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    logical_group TEXT NOT NULL,
    capability_chat INTEGER NOT NULL DEFAULT 1,
    capability_stream INTEGER NOT NULL DEFAULT 1,
    capability_tools INTEGER NOT NULL DEFAULT 1,
    capability_embeddings INTEGER NOT NULL DEFAULT 0
);

-- Accounts Registry
CREATE TABLE IF NOT EXISTS accounts (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    provider_id TEXT NOT NULL,
    secret_ref TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    cooldown_until TEXT,
    failure_count INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (provider_id) REFERENCES providers(id) ON DELETE RESTRICT
);

-- Endpoints Registry (Logical routes binding Nodes, Accounts, and Models)
CREATE TABLE IF NOT EXISTS endpoints (
    id TEXT PRIMARY KEY,
    node_id TEXT NOT NULL,
    account_id TEXT NOT NULL,
    model_id TEXT NOT NULL,
    priority INTEGER NOT NULL DEFAULT 1,
    weight INTEGER NOT NULL DEFAULT 100,
    status TEXT NOT NULL DEFAULT 'active',
    manual_override TEXT NOT NULL DEFAULT 'none',
    cooldown_until TEXT,
    failure_count INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (node_id) REFERENCES nodes(id) ON DELETE CASCADE,
    FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE RESTRICT,
    FOREIGN KEY (model_id) REFERENCES models(id) ON DELETE RESTRICT
);

-- Indices for performance
CREATE INDEX IF NOT EXISTS idx_endpoints_node_id ON endpoints(node_id);
CREATE INDEX IF NOT EXISTS idx_endpoints_account_id ON endpoints(account_id);
CREATE INDEX IF NOT EXISTS idx_endpoints_model_id ON endpoints(model_id);
CREATE INDEX IF NOT EXISTS idx_accounts_provider_id ON accounts(provider_id);

-- Audit Logs Table
CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    changes TEXT NOT NULL, -- JSON string representing diff
    reason TEXT
);

-- Consumers Table
CREATE TABLE IF NOT EXISTS consumers (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    max_budget REAL,
    rate_limit_rpm INTEGER,
    rate_limit_tpm INTEGER,
    status TEXT NOT NULL DEFAULT 'active',
    profile_id TEXT,
    FOREIGN KEY (profile_id) REFERENCES policy_profiles(id) ON DELETE SET NULL
);


-- Consumer Keys (Virtual keys dynamically generated per consumer on each node)
CREATE TABLE IF NOT EXISTS consumer_keys (
    consumer_id TEXT NOT NULL,
    node_id TEXT NOT NULL,
    virtual_key TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    PRIMARY KEY (consumer_id, node_id),
    FOREIGN KEY (consumer_id) REFERENCES consumers(id) ON DELETE CASCADE,
    FOREIGN KEY (node_id) REFERENCES nodes(id) ON DELETE CASCADE
);

-- Indices for consumer tables
CREATE INDEX IF NOT EXISTS idx_consumer_keys_node_id ON consumer_keys(node_id);

-- Incidents and Health Transitions Table
CREATE TABLE IF NOT EXISTS incidents (
    id TEXT PRIMARY KEY,
    target_type TEXT NOT NULL, -- 'account' or 'endpoint'
    target_id TEXT NOT NULL,
    state_from TEXT NOT NULL,
    state_to TEXT NOT NULL,
    reason TEXT,
    raw_response TEXT,         -- JSON string of raw provider error payload, if available
    timestamp TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

-- Policy Profiles Table
CREATE TABLE IF NOT EXISTS policy_profiles (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    allowed_model_groups TEXT NOT NULL, -- JSON list of logical groups: e.g. ["premium", "general"]
    description TEXT
);

-- Rollouts Table
CREATE TABLE IF NOT EXISTS rollouts (
    id TEXT PRIMARY KEY,
    node_id TEXT NOT NULL,
    config_version TEXT NOT NULL,       -- SHA-256 hash of the generated config
    status TEXT NOT NULL,               -- 'pending', 'applying', 'success', 'failed', 'rolled_back'
    config_content TEXT NOT NULL,       -- Full YAML configuration content
    error_message TEXT,
    timestamp TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    FOREIGN KEY (node_id) REFERENCES nodes(id) ON DELETE CASCADE
);



