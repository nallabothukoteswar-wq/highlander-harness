# Protocol Documentation

This document describes the SQL semantics, state machine, and fault semantics for the Highlander experiment harness.

## SQL Semantics

### Clock Rule
Every time comparison and every recorded timestamp uses `clock_timestamp()`. Never use `now()`, `CURRENT_TIMESTAMP`, or `transaction_timestamp()`.

### Single-Call Rule
Every ownership and sink operation is one autocommit call to a SQL function. No client-side multi-statement transactions.

### Schemas and Roles
- `own`: ownership (worker_rw only)
- `src`: work queue (worker_rw only)
- `sink`: co-located sink (worker_rw only)
- `rsink`: remote sink (rsink_rw only, no access to own)
- `ctl`: control, heartbeats, markers (worker_rw and rsink_rw)

### Ownership Functions
- `own.acquire(stream, me, L)`: Acquire ownership, increments epoch, logs grant
- `own.renew(stream, me, epoch, L)`: Renew lease, only for current holder/epoch/unexpired

### Sink Functions
Each sink function logs exactly one `attempt_log` row with:
- trial_id, condition, worker_id, incarnation, stream_id, epoch
- op_key, business_key, target_key, source_version, prep_cpu_ns, at_risk
- outcome (accepted|rejected|replayed), reason
- pre_version, pre_max_epoch, committed_at

#### Plain (C1, C2)
Apply unconditionally. Dup workload: insert into effects. Ordered: upsert state even if lower.

#### Unique (C1u)
Plain with UNIQUE(op_key) constraint. Conflict = rejected/dup_key.

#### Version (C1v, ordered only)
UPDATE state WHERE version < v. Zero rows updated = rejected/version_not_newer.

#### Fenced (C2f)
Check owner row: reject if not_holder, stale_epoch, or expired. Otherwise apply.

#### Fenced Unique (C3)
Fenced check + UNIQUE(op_key) constraint. Track max_epoch per stream.

#### Fenced Unique Cached (C4)
Fenced check + UNIQUE(op_key) + response cache. Replay returns stored response.

#### Remote (C3r)
Remote fence per stream. Reject if epoch < e_current. Advance fence if epoch > e_current.

## State Machine

Worker states: Standby → Candidate → Active → Draining → Standby, plus Failed.

- **Standby**: Trying to acquire ownership (lease mode) or claiming items (uncoordinated)
- **Candidate**: Ready to become active
- **Active**: Processing items, submitting to sink
- **Draining**: Stopping admission, finishing in-flight work
- **Failed**: Fault occurred or unrecoverable error

Transitions are logged to `ctl.transitions`.

## Fault Semantics

### Pause Fault (SIGSTOP)
1. Worker polls `ctl.fault_plan` for its incarnation
2. When armed, prepare next batch, log `ctl.fault_events(prepared_batch, op_keys)`
3. Self-stop with `os.kill(os.getpid(), SIGSTOP)`
4. After SIGCONT, submit captured batch without revalidating (at_risk = true)
5. Next renewal fails, move to Draining → Standby

### Kill Fault (SIGKILL)
1. Record `ctl.kill_markers(before)`
2. Kill worker with SIGKILL
3. Record `ctl.kill_markers(after)`
4. New incarnation registers

### Lost Ack Simulation (Series D)
After accepted call, with probability `lost_ack_rate`:
- Discard response
- Retry same op_key after 50ms
- Classify as duplicate_accepted, unresolved_ambiguous, or replay_stable/mismatch

## Derived Metrics

### Accepted Duplicate Effects (dup workload)
Σ over business keys of max(0, accepted effects − 1)

### Stale Overwrite (ordered workload)
Accepted write with source_version < pre_version, or epoch < pre_max_epoch

### Rejected Attempts and Wasted CPU
Count of rejected attempts and sum of prep_cpu_ns, normalized per 1,000 items

### Late Accept
Accepted write with epoch e where committed_at > own.grants(stream, e+1).granted_at

### At-Risk Attempts
Submissions victim makes after SIGCONT from captured batch (at_risk = true)
