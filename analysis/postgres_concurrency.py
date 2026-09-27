"""Run limited real handover and acquisition races on PostgreSQL 16.

Separate connections race under host-thread scheduling; SQL attempt logs and
late_accepts views provide the outcomes. This is not a cluster fault campaign.
"""
from __future__ import annotations

import csv
import json
import random
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

import psycopg

from analysis.postgres_schedules import OUT, call, dsn, metrics, prepare_database, reset_trial

SEED = 2026
REPEATS = 5
TRIALS = 30
ITEMS = 40
HANDOVER_AFTER = 8
ROUNDS = 1000
CONDITIONS = ('C2f', 'C3', 'C4', 'C3r')


def write_csv(path, rows):
    with path.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def interleaving(admin, condition, repeat, trial):
    reset_trial(admin, condition)
    run_id = f'pg:handover:{condition}:{repeat}:{trial}'
    former, successor = uuid.uuid4(), uuid.uuid4()
    with psycopg.connect(dsn(role='worker_rw'), autocommit=True) as owner:
        epoch_old = owner.execute('SELECT own.acquire(%s,%s,%s::numeric)',
                                  ('S1', former, 60)).fetchone()[0]
        assert epoch_old == 1
    with psycopg.connect(dsn(role='rsink_rw' if condition == 'C3r' else 'worker_rw'),
                         autocommit=True) as initial:
        for i in range(ITEMS):
            key = f'feed-{i}'
            assert call(initial, run_id, condition, key, f'{key}:initial',
                        1, epoch_old, former)['outcome'] == 'accepted'

    progress = threading.Event()
    seed = SEED + repeat * 1000 + trial

    def former_writes():
        rng = random.Random(seed)
        role = 'rsink_rw' if condition == 'C3r' else 'worker_rw'
        with psycopg.connect(dsn(role=role), autocommit=True) as connection:
            for i in range(ITEMS):
                time.sleep(.001 + rng.random() * .002)
                key = f'feed-{i}'
                call(connection, run_id, condition, key, f'{key}:former',
                     2, epoch_old, former, True)
                if i + 1 == HANDOVER_AFTER:
                    progress.set()

    def takeover_then_write():
        assert progress.wait(timeout=15), 'former never started submitting writes'
        # This is a distinct session and thread from the former writer.
        with psycopg.connect(dsn(), autocommit=True) as coordinator:
            changed = coordinator.execute(
                "UPDATE own.owner SET expires_at = clock_timestamp() - interval '1 second' "
                'WHERE stream_id=%s AND holder=%s AND epoch=%s',
                ('S1', former, epoch_old)).rowcount
            assert changed == 1
        with psycopg.connect(dsn(role='worker_rw'), autocommit=True) as candidate:
            epoch_new = candidate.execute('SELECT own.acquire(%s,%s,%s::numeric)',
                                          ('S1', successor, 60)).fetchone()[0]
            assert epoch_new == 2
        rng = random.Random(seed + 999999)
        role = 'rsink_rw' if condition == 'C3r' else 'worker_rw'
        with psycopg.connect(dsn(role=role), autocommit=True) as connection:
            for i in range(ITEMS):
                time.sleep(rng.random() * .002)
                key = f'feed-{i}'
                call(connection, run_id, condition, key, f'{key}:current',
                     3, epoch_new, successor)

    with ThreadPoolExecutor(max_workers=2) as pool:
        old = pool.submit(former_writes)
        new = pool.submit(takeover_then_write)
        old.result(timeout=60)
        new.result(timeout=60)

    schema = 'rsink' if condition == 'C3r' else 'sink'
    post, legitimate = admin.execute(
        f'SELECT count(*) FILTER (WHERE a.committed_at > g.granted_at), '
        f"count(*) FILTER (WHERE a.committed_at <= g.granted_at AND a.outcome='accepted') "
        f'FROM {schema}.attempt_log a JOIN own.grants g ON g.stream_id=a.stream_id AND g.epoch=2 '
        'WHERE a.trial_id=%s AND a.incarnation=%s AND a.at_risk',
        (run_id, former)).fetchone()
    result = metrics(admin, run_id, condition, 'ordered_pause')
    late = result['late_accept'] if condition in ('C3', 'C3r') else admin.execute(
        'SELECT coalesce(sum(late_accept_count),0) FROM sink.late_accepts WHERE trial_id=%s',
        (run_id,)).fetchone()[0]
    assert post > 0, (condition, repeat, trial, 'takeover happened after all former writes')
    assert result['accepted'] + result['rejected_fence'] + result['rejected_remote_epoch'] == ITEMS
    assert late <= post and result['epoch_regression'] == 0
    if condition != 'C3r':
        assert late == 0
    return {'condition': condition, 'repeat': repeat, 'trial': trial, 'seed': seed,
            'former_attempts': ITEMS, 'pre_grant_accepted': legitimate,
            'post_grant_attempts': post, 'late_accept': late,
            'epoch_regression': result['epoch_regression']}


