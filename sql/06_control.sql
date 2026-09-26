-- Control schema
-- Handles heartbeats, lifecycle transitions, fault injection, and trial metadata

-- Incarnations: tracks worker process starts
CREATE TABLE IF NOT EXISTS ctl.incarnations (
    trial_id    text NOT NULL,
    worker_id   text NOT NULL,
    incarnation uuid NOT NULL,
    started_at  timestamptz NOT NULL DEFAULT clock_timestamp(),
    pid         int,
    PRIMARY KEY (trial_id, worker_id, incarnation)
);

-- Heartbeats: worker liveness
CREATE TABLE IF NOT EXISTS ctl.heartbeats (
    trial_id    text NOT NULL,
    worker_id   text NOT NULL,
    incarnation uuid NOT NULL,
    beat_at     timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (trial_id, worker_id, beat_at)
);

-- State transitions: worker lifecycle state changes
CREATE TABLE IF NOT EXISTS ctl.transitions (
    trial_id    text NOT NULL,
    incarnation uuid NOT NULL,
    from_state  text,
    to_state    text NOT NULL,
    event       text NOT NULL,
    at          timestamptz NOT NULL DEFAULT clock_timestamp()
);

-- Fault plan: specifies which worker to fault and when
CREATE TABLE IF NOT EXISTS ctl.fault_plan (
    trial_id    text NOT NULL,
    worker_id   text NOT NULL,
    incarnation uuid NOT NULL,
    fault_type  text NOT NULL,  -- pause, kill
    trigger_type text NOT NULL,  -- after_first_accept, after_grant
    armed       boolean NOT NULL DEFAULT false,
    PRIMARY KEY (trial_id, worker_id, incarnation)
);

-- Fault events: logs when worker prepares a batch before fault
CREATE TABLE IF NOT EXISTS ctl.fault_events (
    trial_id    text NOT NULL,
    worker_id   text NOT NULL,
    incarnation uuid NOT NULL,
    event_type  text NOT NULL,  -- prepared_batch
    op_keys     text[] NOT NULL,
    at          timestamptz NOT NULL DEFAULT clock_timestamp()
);

-- Fault markers: records SIGCONT timing
CREATE TABLE IF NOT EXISTS ctl.fault_markers (
    trial_id    text NOT NULL,
    worker_id   text NOT NULL,
    incarnation uuid NOT NULL,
    marker_type text NOT NULL,  -- cont
    at          timestamptz NOT NULL DEFAULT clock_timestamp()
);

-- Kill markers: brackets SIGKILL timing
CREATE TABLE IF NOT EXISTS ctl.kill_markers (
    trial_id    text NOT NULL,
    worker_id   text NOT NULL,
    incarnation uuid NOT NULL,
    marker_type text NOT NULL,  -- before, after
    at          timestamptz NOT NULL DEFAULT clock_timestamp()
);

-- Trial metadata
CREATE TABLE IF NOT EXISTS ctl.trials (
    trial_id    text PRIMARY KEY,
    series      text NOT NULL,
    condition   text NOT NULL,
    workload    text NOT NULL,
    started_at  timestamptz NOT NULL DEFAULT clock_timestamp(),
    ended_at    timestamptz,
    parameters  jsonb,
    seed        bigint,
    platform    text NOT NULL,
    valid       boolean NOT NULL DEFAULT true,
    invalid_reason text
);

-- Grant privileges to worker_rw
GRANT SELECT, INSERT, UPDATE ON ctl.incarnations TO worker_rw;
GRANT SELECT, INSERT ON ctl.heartbeats TO worker_rw;
GRANT SELECT, INSERT ON ctl.transitions TO worker_rw;
GRANT SELECT, UPDATE ON ctl.fault_plan TO worker_rw;
GRANT SELECT, INSERT ON ctl.fault_events TO worker_rw;
GRANT SELECT, INSERT ON ctl.fault_markers TO worker_rw;
GRANT SELECT, INSERT ON ctl.kill_markers TO worker_rw;
GRANT SELECT, INSERT, UPDATE ON ctl.trials TO worker_rw;

-- Grant read-only privileges to rsink_rw (for heartbeats only)
GRANT SELECT, INSERT ON ctl.heartbeats TO rsink_rw;
