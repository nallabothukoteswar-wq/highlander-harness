"""Measure real, independently connected PostgreSQL workers racing in threads.

This is a single-host, one-database concurrency check, not a kind campaign.
Counts are read from SQL attempt logs and views after each completed run.
"""
from __future__ import annotations

import csv
import random
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

import psycopg

from analysis.postgres_schedules import OUT, call, dsn, metrics, prepare_database, reset_trial

SEED = 2026
TRIALS = 30
ITEMS = 20
ROUNDS = 1000
CONDITIONS = ('C2f', 'C3', 'C4', 'C3r')


def write_csv(path, rows, fields):
    with path.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def interleaving(admin, condition, trial):
    reset_trial(admin, condition)
    run_id = f'pg:threaded:{condition}:{trial}'
    former, current = uuid.uuid4(), uuid.uuid4()
    with psycopg.connect(dsn(role='worker_rw'), autocommit=True) as owner:
        epoch_old = owner.execute('SELECT own.acquire(%s,%s,%s::numeric)',
                                  ('S1', former, .3)).fetchone()[0]
        assert epoch_old == 1
    def worker(identity, epoch, version, label, ready):
        role = 'rsink_rw' if condition == 'C3r' else 'worker_rw'
        rng = random.Random(SEED + trial * 11 + (0 if label == 'former' else 1))
        with psycopg.connect(dsn(role=role), autocommit=True) as connection:
            ready.wait(timeout=10)
            for i in range(ITEMS):
                time.sleep(rng.random() * .001)
                key = f'feed-{i}'
                call(connection, run_id, condition, key, f'{key}:{label}',
                     version, epoch, identity, label == 'former')

    with psycopg.connect(dsn(role='rsink_rw' if condition == 'C3r' else 'worker_rw'),
                         autocommit=True) as initial:
        for i in range(ITEMS):
            key = f'feed-{i}'
            assert call(initial, run_id, condition, key, f'{key}:initial',
                        1, epoch_old, former)['outcome'] == 'accepted'
    time.sleep(.35)
    with psycopg.connect(dsn(role='worker_rw'), autocommit=True) as successor:
        epoch_new = successor.execute('SELECT own.acquire(%s,%s,%s::numeric)',
                                      ('S1', current, 60)).fetchone()[0]
        assert epoch_new == 2
    barrier = threading.Barrier(2)
    with ThreadPoolExecutor(max_workers=2) as pool:
        old = pool.submit(worker, former, epoch_old, 2, 'former', barrier)
        new = pool.submit(worker, current, epoch_new, 3, 'current', barrier)
        old.result(timeout=30)
        new.result(timeout=30)
    result = metrics(admin, run_id, condition, 'ordered_pause')
    assert result['accepted'] + result['rejected_fence'] + result['rejected_remote_epoch'] == ITEMS
    assert result['epoch_regression'] == 0
    if condition != 'C3r':
        assert result['accepted'] == 0
    return {'condition': condition, 'trial': trial, 'seed': SEED + trial * 11,
            'former_attempts': ITEMS, 'former_accepted': result['accepted'],
            'former_rejected': result['rejected_fence'] + result['rejected_remote_epoch'],
            'late_accept': result['late_accept'], 'epoch_regression': result['epoch_regression']}


def reacquisition_races(admin):
    """Persistent, independent sessions attempt an empty owner key concurrently."""
    with psycopg.connect(dsn(role='worker_rw'), autocommit=True) as first, \
            psycopg.connect(dsn(role='worker_rw'), autocommit=True) as second:
        def acquire(connection, stream, holder, barrier):
            barrier.wait(timeout=10)
            return connection.execute('SELECT own.acquire(%s,%s,%s::numeric)',
                                      (stream, holder, 60)).fetchone()[0]
        with ThreadPoolExecutor(max_workers=2) as pool:
            for round_number in range(ROUNDS):
                stream = f'race-{round_number}'
                barrier = threading.Barrier(2)
                one = pool.submit(acquire, first, stream, uuid.uuid4(), barrier)
                two = pool.submit(acquire, second, stream, uuid.uuid4(), barrier)
                outcomes = (one.result(timeout=30), two.result(timeout=30))
                grants = admin.execute('SELECT count(*) FROM own.grants WHERE stream_id=%s',
                                       (stream,)).fetchone()[0]
                winners = sum(value is not None for value in outcomes)
                yield {'round': round_number, 'winners': winners, 'grants': grants}
                assert winners == grants == 1, (round_number, outcomes, grants)


def main():
    version = prepare_database()
    rows = []
    with psycopg.connect(dsn(), autocommit=True) as admin:
        for condition in CONDITIONS:
            for trial in range(TRIALS):
                rows.append(interleaving(admin, condition, trial))
        races = list(reacquisition_races(admin))
    OUT.mkdir(parents=True, exist_ok=True)
    write_csv(OUT / 'pg_concurrency_trials.csv', rows, list(rows[0]))
    write_csv(OUT / 'pg_acquisition_races.csv', races, list(races[0]))
    summary = []
    for condition in CONDITIONS:
        cells = [r for r in rows if r['condition'] == condition]
        summary.append({'condition': condition, 'runs': len(cells),
                        'former_attempts': sum(r['former_attempts'] for r in cells),
                        'former_accepted': sum(r['former_accepted'] for r in cells),
                        'late_accept': sum(r['late_accept'] for r in cells),
                        'epoch_regression': sum(r['epoch_regression'] for r in cells)})
    write_csv(OUT / 'pg_concurrency_summary.csv', summary, list(summary[0]))
    print(f'PostgreSQL {version}: {len(rows)} threaded interleavings and '
          f'{len(races)} acquisition races; '
          f'{sum(r["winners"] for r in races)} rounds had one winner')
    for row in summary:
        print(row)


if __name__ == '__main__':
    main()
