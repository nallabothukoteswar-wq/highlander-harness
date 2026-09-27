"""Run the four scripted workloads through the actual PostgreSQL 16 functions.

Requires an administrative DATABASE_URL on a disposable PostgreSQL instance.
All outcome counts are queried from attempt logs and SQL metric views. This
script does not exercise kind, Pod faults, HTTP serving or production traffic.
"""
from __future__ import annotations

import csv
import json
import os
import random
import time
import uuid
from collections import Counter
from pathlib import Path

import psycopg
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from analysis.exploratory_sqlite import (
    CONDITIONS, FIRST_WRITE_DELAY_S, KEYS, LEASED, LOST_ACK_PROBABILITY,
    RETRY_DELAY_S, SEED, SUCCESSOR_FIRST_PROBABILITY, TRIALS, write_rows,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'paper' / 'supplementary'
STUDY_DB = 'highlander_study'
SQL_FILES = ('00_roles.sql', '01_schemas.sql', '02_ownership.sql',
             '03_queue.sql', '04_sinks_colocated.sql', '05_sink_remote.sql',
             '06_control.sql', '07_views.sql', '08_sink_functions.sql')
FIELDS = ('series', 'condition', 'trial', 'seed', 'delay_s', 'items', 'at_risk_attempts',
          'accepted', 'rejected_fence', 'rejected_remote_epoch', 'rejected_version',
          'rejected_duplicate', 'replayed', 'accepted_duplicates',
          'version_regression', 'epoch_regression', 'late_accept', 'lost_ack',
          'duplicate_accepted', 'unresolved_ambiguous', 'replay_stable', 'replay_mismatch')


def dsn(database=STUDY_DB, role=None):
    source = os.environ.get('DATABASE_URL')
    params = conninfo_to_dict(source) if source else {
        'host': os.environ.get('DB_HOST', 'localhost'),
        'port': os.environ.get('DB_PORT', '5432'),
        'user': os.environ.get('DB_USER', 'postgres'),
        'password': os.environ.get('DB_PASSWORD', 'testpassword'),
    }
    params['dbname'] = database
    if role:
        params['user'] = role
        params['password'] = {'worker_rw': 'worker_password',
                              'rsink_rw': 'rsink_password'}[role]
    return make_conninfo(**params)


def prepare_database():
    with psycopg.connect(dsn('postgres'), autocommit=True) as admin:
        admin.execute(f'DROP DATABASE IF EXISTS {STUDY_DB}')
        admin.execute(f'CREATE DATABASE {STUDY_DB}')
    with psycopg.connect(dsn(), autocommit=True) as admin:
        for name in SQL_FILES:
            admin.execute((ROOT / 'sql' / name).read_text())
        return admin.execute('SHOW server_version').fetchone()[0]


def reset_trial(admin, condition):
    admin.execute('TRUNCATE own.grants, own.renewals, own.owner, '
                  'sink.state, sink.effects, sink.responses, sink.attempt_log, sink.max_epoch, '
                  'rsink.fence, rsink.state, rsink.effects, rsink.attempt_log CASCADE')
    admin.execute('ALTER TABLE sink.effects DROP CONSTRAINT IF EXISTS effects_op_key_unique')
    if condition in ('C1u', 'C3', 'C3r', 'C4'):
        admin.execute('ALTER TABLE sink.effects ADD CONSTRAINT effects_op_key_unique UNIQUE (trial_id, op_key)')


def call(conn, trial_id, condition, key, op_key, version, epoch, identity, risk=False):
    function = {'C1': 'sink.sink_plain', 'C1u': 'sink.sink_unique',
                'C1v': 'sink.sink_version', 'C2': 'sink.sink_plain',
                'C2f': 'sink.sink_fenced', 'C3': 'sink.sink_fenced_unique',
                'C3r': 'rsink.sink_remote', 'C4': 'sink.sink_fenced_unique_cached'}[condition]
    return conn.execute(f'SELECT {function}(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                        (trial_id, condition, str(identity), identity, 'S1', epoch,
                         op_key, key, key, version, 0, risk)).fetchone()[0]


