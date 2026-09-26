-- Remote sink schema
-- Implements sink functions for condition C3r
-- Runs as role rsink_rw with no access to own schema

-- Remote fence table: tracks current epoch per stream
CREATE TABLE IF NOT EXISTS rsink.fence (
    trial_id     text NOT NULL,
    stream_id    text NOT NULL,
    e_current    bigint NOT NULL DEFAULT 0,
    advanced_at  timestamptz,
    PRIMARY KEY (trial_id, stream_id)
);

-- Remote state table: tracks current version per target_key
CREATE TABLE IF NOT EXISTS rsink.state (
    trial_id    text NOT NULL,
    target_key  text NOT NULL,
    version     bigint NOT NULL DEFAULT 0,
    PRIMARY KEY (trial_id, target_key)
);

-- Remote effects table: records accepted effects
CREATE TABLE IF NOT EXISTS rsink.effects (
    trial_id    text NOT NULL,
    effect_id   uuid NOT NULL DEFAULT gen_random_uuid(),
    business_key text NOT NULL,
    op_key      text NOT NULL,
    version     bigint NOT NULL,
    committed_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (trial_id, effect_id)
);

-- Unique constraint on op_key (for C3r)
CREATE UNIQUE INDEX IF NOT EXISTS rsink_effects_op_key_idx ON rsink.effects (trial_id, op_key);

-- Remote attempt log: records every sink call attempt
CREATE TABLE IF NOT EXISTS rsink.attempt_log (
    trial_id        text NOT NULL,
    condition       text NOT NULL,
    worker_id       text NOT NULL,
    incarnation     uuid NOT NULL,
    stream_id       text NOT NULL,
    epoch           bigint NOT NULL,
    op_key          text NOT NULL,
    business_key    text NOT NULL,
    target_key      text NOT NULL,
    source_version  bigint NOT NULL,
    prep_cpu_ns     bigint NOT NULL,
    at_risk         boolean NOT NULL DEFAULT false,
    outcome         text NOT NULL,  -- accepted, rejected, replayed
    reason          text,  -- stale_epoch, dup_key
    pre_version     bigint,
    pre_max_epoch   bigint,
    committed_at    timestamptz NOT NULL DEFAULT clock_timestamp()
);

-- Index for querying attempts
CREATE INDEX IF NOT EXISTS rsink_attempt_log_idx ON rsink.attempt_log (trial_id, condition);

-- Grant privileges to rsink_rw only
-- NOTE: rsink_rw has NO privileges on own schema
GRANT SELECT, INSERT, UPDATE ON rsink.fence TO rsink_rw;
GRANT SELECT, INSERT, UPDATE ON rsink.state TO rsink_rw;
GRANT SELECT, INSERT ON rsink.effects TO rsink_rw;
GRANT SELECT, INSERT ON rsink.attempt_log TO rsink_rw;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA rsink TO rsink_rw;
