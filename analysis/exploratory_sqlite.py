"""Controlled, serialized SQLite interleaving study; not the PostgreSQL/kind campaign.

Run: python3 -m analysis.exploratory_sqlite --output paper/supplementary
Uses seeded event order and actual transactional SQL writes. Raw trial CSVs are retained.
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import sqlite3
import time
from collections import Counter
from pathlib import Path

CONDITIONS = ('C1', 'C1u', 'C1v', 'C2', 'C2f', 'C3', 'C3r', 'C4')
LEASED = frozenset(('C2', 'C2f', 'C3', 'C3r', 'C4'))
UNIQUE = frozenset(('C1u', 'C3', 'C3r', 'C4'))
FENCED = frozenset(('C2f', 'C3', 'C4'))
KEYS = 100
TRIALS = 30
SEED = 2026
SUCCESSOR_FIRST_PROBABILITY = .7
LOST_ACK_PROBABILITY = .05
FIRST_WRITE_DELAY_S = 2
RETRY_DELAY_S = .05


def database():
    db = sqlite3.connect(':memory:', isolation_level=None)
    db.execute('CREATE TABLE state (key TEXT PRIMARY KEY, version INTEGER, max_epoch INTEGER)')
    db.execute('CREATE TABLE ops (op_key TEXT PRIMARY KEY, response TEXT)')
    db.execute('CREATE TABLE remote_feed (feed TEXT PRIMARY KEY, max_epoch INTEGER)')
    return db


def submit(db, condition, key, op_key, version, epoch, holder, current_epoch,
           first_write_after_grant=False):
    """Commit one effect with a ledger and its pre-write state in one transaction."""
    db.execute('BEGIN IMMEDIATE')
    try:
        pre = db.execute('SELECT version, max_epoch FROM state WHERE key=?', (key,)).fetchone()
        pre_version, pre_epoch = pre if pre else (None, None)
        highest_applied_epoch = db.execute('SELECT MAX(max_epoch) FROM state').fetchone()[0]
        remote_epoch = db.execute('SELECT max_epoch FROM remote_feed WHERE feed=?',
                                  ('feed',)).fetchone()
        prior_response = db.execute('SELECT response FROM ops WHERE op_key=?', (op_key,)).fetchone()
        response_text = f'ok:{key}:{version}'
        if condition in FENCED and (epoch != current_epoch or holder != 'current'):
            outcome = 'rejected_fence'
        elif condition == 'C3r' and remote_epoch is not None and epoch < remote_epoch[0]:
            outcome = 'rejected_remote_epoch'
        elif condition == 'C1v' and pre_version is not None and version <= pre_version:
            outcome = 'rejected_version'
        elif condition in UNIQUE and prior_response:
            outcome = 'replayed' if condition == 'C4' else 'rejected_duplicate'
            if outcome == 'replayed':
                response_text = prior_response[0]
        else:
            outcome = 'accepted'
            # For the remote condition the local grant is not visible at this sink.
            max_epoch = max(epoch, pre_epoch or 0)
            db.execute('INSERT INTO state VALUES (?, ?, ?) ON CONFLICT(key) DO UPDATE SET '
                       'version=excluded.version, max_epoch=excluded.max_epoch',
                       (key, version, max_epoch))
            if condition == 'C3r':
                db.execute('INSERT INTO remote_feed VALUES (?, ?) ON CONFLICT(feed) DO UPDATE SET '
                           'max_epoch=MAX(remote_feed.max_epoch, excluded.max_epoch)',
                           ('feed', epoch))
            if condition in UNIQUE:
                db.execute('INSERT INTO ops VALUES (?, ?)', (op_key, response_text))
        db.execute('COMMIT')
    except Exception:
        db.execute('ROLLBACK')
        raise
    accepted = outcome == 'accepted'
    return dict(outcome=outcome, response=response_text if accepted or outcome == 'replayed' else None,
                version_regression=int(accepted and pre_version is not None
                and version < pre_version), epoch_regression=int(accepted and
                condition in LEASED and highest_applied_epoch is not None
                and epoch < highest_applied_epoch),
                late_accept=int(accepted and condition == 'C3r' and
                first_write_after_grant and epoch < current_epoch))


def one_ordered(condition, trial):
    rng = random.Random(SEED + trial)
    db = database()
    totals = Counter()
    # All v1 publications precede the grant; the feed fence spans every item.
    for i in range(KEYS):
        key = f'feed-{i}'
        submit(db, condition, key, f'{key}:initial', 1, 1, 'current', 1)
    keys = list(range(KEYS))
    rng.shuffle(keys)
    for i in keys:
        key = f'feed-{i}'
        successor_first = rng.random() < SUCCESSOR_FIRST_PROBABILITY
        if successor_first:
            submit(db, condition, key, f'{key}:successor', 3, 2, 'current', 2)
        old = submit(db, condition, key, f'{key}:delayed', 2, 1, 'former', 2,
                     first_write_after_grant=not successor_first)
        for field in ('version_regression', 'epoch_regression', 'late_accept'):
            totals[field] += old[field]
        totals[old['outcome']] += 1
        if not successor_first:
            submit(db, condition, key, f'{key}:successor', 3, 2, 'current', 2)
    db.close()
    return dict(series='ordered_pause', condition=condition, trial=trial,
                seed=SEED + trial,
                items=KEYS, at_risk_attempts=KEYS, **totals)


def one_duplicate(condition, trial):
    db = database()
    totals = Counter()
    for i in range(KEYS):
        key = f'op-{i}'
        submit(db, condition, key, key, 1, 1, 'current', 1)
        again = submit(db, condition, key, key, 1, 1, 'former', 2)
        totals[again['outcome']] += 1
        totals['accepted_duplicates'] += again['outcome'] == 'accepted'
    db.close()
    return dict(series='duplicate_pause', condition=condition, trial=trial,
                seed=SEED + trial,
                items=KEYS, at_risk_attempts=KEYS, **totals)


def one_replay(condition, trial):
    rng = random.Random(SEED + 100000 + trial)
    db = database()
    totals = Counter()
    for i in range(KEYS):
        key = f'retry-{i}'
        original = submit(db, condition, key, key, 1, 1, 'current', 1)
        assert original['outcome'] == 'accepted'
        if rng.random() >= LOST_ACK_PROBABILITY:
            continue
        totals['lost_ack'] += 1
        time.sleep(RETRY_DELAY_S)
        retry = submit(db, condition, key, key, 1, 1, 'current', 1)
        category = {'accepted': 'duplicate_accepted',
                    'rejected_duplicate': 'unresolved_ambiguous',
                    'replayed': ('replay_stable' if retry['response'] == original['response']
                                 else 'replay_mismatch')}[retry['outcome']]
        totals[category] += 1
    db.close()
    return dict(series='lost_ack', condition=condition, trial=trial,
                seed=SEED + 100000 + trial,
                items=KEYS, at_risk_attempts=0, **totals)


def one_after_grant(condition, trial, delay_s):
    db = database()
    totals = Counter()
    for i in range(KEYS):
        key = f'feed-{i}'
        submit(db, condition, key, f'{key}:initial', 1, 1, 'current', 1)
    # The whole captured batch resumes at t=d; the successor's first remote
    # write occurs at t=2 s. Event-time ordering, not wall-clock benchmarking.
    old_first = delay_s < FIRST_WRITE_DELAY_S

    def release_old_batch():
        for i in range(KEYS):
            key = f'feed-{i}'
            old = submit(db, condition, key, f'{key}:delayed', 2, 1, 'former', 2,
                         first_write_after_grant=old_first)
            totals['late_accept'] += old['late_accept']
            totals['version_regression'] += old['version_regression']
            totals[old['outcome']] += 1

    def successor_publishes():
        for i in range(KEYS):
            key = f'feed-{i}'
            submit(db, condition, key, f'{key}:successor', 3, 2, 'current', 2)

    if old_first:
        release_old_batch()
        successor_publishes()
    else:
        successor_publishes()
        release_old_batch()
    db.close()
    return dict(series='after_grant', condition=condition, trial=trial,
                seed=SEED + trial, delay_s=delay_s, items=KEYS,
                at_risk_attempts=KEYS, **totals)


def write_rows(path, rows, fields):
    with path.open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields, lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=Path('paper/supplementary'))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    rows = []
    for condition in CONDITIONS:
        for trial in range(TRIALS):
            rows.append(one_ordered(condition, trial))
        # The duplicate pause is deterministic under the stated schedule.
        if condition != 'C1v':
            rows.append(one_duplicate(condition, 0))
    for condition in ('C2f', 'C3', 'C4'):
        for trial in range(TRIALS):
            rows.append(one_replay(condition, trial))
    for condition in ('C3', 'C3r'):
        for delay_s in (0, 1, 5):
            rows.append(one_after_grant(condition, 0, delay_s))
    fields = ['series', 'condition', 'trial', 'seed', 'delay_s', 'items', 'at_risk_attempts',
              'accepted', 'rejected_fence', 'rejected_remote_epoch', 'rejected_version',
              'rejected_duplicate', 'replayed', 'accepted_duplicates',
              'version_regression', 'epoch_regression', 'late_accept', 'lost_ack',
              'duplicate_accepted', 'unresolved_ambiguous', 'replay_stable', 'replay_mismatch']
    write_rows(args.output / 'sqlite_trials.csv', rows, fields)
    (args.output / 'experiment_config.json').write_text(json.dumps({
        'seed': SEED, 'keys_per_run': KEYS, 'ordered_runs_per_condition': TRIALS,
        'duplicate_runs_per_condition': 1, 'replay_runs_per_condition': TRIALS,
        'after_grant_runs_per_cell': 1,
        'successor_first_probability': SUCCESSOR_FIRST_PROBABILITY,
        'lost_ack_probability': LOST_ACK_PROBABILITY,
        'first_write_delay_s': FIRST_WRITE_DELAY_S,
        'retry_delay_s': RETRY_DELAY_S, 'resume_delays_s': [0, 1, 5],
        'sink': 'SQLite scheduled rule model; no PostgreSQL or Kubernetes execution'
    }, indent=2) + '\n')
    summary = []
    for series in ('ordered_pause', 'duplicate_pause', 'lost_ack', 'after_grant'):
        for condition in CONDITIONS:
            for delay_s in ((0, 1, 5) if series == 'after_grant' else (None,)):
                group = [r for r in rows if r['series'] == series and r['condition'] == condition
                         and (delay_s is None or r.get('delay_s') == delay_s)]
                if not group:
                    continue
                fields_for_series = {'ordered_pause': (('version_regression', 'epoch_regression', 'late_accept')
                                   if condition in ('C3', 'C3r') else ('version_regression', 'epoch_regression')),
                                 'duplicate_pause': ('accepted_duplicates',),
                                 'lost_ack': ('lost_ack', 'duplicate_accepted',
                                              'unresolved_ambiguous', 'replay_stable', 'replay_mismatch'),
                                  'after_grant': ('late_accept',)}[series]
                for metric in fields_for_series:
                    if metric == 'epoch_regression' and condition not in LEASED:
                        continue
                    count = sum(r.get(metric, 0) for r in group)
                    summary.append(dict(series=series, condition=condition,
                                        delay_s='' if delay_s is None else delay_s, metric=metric,
                                        scheduled_runs=len(group),
                                        items=sum(r['items'] for r in group), events=count,
                                        at_risk_attempts=sum(r['at_risk_attempts'] for r in group)))
    write_rows(args.output / 'sqlite_summary.csv', summary, list(summary[0]))
    print('Wrote', len(rows), 'raw trial rows and', len(summary), 'summary rows to', args.output)


if __name__ == '__main__':
    main()