def metrics(admin, trial_id, condition, series):
    schema = 'rsink' if condition == 'C3r' else 'sink'
    output = Counter()
    for outcome, reason, count in admin.execute(
            f'SELECT outcome, reason, count(*) FROM {schema}.attempt_log '
            'WHERE trial_id=%s AND at_risk GROUP BY outcome, reason', (trial_id,)):
        output['accepted' if outcome == 'accepted' else 'replayed' if outcome == 'replayed'
               else {'dup_key': 'rejected_duplicate', 'version_not_newer': 'rejected_version',
                     'stale_epoch': 'rejected_remote_epoch' if condition == 'C3r' else 'rejected_fence',
                     'not_holder': 'rejected_fence', 'expired': 'rejected_fence'}[reason]] += count
    if series == 'ordered_pause':
        for view, field in (('version_regressions', 'version_regression'),
                            ('epoch_regressions', 'epoch_regression')):
            row = admin.execute(f'SELECT at_risk_regression_count FROM {schema}.{view} '
                                'WHERE trial_id=%s', (trial_id,)).fetchone()
            output[field] = row[0] if row else 0
    if series in ('ordered_pause', 'after_grant') and condition in ('C3', 'C3r'):
        row = admin.execute(f'SELECT coalesce(sum(late_accept_count),0) FROM '
                            f'{schema}.late_accepts WHERE trial_id=%s', (trial_id,)).fetchone()
        output['late_accept'] = row[0]
    if series == 'after_grant':
        row = admin.execute(f'SELECT at_risk_regression_count FROM {schema}.version_regressions '
                            'WHERE trial_id=%s', (trial_id,)).fetchone()
        output['version_regression'] = row[0] if row else 0
    if series == 'duplicate_pause':
        if schema == 'sink':
            row = admin.execute('SELECT duplicate_count FROM sink.accepted_duplicates '
                                'WHERE trial_id=%s', (trial_id,)).fetchone()
            output['accepted_duplicates'] = row[0] if row else 0
        else:
            row = admin.execute('SELECT coalesce(sum(n-1),0) FROM '
                                '(SELECT count(*) n FROM rsink.attempt_log WHERE trial_id=%s '
                                "AND outcome='accepted' GROUP BY business_key HAVING count(*)>1) q",
                                (trial_id,)).fetchone()
            output['accepted_duplicates'] = row[0]
    if series == 'lost_ack':
        grouped = admin.execute(
            'WITH ranked AS (SELECT outcome, row_number() OVER '
            '(PARTITION BY op_key ORDER BY committed_at, ctid) AS n '
            'FROM sink.attempt_log WHERE trial_id=%s) '
            'SELECT outcome, count(*) FROM ranked WHERE n>1 GROUP BY outcome',
            (trial_id,)).fetchall()
        mapping = {'accepted': 'duplicate_accepted', 'rejected': 'unresolved_ambiguous',
                   'replayed': 'replay_stable'}
        for outcome, count in grouped:
            output[mapping[outcome]] = count
        output['lost_ack'] = sum(count for _, count in grouped)
        output['replay_mismatch'] = 0  # Calls assert exact cached responses before this query.
    return output


