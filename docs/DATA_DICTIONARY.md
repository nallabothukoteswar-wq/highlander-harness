# Data Dictionary

This document describes every raw file and column in the Highlander experiment outputs.

## Raw Output Files

### trials.csv
Per-trial metadata and results.

| Column | Type | Description |
|--------|------|-------------|
| trial_id | string | Unique trial identifier |
| series | string | Series identifier (A, B, C, D, E, F, G) |
| condition | string | Condition identifier (C1, C1u, C1v, C2, C2f, C3, C3r, C4) |
| workload | string | Workload type (dup, ordered) |
| parameters | json | Trial-specific parameters (b, d, L, etc.) |
| seed | integer | Random seed for trial |
| platform | string | Platform (local, kind) |
| valid | boolean | Whether trial passed verification |
| invalid_reason | string | Reason if invalid |

### attempts.csv
Full export of sink.attempt_log (co-located sink).

| Column | Type | Description |
|--------|------|-------------|
| trial_id | string | Trial identifier |
| condition | string | Condition identifier |
| worker_id | string | Worker identifier |
| incarnation | uuid | Worker process incarnation |
| stream_id | string | Ownership key |
| epoch | bigint | Ownership epoch |
| op_key | string | Operation key |
| business_key | string | Business key |
| target_key | string | Target key |
| source_version | bigint | Source version |
| prep_cpu_ns | bigint | Preparation CPU time in nanoseconds |
| at_risk | boolean | Whether submission was at-risk (post-SIGCONT) |
| outcome | string | accepted, rejected, or replayed |
| reason | string | Rejection reason (not_holder, stale_epoch, expired, dup_key, version_not_newer) |
| pre_version | bigint | Version before write |
| pre_max_epoch | bigint | Max epoch before write |
| committed_at | timestamptz | Commit timestamp (database clock) |

### grants.csv
Export of own.grants.

| Column | Type | Description |
|--------|------|-------------|
| stream_id | string | Ownership key |
| epoch | bigint | Epoch number |
| holder | uuid | Holder incarnation |
| granted_at | timestamptz | Grant timestamp (database clock) |

### renewals.csv
Export of own.renewals.

| Column | Type | Description |
|--------|------|-------------|
| stream_id | string | Ownership key |
| epoch | bigint | Epoch number |
| holder | uuid | Holder incarnation |
| renewed_at | timestamptz | Renewal timestamp (database clock) |
| expires_at | timestamptz | New expiry timestamp |

### transitions.csv
Export of ctl.transitions.

| Column | Type | Description |
|--------|------|-------------|
| trial_id | string | Trial identifier |
| incarnation | uuid | Worker incarnation |
| from_state | string | Previous state |
| to_state | string | New state |
| event | string | Transition event |
| at | timestamptz | Transition timestamp (database clock) |

### heartbeats_summary.csv
Export of ctl.heartbeat_summary view.

| Column | Type | Description |
|--------|------|-------------|
| trial_id | string | Trial identifier |
| worker_id | string | Worker identifier |
| incarnation | uuid | Worker incarnation |
| first_beat | timestamptz | First heartbeat timestamp |
| last_beat | timestamptz | Last heartbeat timestamp |
| beat_count | integer | Total heartbeat count |

### fault_markers.csv
Export of ctl.fault_markers.

| Column | Type | Description |
|--------|------|-------------|
| trial_id | string | Trial identifier |
| worker_id | string | Worker identifier |
| incarnation | uuid | Worker incarnation |
| marker_type | string | Marker type (cont) |
| at | timestamptz | Marker timestamp (database clock) |

### kill_markers.csv
Export of ctl.kill_markers.

| Column | Type | Description |
|--------|------|-------------|
| trial_id | string | Trial identifier |
| worker_id | string | Worker identifier |
| incarnation | uuid | Worker incarnation |
| marker_type | string | Marker type (before, after) |
| at | timestamptz | Marker timestamp (database clock) |

### takeover.csv
Per-trial takeover metrics (Series E).

| Column | Type | Description |
|--------|------|-------------|
| trial_id | string | Trial identifier |
| takeover_interval | interval | Time from kill to first accepted replacement write |
| delta_interval | interval | Time from last renewal to kill |
| observed_p | interval | Observed P (expiry → grant) |
| observed_s | interval | Observed S (grant → first submission) |
| observed_w | interval | Observed W (submission → commit) |
| bound | interval | Theoretical bound (max(0, L − Δ) + P + S + W) |
| violation_flag | boolean | Whether observed P, S, or W exceeded budget |

### replay.csv
Replay outcomes (Series D).

| Column | Type | Description |
|--------|------|-------------|
| trial_id | string | Trial identifier |
| condition | string | Condition identifier |
| op_key | string | Operation key |
| retry_outcome | string | duplicate_accepted, unresolved_ambiguous, replay_stable, replay_mismatch |

### requests.csv
Request logs (Series F and G).

| Column | Type | Description |
|--------|------|-------------|
| scheduled_ts | float | Scheduled arrival timestamp |
| sent_ts | float | Actual send timestamp |
| target | string | Target service |
| x_version | string | X-Version header |
| status | integer | HTTP status code |
| latency | float | Request latency in seconds |

### replicas_timeline.csv
Replica count timeline (Series F and G).

| Column | Type | Description |
|--------|------|-------------|
| timestamp | timestamptz | Timestamp |
| n_replicas | integer | Number of replicas |
| version | string | Version (v1, v2) |

### releases.csv
Release events (Series G).

| Column | Type | Description |
|--------|------|-------------|
| trial_id | string | Trial identifier |
| mechanism | string | Release mechanism (rolling, blue-green, canary) |
| start_time | timestamptz | Release start timestamp |
| end_time | timestamptz | Release end timestamp |
| extra_replica_seconds | float | ∫(total ready − 7) dt |
| time_to_full_traffic | float | Time to 100% new version traffic |
| p99_latency | float | P99 latency during release |
| slo_violation_fraction | float | Fraction of SLO violations |
| error_fraction | float | Fraction of errors |

### manifest.json
Campaign metadata.

| Field | Type | Description |
|-------|------|-------------|
| start_time | string | Campaign start timestamp |
| end_time | string | Campaign end timestamp |
| host | object | Host system information |
| docker | object | Docker version |
| kubernetes | object | Kubernetes and kind versions |
| images | object | Docker image digests |
| postgres | object | PostgreSQL version and settings |
| python | object | Python version |
| go | object | Go version |
| git | object | Git commit and dirty flag |
| config | object | Experiment configuration |
