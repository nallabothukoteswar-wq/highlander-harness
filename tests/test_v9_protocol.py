"""Regression cases for the PostgreSQL implementation (requires PostgreSQL 16)."""
import uuid

import psycopg
import pytest

from runner.trials import TrialRunner


@pytest.fixture
def db(setup_test_database):
    from tests.conftest import test_dsn
    with psycopg.connect(test_dsn(), autocommit=True) as conn:
        conn.execute('TRUNCATE own.grants, own.renewals, own.owner CASCADE')
        conn.execute('TRUNCATE sink.state, sink.effects, sink.responses, sink.attempt_log, sink.max_epoch CASCADE')
        conn.execute('TRUNCATE rsink.fence, rsink.state, rsink.effects, rsink.attempt_log CASCADE')
        yield conn


def submit(conn, condition, key, version, epoch, holder, op=None, trial='v9'):
    name = {'C1': 'sink.sink_plain', 'C2': 'sink.sink_plain',
            'C1u': 'sink.sink_unique', 'C1v': 'sink.sink_version',
            'C2f': 'sink.sink_fenced', 'C3': 'sink.sink_fenced_unique',
            'C4': 'sink.sink_fenced_unique_cached', 'C3r': 'rsink.sink_remote'}[condition]
    return conn.execute(f'SELECT {name}(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                        (trial, condition, 'worker', holder, 'S1', epoch,
                         op or f'{key}:{version}', key, key, version, 0, True)).fetchone()[0]


def test_d1_acquire_after_empty_reset(db):
    holder = uuid.uuid4()
    assert db.execute('SELECT own.acquire(%s,%s,%s)', ('S1', holder, 10)).fetchone()[0] == 1
    assert db.execute('SELECT count(*) FROM own.grants').fetchone()[0] == 1


@pytest.mark.parametrize('condition', ['C1', 'C1u', 'C1v', 'C2', 'C2f', 'C3', 'C3r', 'C4'])
def test_d2_reset_twice(db, tmp_path, condition):
    class Platform:
        def get_db_connection(self):
            from tests.conftest import test_dsn
            return psycopg.connect(test_dsn(), autocommit=True)
    runner = TrialRunner(Platform(), str(tmp_path), False, 1)
    runner._reset_trial_state('v9', {'condition': condition})
    runner._reset_trial_state('v9', {'condition': condition})


@pytest.mark.parametrize('condition', ['C1', 'C1u', 'C2'])
def test_d4_version_regression_then_recovery(db, condition):
    holder = uuid.uuid4()
    for version in (3, 2):
        assert submit(db, condition, 'k', version, 1 if condition == 'C2' else None, holder)['outcome'] == 'accepted'
    assert db.execute('SELECT version FROM sink.state WHERE target_key=%s', ('k',)).fetchone()[0] == 2
    assert db.execute('SELECT regression_count FROM sink.version_regressions WHERE condition=%s', (condition,)).fetchone()[0] == 1


def test_d5_feed_wide_epoch_prestate(db):
    holder = uuid.uuid4()
    submit(db, 'C2', 'key-a', 1, 2, holder)
    submit(db, 'C2', 'key-b', 1, 1, holder)
    assert db.execute("SELECT pre_max_epoch FROM sink.attempt_log WHERE target_key='key-b'").fetchone()[0] == 2
    assert db.execute("SELECT regression_count FROM sink.epoch_regressions WHERE condition='C2'").fetchone()[0] == 1


def test_d6_cached_response_identity(db):
    holder = uuid.uuid4()
    epoch = db.execute('SELECT own.acquire(%s,%s,%s)', ('S1', holder, 10)).fetchone()[0]
    first = submit(db, 'C4', 'k', 1, epoch, holder, 'replay')
    second = submit(db, 'C4', 'k', 1, epoch, holder, 'replay')
    assert first['outcome'] == 'accepted'
    assert second['outcome'] == 'replayed'
    assert second['response'] == first['response']


def test_d7_remote_invoker_and_no_ownership_visibility(db):
    db.execute('SET ROLE rsink_rw')
    try:
        assert submit(db, 'C3r', 'k', 1, 1, uuid.uuid4())['outcome'] == 'accepted'
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            db.execute('SELECT * FROM own.owner').fetchall()
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            db.execute('SELECT * FROM rsink.late_accepts').fetchall()
    finally:
        db.execute('RESET ROLE')


def test_d8_remote_metric_views(db):
    for name in ('version_regressions', 'epoch_regressions'):
        assert db.execute('SELECT to_regclass(%s)', (f'rsink.{name}',)).fetchone()[0] is not None
    assert db.execute("SELECT to_regclass('sink.stale_overwrites')").fetchone()[0] is None