def run_cell(admin, condition, series, trial, delay=None):
    trial_id = f'pg:{series}:{condition}:{trial}:{delay}'
    reset_trial(admin, condition)
    former, successor = uuid.uuid4(), uuid.uuid4()
    a = psycopg.connect(dsn(role='worker_rw'), autocommit=True)
    b = psycopg.connect(dsn(role='worker_rw'), autocommit=True)
    ra = psycopg.connect(dsn(role='rsink_rw'), autocommit=True) if condition == 'C3r' else None
    rb = psycopg.connect(dsn(role='rsink_rw'), autocommit=True) if condition == 'C3r' else None
    old_conn, new_conn = (ra or a), (rb or b)
    lease = condition in LEASED
    epoch_a = epoch_b = None
    seed = SEED + (100000 if series == 'lost_ack' else 0) + trial
    try:
        if lease:
            epoch_a = a.execute('SELECT own.acquire(%s,%s,%s::numeric)',
                                ('S1', former, .3)).fetchone()[0]
            assert epoch_a == 1
        if series != 'lost_ack':
            for i in range(KEYS):
                key = f'feed-{i}' if series != 'duplicate_pause' else f'op-{i}'
                original_key = key if series == 'duplicate_pause' else f'{key}:initial'
                result = call(old_conn, trial_id, condition, key, original_key, 1, epoch_a, former)
                assert result['outcome'] == 'accepted', (condition, series, i, result)
        if lease:
            time.sleep(.35)
            epoch_b = b.execute('SELECT own.acquire(%s,%s,%s::numeric)',
                                ('S1', successor, 60)).fetchone()[0]
            assert epoch_b == 2
        rng = random.Random(seed)
        if series == 'ordered_pause':
            keys = list(range(KEYS))
            rng.shuffle(keys)
            for i in keys:
                key = f'feed-{i}'
                successor_first = rng.random() < SUCCESSOR_FIRST_PROBABILITY
                if successor_first:
                    call(new_conn, trial_id, condition, key, f'{key}:successor', 3, epoch_b, successor)
                call(old_conn, trial_id, condition, key, f'{key}:delayed', 2, epoch_a, former, True)
                if not successor_first:
                    call(new_conn, trial_id, condition, key, f'{key}:successor', 3, epoch_b, successor)
        elif series == 'duplicate_pause':
            for i in range(KEYS):
                key = f'op-{i}'
                call(old_conn, trial_id, condition, key, key, 1, epoch_a, former, True)
        elif series == 'lost_ack':
            for i in range(KEYS):
                key = f'retry-{i}'
                original = call(new_conn, trial_id, condition, key, key, 1, epoch_b, successor)
                assert original['outcome'] == 'accepted'
                if rng.random() < LOST_ACK_PROBABILITY:
                    time.sleep(RETRY_DELAY_S)
                    repeated = call(new_conn, trial_id, condition, key, key, 1, epoch_b, successor)
                    if condition == 'C4':
                        assert repeated['outcome'] == 'replayed'
                        assert repeated['response'] == original['response']
        elif series == 'after_grant':
            assert delay in (0, 1, 5)
            grant_time = time.monotonic()
            def old_batch():
                for i in range(KEYS):
                    key = f'feed-{i}'
                    call(old_conn, trial_id, condition, key, f'{key}:delayed', 2, epoch_a, former, True)
            def new_batch():
                for i in range(KEYS):
                    key = f'feed-{i}'
                    call(new_conn, trial_id, condition, key, f'{key}:successor', 3, epoch_b, successor)
            def until(target):
                remaining = grant_time + target - time.monotonic()
                if remaining > 0:
                    time.sleep(remaining)
            if delay < FIRST_WRITE_DELAY_S:
                until(delay)
                old_batch()
                until(FIRST_WRITE_DELAY_S)
                new_batch()
            else:
                until(FIRST_WRITE_DELAY_S)
                new_batch()
                until(delay)
                old_batch()
        else:
            raise ValueError(series)
    finally:
        for conn in (ra, rb, a, b):
            if conn:
                conn.close()
    totals = metrics(admin, trial_id, condition, series)
    return {'series': series, 'condition': condition, 'trial': trial, 'seed': seed,
            'delay_s': delay if delay is not None else '', 'items': KEYS,
            'at_risk_attempts': 0 if series == 'lost_ack' else KEYS, **totals}


def summarize(rows):
    summary = []
    for series in ('ordered_pause', 'duplicate_pause', 'lost_ack', 'after_grant'):
        for condition in CONDITIONS:
            for delay in ((0, 1, 5) if series == 'after_grant' else (None,)):
                group = [r for r in rows if r['series'] == series and r['condition'] == condition
                         and (delay is None or r['delay_s'] == delay)]
                if not group:
                    continue
                fields = {'ordered_pause': ('version_regression', 'epoch_regression', 'late_accept'),
                          'duplicate_pause': ('accepted_duplicates',),
                          'lost_ack': ('lost_ack', 'duplicate_accepted', 'unresolved_ambiguous',
                                       'replay_stable', 'replay_mismatch'),
                          'after_grant': ('late_accept',)}[series]
                for metric in fields:
                    if metric == 'epoch_regression' and condition not in LEASED:
                        continue
                    if metric == 'late_accept' and series == 'ordered_pause' and condition not in ('C3', 'C3r'):
                        continue
                    summary.append({'series': series, 'condition': condition,
                                    'delay_s': '' if delay is None else delay,
                                    'metric': metric, 'scheduled_runs': len(group),
                                    'items': sum(r['items'] for r in group),
                                    'events': sum(r.get(metric, 0) for r in group),
                                    'at_risk_attempts': sum(r['at_risk_attempts'] for r in group)})
    return summary


