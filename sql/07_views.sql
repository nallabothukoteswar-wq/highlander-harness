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

DROP VIEW IF EXISTS sink.stale_overwrites;

-- Version regressions are defined for every condition with a source version.
CREATE OR REPLACE VIEW sink.version_regressions AS
SELECT trial_id, condition,
       COUNT(*) FILTER (WHERE source_version < pre_version) AS regression_count,
       COUNT(*) FILTER (WHERE at_risk AND source_version < pre_version) AS at_risk_regression_count
FROM sink.attempt_log
WHERE outcome = 'accepted'
GROUP BY trial_id, condition;

-- Authority regressions apply only to conditions with a lease epoch.
CREATE OR REPLACE VIEW sink.epoch_regressions AS
SELECT trial_id, condition,
       COUNT(*) FILTER (WHERE epoch < pre_max_epoch) AS regression_count,
       COUNT(*) FILTER (WHERE at_risk AND epoch < pre_max_epoch) AS at_risk_regression_count
FROM sink.attempt_log
WHERE outcome = 'accepted' AND condition IN ('C2', 'C2f', 'C3', 'C3r', 'C4')
GROUP BY trial_id, condition;

CREATE OR REPLACE VIEW rsink.version_regressions AS
SELECT trial_id, condition,
       COUNT(*) FILTER (WHERE source_version < pre_version) AS regression_count,
       COUNT(*) FILTER (WHERE at_risk AND source_version < pre_version) AS at_risk_regression_count
FROM rsink.attempt_log WHERE outcome = 'accepted'
GROUP BY trial_id, condition;

CREATE OR REPLACE VIEW rsink.epoch_regressions AS
SELECT trial_id, condition,
       COUNT(*) FILTER (WHERE epoch < pre_max_epoch) AS regression_count,
       COUNT(*) FILTER (WHERE at_risk AND epoch < pre_max_epoch) AS at_risk_regression_count
FROM rsink.attempt_log WHERE outcome = 'accepted'
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
GRANT SELECT ON sink.version_regressions TO worker_rw;
GRANT SELECT ON sink.epoch_regressions TO worker_rw;
GRANT SELECT ON sink.rejected_metrics TO worker_rw;
GRANT SELECT ON sink.late_accepts TO worker_rw;
GRANT SELECT ON sink.at_risk_attempts TO worker_rw;
GRANT SELECT ON ctl.heartbeat_summary TO worker_rw;

-- Analysis uses the administrator role. No own.grants-backed view is granted
-- to the restricted remote writer.
REVOKE ALL ON rsink.late_accepts FROM PUBLIC, rsink_rw;