def acquisition_races(admin):
    """Race two persistent sessions on fresh and expired owner rows."""
    with psycopg.connect(dsn(role='worker_rw'), autocommit=True) as first, \
            psycopg.connect(dsn(role='worker_rw'), autocommit=True) as second:
        def acquire(connection, stream, holder, barrier):
            barrier.wait(timeout=15)
            return connection.execute('SELECT own.acquire(%s,%s,%s::numeric)',
                                      (stream, holder, 60)).fetchone()[0]
        with ThreadPoolExecutor(max_workers=2) as pool:
            for path in ('fresh', 'expired'):
                for round_number in range(ROUNDS):
                    stream = f'{path}-race-{round_number}'
                    expected = 1 if path == 'fresh' else 2
                    if path == 'expired':
                        initial = first.execute('SELECT own.acquire(%s,%s,%s::numeric)',
                                                (stream, uuid.uuid4(), 60)).fetchone()[0]
                        assert initial == 1
                        changed = admin.execute(
                            "UPDATE own.owner SET expires_at=clock_timestamp() - interval '1 second' "
                            'WHERE stream_id=%s AND epoch=1', (stream,)).rowcount
                        assert changed == 1
                    barrier = threading.Barrier(2)
                    one = pool.submit(acquire, first, stream, uuid.uuid4(), barrier)
                    two = pool.submit(acquire, second, stream, uuid.uuid4(), barrier)
                    outcomes = (one.result(timeout=30), two.result(timeout=30))
                    epoch = admin.execute('SELECT epoch FROM own.owner WHERE stream_id=%s',
                                          (stream,)).fetchone()[0]
                    grants = admin.execute('SELECT count(*) FROM own.grants '
                                           'WHERE stream_id=%s AND epoch=%s',
                                           (stream, expected)).fetchone()[0]
                    winners = sum(value is not None for value in outcomes)
                    yield {'path': path, 'round': round_number, 'winners': winners,
                           'winning_epoch': epoch, 'expected_epoch': expected,
                           'grants_at_epoch': grants}
                    assert winners == grants == 1 and epoch == expected, (path, round_number, outcomes)


def main():
    version = prepare_database()
    rows = []
    with psycopg.connect(dsn(), autocommit=True) as admin:
        for repeat in range(REPEATS):
            for condition in CONDITIONS:
                for trial in range(TRIALS):
                    rows.append(interleaving(admin, condition, repeat, trial))
            print(f'Completed threaded repetition {repeat + 1}/{REPEATS}', flush=True)
        races = list(acquisition_races(admin))
    OUT.mkdir(parents=True, exist_ok=True)
    write_csv(OUT / 'pg_concurrency_trials.csv', rows)
    write_csv(OUT / 'pg_acquisition_races.csv', races)
    summary = []
    for repeat in range(REPEATS):
        for condition in CONDITIONS:
            group = [r for r in rows if r['condition'] == condition and r['repeat'] == repeat]
            summary.append({'repeat': repeat, 'condition': condition,
                            'runs': len(group),
                            'post_grant_attempts': sum(r['post_grant_attempts'] for r in group),
                            'late_accept': sum(r['late_accept'] for r in group),
                            'pre_grant_accepted': sum(r['pre_grant_accepted'] for r in group)})
    write_csv(OUT / 'pg_concurrency_summary.csv', summary)
    (OUT / 'pg_concurrency_config.json').write_text(json.dumps({
        'postgresql_version': version, 'seed': SEED, 'repeats': REPEATS,
        'runs_per_condition_per_repeat': TRIALS, 'items_per_worker': ITEMS,
        'handover_after_former_writes': HANDOVER_AFTER,
        'acquisition_rounds_per_path': ROUNDS,
        'takeover': 'admin expires owner row after initial writes; own.acquire issues epoch 2',
    }, indent=2) + '\n')
    print(f'PostgreSQL {version}: {len(rows)} handover trials, {len(races)} acquisition races', flush=True)
    for condition in CONDITIONS:
        counts = [r['late_accept'] for r in summary if r['condition'] == condition]
        print(condition, 'late accepts by repetition:', counts, flush=True)


if __name__ == '__main__':
    main()
