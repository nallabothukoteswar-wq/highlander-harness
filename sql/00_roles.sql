-- Roles and schemas for Highlander harness
-- This file must be run first

-- Drop roles if they exist (for clean setup)
DROP ROLE IF EXISTS rsink_rw;
DROP ROLE IF EXISTS worker_rw;

-- Create roles
CREATE ROLE worker_rw WITH LOGIN PASSWORD 'worker_password';
CREATE ROLE rsink_rw WITH LOGIN PASSWORD 'rsink_password';

-- Create schemas
CREATE SCHEMA IF NOT EXISTS own;
CREATE SCHEMA IF NOT EXISTS src;
CREATE SCHEMA IF NOT EXISTS sink;
CREATE SCHEMA IF NOT EXISTS rsink;
CREATE SCHEMA IF NOT EXISTS ctl;

-- Grant schema usage
GRANT USAGE ON SCHEMA own TO worker_rw;
GRANT USAGE ON SCHEMA src TO worker_rw;
GRANT USAGE ON SCHEMA sink TO worker_rw;
GRANT USAGE ON SCHEMA ctl TO worker_rw;
GRANT USAGE ON SCHEMA rsink TO rsink_rw;
GRANT USAGE ON SCHEMA ctl TO rsink_rw;

-- Note: rsink_rw must NOT have privileges on own schema
-- This will be enforced by tests

-- Set worker timeouts for defence in depth
ALTER ROLE worker_rw SET statement_timeout = '5s';
ALTER ROLE worker_rw SET lock_timeout = '1s';
ALTER ROLE worker_rw SET idle_in_transaction_session_timeout = '2s';

ALTER ROLE rsink_rw SET statement_timeout = '5s';
ALTER ROLE rsink_rw SET lock_timeout = '1s';
ALTER ROLE rsink_rw SET idle_in_transaction_session_timeout = '2s';
