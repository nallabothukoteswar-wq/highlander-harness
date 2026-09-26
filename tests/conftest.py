"""Pytest configuration for Highlander tests."""

import pytest
import psycopg
import subprocess
import os


@pytest.fixture(scope="session")
def setup_test_database():
    """Set up the test database and run schema migrations."""
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = int(os.getenv("DB_PORT", "5432"))
    db_name = "highlander_test"
    db_user = os.getenv("DB_USER", "postgres")
    db_password = os.getenv("DB_PASSWORD", "testpassword")

    # Connect to postgres database to create test database
    conn = psycopg.connect(
        host=db_host,
        port=db_port,
        dbname="postgres",
        user=db_user,
        password=db_password,
        autocommit=True
    )

    # Drop test database if it exists
    conn.execute(f"DROP DATABASE IF EXISTS {db_name}")

    # Create test database
    conn.execute(f"CREATE DATABASE {db_name}")

    conn.close()

    # Connect to test database and run schema migrations
    conn = psycopg.connect(
        host=db_host,
        port=db_port,
        dbname=db_name,
        user=db_user,
        password=db_password,
        autocommit=True
    )

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
    conn = psycopg.connect(
        host=db_host,
        port=db_port,
        dbname="postgres",
        user=db_user,
        password=db_password,
        autocommit=True
    )
    conn.execute(f"DROP DATABASE IF EXISTS {db_name}")
    conn.close()
