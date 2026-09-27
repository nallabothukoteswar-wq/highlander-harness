"""Pytest configuration for Highlander tests."""

import pytest
import psycopg
import subprocess
import os


def test_dsn(database='highlander_test'):
    """Use DATABASE_URL when present, otherwise the repository's DB_* settings."""
    from psycopg.conninfo import conninfo_to_dict, make_conninfo
    if os.getenv('DATABASE_URL'):
        params = conninfo_to_dict(os.environ['DATABASE_URL'])
        params['dbname'] = database
        return make_conninfo(**params)
    return make_conninfo(host=os.getenv('DB_HOST', 'localhost'),
                         port=os.getenv('DB_PORT', '5432'), dbname=database,
                         user=os.getenv('DB_USER', 'postgres'),
                         password=os.getenv('DB_PASSWORD', 'testpassword'))


@pytest.fixture(scope="session")
def setup_test_database():
    """Set up the test database and run schema migrations."""
    db_name = "highlander_test"

    # Connect to postgres database to create test database
    conn = psycopg.connect(test_dsn('postgres'), autocommit=True)

    # Drop test database if it exists
    conn.execute(f"DROP DATABASE IF EXISTS {db_name}")

    # Create test database
    conn.execute(f"CREATE DATABASE {db_name}")

    conn.close()

    # Connect to test database and run schema migrations
    conn = psycopg.connect(test_dsn(db_name), autocommit=True)

    # Run SQL schema files in order
    sql_dir = os.path.join(os.path.dirname(__file__), '..', 'sql')
    sql_files = [
        '00_roles.sql',
        '01_schemas.sql',
        '02_ownership.sql',
        '03_queue.sql',
        '04_sinks_colocated.sql',
        '05_sink_remote.sql',
        '06_control.sql',
        '07_views.sql',
        '08_sink_functions.sql'
    ]

    for sql_file in sql_files:
        filepath = os.path.join(sql_dir, sql_file)
        with open(filepath, 'r') as f:
            sql_content = f.read()
            conn.execute(sql_content)

    conn.close()

    yield

    # Cleanup: drop test database
    conn = psycopg.connect(test_dsn('postgres'), autocommit=True)
    conn.execute(f"DROP DATABASE IF EXISTS {db_name}")
    conn.close()
