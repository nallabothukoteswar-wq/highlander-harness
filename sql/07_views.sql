-- Views for derived metrics
-- These views compute the metrics used in analysis

-- Accepted duplicate effects (dup workload)
-- Sum over business keys of max(0, accepted effects - 1)
CREATE OR REPLACE VIEW sink.accepted_duplicates AS
SELECT
    trial_id,
    condition,
    SUM(accepted_count - 1) AS duplicate_count
FROM (
    SELECT
        trial_id,
        condition,
        business_key,
        COUNT(*) AS accepted_count
    FROM sink.attempt_log
    WHERE outcome = 'accepted'
    GROUP BY trial_id, condition, business_key
) sub
WHERE accepted_count > 1
GROUP BY trial_id, condition;

-- Stale overwrites (ordered workload)
-- Accepted write with source_version < pre_version, or epoch < pre_max_epoch
CREATE OR REPLACE VIEW sink.stale_overwrites AS
SELECT
    trial_id,
    condition,
    COUNT(*) FILTER (WHERE source_version < pre_version OR epoch < pre_max_epoch) AS stale_count,
    COUNT(*) FILTER (WHERE at_risk = true AND (source_version < pre_version OR epoch < pre_max_epoch)) AS at_risk_stale_count,
    COUNT(*) AS total_accepted
FROM sink.attempt_log
WHERE outcome = 'accepted'
GROUP BY trial_id, condition;

-- Rejected attempts and wasted CPU
CREATE OR REPLACE VIEW sink.rejected_metrics AS
SELECT
    trial_id,
    condition,
    COUNT(*) FILTER (WHERE outcome = 'rejected') AS rejected_count,
    COALESCE(SUM(prep_cpu_ns) FILTER (WHERE outcome = 'rejected'), 0) AS wasted_prep_cpu_ns
FROM sink.attempt_log
GROUP BY trial_id, condition;

-- Late accepts (C3 and C3r)
-- Accepted write with epoch e whose committed_at > own.grants(stream, e+1).granted_at
CREATE OR REPLACE VIEW sink.late_accepts AS
SELECT
    al.trial_id,
    al.condition,
    al.stream_id,
    al.epoch,
    COUNT(*) AS late_accept_count
FROM sink.attempt_log al
JOIN own.grants g ON g.stream_id = al.stream_id AND g.epoch = al.epoch + 1
WHERE al.outcome = 'accepted'
  AND al.committed_at > g.granted_at
GROUP BY al.trial_id, al.condition, al.stream_id, al.epoch;

-- Remote late accepts (C3r)
CREATE OR REPLACE VIEW rsink.late_accepts AS
SELECT
    al.trial_id,
    al.condition,
    al.stream_id,
    al.epoch,
    COUNT(*) AS late_accept_count
FROM rsink.attempt_log al
JOIN own.grants g ON g.stream_id = al.stream_id AND g.epoch = al.epoch + 1
WHERE al.outcome = 'accepted'
  AND al.committed_at > g.granted_at
GROUP BY al.trial_id, al.condition, al.stream_id, al.epoch;

-- At-risk attempts
-- Submissions the victim makes after SIGCONT from its captured batch
CREATE OR REPLACE VIEW sink.at_risk_attempts AS
SELECT
    trial_id,
    condition,
    worker_id,
    incarnation,
    COUNT(*) AS at_risk_count
FROM sink.attempt_log
WHERE at_risk = true
GROUP BY trial_id, condition, worker_id, incarnation;

-- Heartbeat summary for fault verification
CREATE OR REPLACE VIEW ctl.heartbeat_summary AS
SELECT
    trial_id,
    worker_id,
    incarnation,
    MIN(beat_at) AS first_beat,
    MAX(beat_at) AS last_beat,
    COUNT(*) AS beat_count
FROM ctl.heartbeats
GROUP BY trial_id, worker_id, incarnation;

-- Grant read access on views to worker_rw
GRANT SELECT ON sink.accepted_duplicates TO worker_rw;
GRANT SELECT ON sink.stale_overwrites TO worker_rw;
GRANT SELECT ON sink.rejected_metrics TO worker_rw;
GRANT SELECT ON sink.late_accepts TO worker_rw;
GRANT SELECT ON sink.at_risk_attempts TO worker_rw;
GRANT SELECT ON ctl.heartbeat_summary TO worker_rw;

-- Grant read access on remote views to rsink_rw
GRANT SELECT ON rsink.late_accepts TO rsink_rw;
