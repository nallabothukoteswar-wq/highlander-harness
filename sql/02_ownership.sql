-- Ownership tables and functions
-- Implements the owner-row lease mechanism

-- Owner table: one row per ownership key (stream_id)
CREATE TABLE IF NOT EXISTS own.owner (
    stream_id  text PRIMARY KEY,
    holder     uuid,
    epoch      bigint      NOT NULL DEFAULT 0,
    expires_at timestamptz NOT NULL DEFAULT '-infinity',
    granted_at timestamptz
);

-- Grants log: records every successful ownership acquisition
CREATE TABLE IF NOT EXISTS own.grants (
    stream_id  text,
    epoch      bigint,
    holder     uuid,
    granted_at timestamptz,
    PRIMARY KEY (stream_id, epoch)
);

-- Renewals log: records every successful lease renewal
CREATE TABLE IF NOT EXISTS own.renewals (
    stream_id  text,
    epoch      bigint,
    holder     uuid,
    renewed_at timestamptz,
    expires_at timestamptz,
    PRIMARY KEY (stream_id, epoch, renewed_at)
);

-- Grant privileges on ownership tables to worker_rw
GRANT SELECT, INSERT, UPDATE ON own.owner TO worker_rw;
GRANT SELECT, INSERT ON own.grants TO worker_rw;
GRANT SELECT, INSERT ON own.renewals TO worker_rw;

-- IMPORTANT: rsink_rw must NOT have any privileges on own schema
-- This is enforced by tests

-- Ownership functions

-- Acquire ownership: succeeds only if row is free or expired
-- Returns the new epoch if successful, NULL otherwise
CREATE OR REPLACE FUNCTION own.acquire(
    p_stream_id text,
    p_holder uuid,
    p_lease_secs numeric
) RETURNS bigint AS $$
DECLARE
    v_epoch bigint;
BEGIN
    WITH g AS (
        INSERT INTO own.owner (stream_id, holder, epoch, granted_at, expires_at)
        VALUES (p_stream_id, p_holder, 1, clock_timestamp(),
                clock_timestamp() + make_interval(secs => p_lease_secs))
        ON CONFLICT (stream_id) DO UPDATE
        SET holder = EXCLUDED.holder,
            epoch = own.owner.epoch + 1,
            granted_at = clock_timestamp(),
            expires_at = clock_timestamp() + make_interval(secs => p_lease_secs)
        WHERE own.owner.expires_at <= clock_timestamp()
        RETURNING stream_id, epoch, holder, granted_at
    )
    INSERT INTO own.grants (stream_id, epoch, holder, granted_at)
    SELECT stream_id, epoch, holder, granted_at FROM g
    RETURNING epoch INTO v_epoch;

    RETURN v_epoch;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, own;

-- Renew ownership: succeeds only for current holder with correct epoch and unexpired lease
-- Returns the new expires_at if successful, NULL otherwise
CREATE OR REPLACE FUNCTION own.renew(
    p_stream_id text,
    p_holder uuid,
    p_epoch bigint,
    p_lease_secs numeric
) RETURNS timestamptz AS $$
DECLARE
    v_expires_at timestamptz;
BEGIN
    WITH r AS (
        UPDATE own.owner
        SET expires_at = clock_timestamp() + make_interval(secs => p_lease_secs)
        WHERE stream_id = p_stream_id
          AND holder = p_holder
          AND epoch = p_epoch
          AND expires_at > clock_timestamp()
        RETURNING stream_id, epoch, holder, expires_at
    )
    INSERT INTO own.renewals (stream_id, epoch, holder, renewed_at, expires_at)
    SELECT stream_id, epoch, holder, clock_timestamp(), expires_at FROM r
    RETURNING expires_at INTO v_expires_at;

    RETURN v_expires_at;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, own;

-- Grant execute on functions to worker_rw
GRANT EXECUTE ON FUNCTION own.acquire(text, uuid, numeric) TO worker_rw;
GRANT EXECUTE ON FUNCTION own.renew(text, uuid, bigint, numeric) TO worker_rw;