def compare(sqlite_rows, pg_rows):
    # Every result field is checked, not just the headline late-accept values.
    categories = ('accepted', 'rejected_fence', 'rejected_remote_epoch', 'rejected_version',
                  'rejected_duplicate', 'replayed', 'accepted_duplicates', 'version_regression',
                  'epoch_regression', 'late_accept', 'lost_ack', 'duplicate_accepted',
                  'unresolved_ambiguous', 'replay_stable', 'replay_mismatch')
    index = lambda rows: {(r['series'], r['condition'], int(r['trial']),
                           str(r.get('delay_s') if r.get('delay_s') is not None else '')): r
                          for r in rows}
    left, right = index(sqlite_rows), index(pg_rows)
    assert left.keys() == right.keys(), 'PostgreSQL and SQLite schedule cells differ'
    mismatches = []
    for key in sorted(left):
        for field in categories:
            s, p = int(left[key].get(field) or 0), int(right[key].get(field) or 0)
            if s != p:
                mismatches.append((key, field, s, p))
    lines = ['# PostgreSQL versus SQLite scheduled sink rules', '',
             'Both studies use the same declared inputs. PostgreSQL values are from SQL attempt logs '
             'and views; SQLite values are from the independent rule model. These are scripted '
             'schedules, not failure-rate or cluster measurements.', '',
             '| Series | Condition | Delay | Metric | SQLite | PostgreSQL |',
             '| --- | --- | ---: | --- | ---: | ---: |']
    for key in sorted(left):
        for field in categories:
            s, p = int(left[key].get(field) or 0), int(right[key].get(field) or 0)
            if s or p:
                lines.append(f'| {key[0]} | {key[1]} | {key[3] or "--"} | {field} | {s} | {p} |')
    lines += ['', f'Mismatched cells/metrics: {len(mismatches)}.', '']
    (ROOT / 'docs' / 'PG_VS_SQLITE.md').write_text('\n'.join(lines))
    return mismatches


def main():
    version = prepare_database()
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    with psycopg.connect(dsn(), autocommit=True) as admin:
        for condition in CONDITIONS:
            for trial in range(TRIALS):
                rows.append(run_cell(admin, condition, 'ordered_pause', trial))
            if condition != 'C1v':
                rows.append(run_cell(admin, condition, 'duplicate_pause', 0))
        for condition in ('C2f', 'C3', 'C4'):
            for trial in range(TRIALS):
                rows.append(run_cell(admin, condition, 'lost_ack', trial))
        for condition in ('C3', 'C3r'):
            for delay in (0, 1, 5):
                rows.append(run_cell(admin, condition, 'after_grant', 0, delay))
    write_rows(OUT / 'pg_trials.csv', rows, FIELDS)
    summary = summarize(rows)
    write_rows(OUT / 'pg_summary.csv', summary, list(summary[0]))
    config = json.loads((OUT / 'experiment_config.json').read_text())
    config['postgresql_version'] = version
    config['postgresql_connection_route'] = 'GitHub Actions postgres:16 service' if os.environ.get('GITHUB_ACTIONS') else 'local PostgreSQL'
    (OUT / 'experiment_config.json').write_text(json.dumps(config, indent=2) + '\n')
    with (OUT / 'sqlite_trials.csv').open(newline='') as f:
        mismatches = compare(list(csv.DictReader(f)), rows)
    print(f'PostgreSQL {version}; {len(rows)} raw runs, {len(summary)} summary rows; '
          f'{len(mismatches)} metric mismatches')
    if mismatches:
        print('First mismatches:', mismatches[:10])


if __name__ == '__main__':
    main()
