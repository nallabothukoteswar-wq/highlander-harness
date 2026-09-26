-- Co-located sink schema
-- Implements sink functions for conditions C1, C1u, C1v, C2, C2f, C3, C4

-- State table: tracks current version per target_key
CREATE TABLE IF NOT EXISTS sink.state (
    trial_id    text NOT NULL,
    target_key  text NOT NULL,
    version     bigint NOT NULL DEFAULT 0,
    PRIMARY KEY (trial_id, target_key)
);

-- Effects table: records accepted effects (for dup workload)
CREATE TABLE IF NOT EXISTS sink.effects (
    trial_id    text NOT NULL,
    effect_id   uuid NOT NULL DEFAULT gen_random_uuid(),
    business_key text NOT NULL,
    op_key      text NOT NULL,
    version     bigint NOT NULL,
    committed_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (trial_id, effect_id)
);

-- Unique constraint on op_key (for C1u, C3, C4 conditions)
-- This will be added dynamically per trial based on condition

-- Responses table (for C4 response caching)
CREATE TABLE IF NOT EXISTS sink.responses (
    trial_id    text NOT NULL,
    op_key      text NOT NULL,
    response    jsonb NOT NULL,
    committed_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (trial_id, op_key)
);

-- Attempt log: records every sink call attempt
CREATE TABLE IF NOT EXISTS sink.attempt_log (
    trial_id        text NOT NULL,
    condition       text NOT NULL,
    worker_id       text NOT NULL,
    incarnation     uuid NOT NULL,
    stream_id       text NOT NULL,
    epoch           bigint,
    op_key          text NOT NULL,
    business_key    text NOT NULL,
    target_key      text NOT NULL,
    source_version  bigint NOT NULL,
    prep_cpu_ns     bigint NOT NULL,
    at_risk         boolean NOT NULL DEFAULT false,
    outcome         text NOT NULL,  -- accepted, rejected, replayed
    reason          text,  -- not_holder, stale_epoch, expired, dup_key, version_not_newer
    pre_version     bigint,
    pre_max_epoch   bigint,
    committed_at    timestamptz NOT NULL DEFAULT clock_timestamp()
);

-- Index for querying attempts
CREATE INDEX IF NOT EXISTS sink_attempt_log_idx ON sink.attempt_log (trial_id, condition);

-- Max epoch tracking per stream (for fenced conditions)
CREATE TABLE IF NOT EXISTS sink.max_epoch (
    trial_id    text NOT NULL,
    stream_id   text NOT NULL,
    max_epoch   bigint NOT NULL DEFAULT 0,
    PRIMARY KEY (trial_id, stream_id)
);

-- Grant privileges to worker_rw
GRANT SELECT, INSERT, UPDATE ON sink.state TO worker_rw;
GRANT SELECT, INSERT ON sink.effects TO worker_rw;
GRANT SELECT, INSERT, UPDATE ON sink.responses TO worker_rw;
GRANT SELECT, INSERT ON sink.attempt_log TO worker_rw;
GRANT SELECT, INSERT, UPDATE ON sink.max_epoch TO worker_rw;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA sink TO worker_rw;
