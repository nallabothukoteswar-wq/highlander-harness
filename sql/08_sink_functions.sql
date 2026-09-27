-- Sink functions for all conditions
-- Each function is a single autocommit call that logs exactly one attempt_log row

-- Lock the feed-wide metric row, return its pre-write value, then advance it.
-- It records applied authority and is independent of the ownership fence.
CREATE OR REPLACE FUNCTION sink.advance_epoch(p_trial_id text, p_stream_id text,
                                              p_epoch bigint) RETURNS bigint AS $$
DECLARE
    v_previous bigint;
BEGIN
    IF p_epoch IS NULL THEN
        RETURN NULL;
    END IF;
    INSERT INTO sink.max_epoch (trial_id, stream_id, max_epoch)
    VALUES (p_trial_id, p_stream_id, 0) ON CONFLICT DO NOTHING;
    SELECT max_epoch INTO v_previous FROM sink.max_epoch
    WHERE trial_id = p_trial_id AND stream_id = p_stream_id FOR UPDATE;
    UPDATE sink.max_epoch SET max_epoch = GREATEST(max_epoch, p_epoch)
    WHERE trial_id = p_trial_id AND stream_id = p_stream_id;
    RETURN v_previous;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, sink;

-- Plain sink (C1, C2): apply unconditionally
CREATE OR REPLACE FUNCTION sink.sink_plain(
    p_trial_id text,
    p_condition text,
    p_worker_id text,
    p_incarnation uuid,
    p_stream_id text,
    p_epoch bigint,
    p_op_key text,
    p_business_key text,
    p_target_key text,
    p_source_version bigint,
    p_prep_cpu_ns bigint,
    p_at_risk boolean DEFAULT false
) RETURNS jsonb AS $$
DECLARE
    v_pre_version bigint;
    v_pre_max_epoch bigint;
    v_committed_at timestamptz;
BEGIN
    -- Lock state row and read pre_version
    SELECT version INTO v_pre_version
    FROM sink.state
    WHERE trial_id = p_trial_id AND target_key = p_target_key
    FOR UPDATE;

    IF v_pre_version IS NULL THEN
        v_pre_version := 0;
        INSERT INTO sink.state (trial_id, target_key, version)
        VALUES (p_trial_id, p_target_key, 0);
    END IF;

    -- Apply effect unconditionally
    INSERT INTO sink.effects (trial_id, business_key, op_key, version, committed_at)
    VALUES (p_trial_id, p_business_key, p_op_key, p_source_version, clock_timestamp());

    UPDATE sink.state SET version = p_source_version
    WHERE trial_id = p_trial_id AND target_key = p_target_key;
    v_pre_max_epoch := sink.advance_epoch(p_trial_id, p_stream_id, p_epoch);

    v_committed_at := clock_timestamp();

    -- Log attempt
    INSERT INTO sink.attempt_log (
        trial_id, condition, worker_id, incarnation, stream_id, epoch,
        op_key, business_key, target_key, source_version, prep_cpu_ns, at_risk,
        outcome, reason, pre_version, pre_max_epoch, committed_at
    ) VALUES (
        p_trial_id, p_condition, p_worker_id, p_incarnation, p_stream_id, p_epoch,
        p_op_key, p_business_key, p_target_key, p_source_version, p_prep_cpu_ns, p_at_risk,
        'accepted', NULL, v_pre_version, v_pre_max_epoch, v_committed_at
    );

    RETURN jsonb_build_object('outcome', 'accepted', 'committed_at', v_committed_at);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, sink, own;

-- Unique sink (C1u): plain with UNIQUE(op_key) constraint
CREATE OR REPLACE FUNCTION sink.sink_unique(
    p_trial_id text,
    p_condition text,
    p_worker_id text,
    p_incarnation uuid,
    p_stream_id text,
    p_epoch bigint,
    p_op_key text,
    p_business_key text,
    p_target_key text,
    p_source_version bigint,
    p_prep_cpu_ns bigint,
    p_at_risk boolean DEFAULT false
) RETURNS jsonb AS $$
DECLARE
    v_pre_version bigint;
    v_pre_max_epoch bigint;
    v_committed_at timestamptz;
    v_outcome text;
    v_reason text;
BEGIN
    -- Lock state row and read pre_version
    SELECT version INTO v_pre_version
    FROM sink.state
    WHERE trial_id = p_trial_id AND target_key = p_target_key
    FOR UPDATE;

    IF v_pre_version IS NULL THEN
        v_pre_version := 0;
        INSERT INTO sink.state (trial_id, target_key, version)
        VALUES (p_trial_id, p_target_key, 0);
    END IF;

    -- Reserve the operation key atomically; plain conditions do not use this ledger.
    BEGIN
        INSERT INTO sink.responses (trial_id, op_key, response)
        VALUES (p_trial_id, p_op_key, jsonb_build_object('accepted', true))
        ON CONFLICT (trial_id, op_key) DO NOTHING;

        IF NOT FOUND THEN
            v_outcome := 'rejected';
            v_reason := 'dup_key';
            v_committed_at := clock_timestamp();
        ELSE
            INSERT INTO sink.effects (trial_id, business_key, op_key, version)
            VALUES (p_trial_id, p_business_key, p_op_key, p_source_version);
            v_outcome := 'accepted';
            v_reason := NULL;
            v_committed_at := clock_timestamp();
            UPDATE sink.state SET version = p_source_version
            WHERE trial_id = p_trial_id AND target_key = p_target_key;
            v_pre_max_epoch := sink.advance_epoch(p_trial_id, p_stream_id, p_epoch);
        END IF;
    EXCEPTION WHEN unique_violation THEN
        v_outcome := 'rejected';
        v_reason := 'dup_key';
        v_committed_at := clock_timestamp();
    END;

    -- Log attempt
    INSERT INTO sink.attempt_log (
        trial_id, condition, worker_id, incarnation, stream_id, epoch,
        op_key, business_key, target_key, source_version, prep_cpu_ns, at_risk,
        outcome, reason, pre_version, pre_max_epoch, committed_at
    ) VALUES (
        p_trial_id, p_condition, p_worker_id, p_incarnation, p_stream_id, p_epoch,
        p_op_key, p_business_key, p_target_key, p_source_version, p_prep_cpu_ns, p_at_risk,
        v_outcome, v_reason, v_pre_version, v_pre_max_epoch, v_committed_at
    );

    RETURN jsonb_build_object('outcome', v_outcome, 'reason', v_reason, 'committed_at', v_committed_at);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, sink, own;

-- Version sink (C1v, ordered only): reject if version not newer
CREATE OR REPLACE FUNCTION sink.sink_version(
    p_trial_id text,
    p_condition text,
    p_worker_id text,
    p_incarnation uuid,
    p_stream_id text,
    p_epoch bigint,
    p_op_key text,
    p_business_key text,
    p_target_key text,
    p_source_version bigint,
    p_prep_cpu_ns bigint,
    p_at_risk boolean DEFAULT false
) RETURNS jsonb AS $$
DECLARE
    v_pre_version bigint;
    v_updated integer;
    v_committed_at timestamptz;
    v_outcome text;
    v_reason text;
BEGIN
    -- Lock state row and read pre_version
    SELECT version INTO v_pre_version
    FROM sink.state
    WHERE trial_id = p_trial_id AND target_key = p_target_key
    FOR UPDATE;

    IF v_pre_version IS NULL THEN
        v_pre_version := 0;
        INSERT INTO sink.state (trial_id, target_key, version)
        VALUES (p_trial_id, p_target_key, 0);
    END IF;

    -- Update only if version is newer
    UPDATE sink.state
    SET version = p_source_version
    WHERE trial_id = p_trial_id
      AND target_key = p_target_key
      AND version < p_source_version;

    GET DIAGNOSTICS v_updated = ROW_COUNT;

    IF v_updated = 0 THEN
        v_outcome := 'rejected';
        v_reason := 'version_not_newer';
    ELSE
        v_outcome := 'accepted';
        v_reason := NULL;
    END IF;

    v_committed_at := clock_timestamp();

    -- Log attempt
    INSERT INTO sink.attempt_log (
        trial_id, condition, worker_id, incarnation, stream_id, epoch,
        op_key, business_key, target_key, source_version, prep_cpu_ns, at_risk,
        outcome, reason, pre_version, pre_max_epoch, committed_at
    ) VALUES (
        p_trial_id, p_condition, p_worker_id, p_incarnation, p_stream_id, p_epoch,
        p_op_key, p_business_key, p_target_key, p_source_version, p_prep_cpu_ns, p_at_risk,
        v_outcome, v_reason, v_pre_version, NULL, v_committed_at
    );

    RETURN jsonb_build_object('outcome', v_outcome, 'reason', v_reason, 'committed_at', v_committed_at);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, sink, own;

-- Fenced sink (C2f): check ownership fence before applying
CREATE OR REPLACE FUNCTION sink.sink_fenced(
    p_trial_id text,
    p_condition text,
    p_worker_id text,
    p_incarnation uuid,
    p_stream_id text,
    p_epoch bigint,
    p_op_key text,
    p_business_key text,
    p_target_key text,
    p_source_version bigint,
    p_prep_cpu_ns bigint,
    p_at_risk boolean DEFAULT false
) RETURNS jsonb AS $$
DECLARE
    v_holder uuid;
    v_owner_epoch bigint;
    v_expires_at timestamptz;
    v_pre_version bigint;
    v_pre_max_epoch bigint;
    v_committed_at timestamptz;
    v_outcome text;
    v_reason text;
BEGIN
    -- Lock owner row and check fence
    SELECT holder, epoch, expires_at INTO v_holder, v_owner_epoch, v_expires_at
    FROM own.owner
    WHERE stream_id = p_stream_id
    FOR UPDATE;

    -- Check fence conditions
    IF v_holder IS NULL OR v_holder <> p_incarnation::uuid THEN
        v_outcome := 'rejected';
        v_reason := 'not_holder';
        v_committed_at := clock_timestamp();
    ELSIF v_owner_epoch <> p_epoch THEN
        v_outcome := 'rejected';
        v_reason := 'stale_epoch';
        v_committed_at := clock_timestamp();
    ELSIF v_expires_at <= clock_timestamp() THEN
        v_outcome := 'rejected';
        v_reason := 'expired';
        v_committed_at := clock_timestamp();
    ELSE
        -- Fence passed, apply effect
        SELECT version INTO v_pre_version
        FROM sink.state
        WHERE trial_id = p_trial_id AND target_key = p_target_key
        FOR UPDATE;

        IF v_pre_version IS NULL THEN
            v_pre_version := 0;
            INSERT INTO sink.state (trial_id, target_key, version)
            VALUES (p_trial_id, p_target_key, 0);
        END IF;

        INSERT INTO sink.effects (trial_id, business_key, op_key, version, committed_at)
        VALUES (p_trial_id, p_business_key, p_op_key, p_source_version, clock_timestamp());

        UPDATE sink.state SET version = p_source_version
        WHERE trial_id = p_trial_id AND target_key = p_target_key;
        v_pre_max_epoch := sink.advance_epoch(p_trial_id, p_stream_id, p_epoch);

        v_outcome := 'accepted';
        v_reason := NULL;
        v_committed_at := clock_timestamp();
    END IF;

    -- Log attempt
    INSERT INTO sink.attempt_log (
        trial_id, condition, worker_id, incarnation, stream_id, epoch,
        op_key, business_key, target_key, source_version, prep_cpu_ns, at_risk,
        outcome, reason, pre_version, pre_max_epoch, committed_at
    ) VALUES (
        p_trial_id, p_condition, p_worker_id, p_incarnation, p_stream_id, p_epoch,
        p_op_key, p_business_key, p_target_key, p_source_version, p_prep_cpu_ns, p_at_risk,
        v_outcome, v_reason, v_pre_version, v_pre_max_epoch, v_committed_at
    );

    RETURN jsonb_build_object('outcome', v_outcome, 'reason', v_reason, 'committed_at', v_committed_at);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, sink, own;

-- Fenced unique sink (C3): fence with unique constraint
CREATE OR REPLACE FUNCTION sink.sink_fenced_unique(
    p_trial_id text,
    p_condition text,
    p_worker_id text,
    p_incarnation uuid,
    p_stream_id text,
    p_epoch bigint,
    p_op_key text,
    p_business_key text,
    p_target_key text,
    p_source_version bigint,
    p_prep_cpu_ns bigint,
    p_at_risk boolean DEFAULT false
) RETURNS jsonb AS $$
DECLARE
    v_holder uuid;
    v_owner_epoch bigint;
    v_expires_at timestamptz;
    v_pre_version bigint;
    v_pre_max_epoch bigint;
    v_committed_at timestamptz;
    v_outcome text;
    v_reason text;
BEGIN
    -- Lock owner row and check fence
    SELECT holder, epoch, expires_at INTO v_holder, v_owner_epoch, v_expires_at
    FROM own.owner
    WHERE stream_id = p_stream_id
    FOR UPDATE;

    -- Check fence conditions
    IF v_holder IS NULL OR v_holder <> p_incarnation::uuid THEN
        v_outcome := 'rejected';
        v_reason := 'not_holder';
        v_committed_at := clock_timestamp();
        v_pre_version := NULL;
        v_pre_max_epoch := v_owner_epoch;
    ELSIF v_owner_epoch <> p_epoch THEN
        v_outcome := 'rejected';
        v_reason := 'stale_epoch';
        v_committed_at := clock_timestamp();
        v_pre_version := NULL;
        v_pre_max_epoch := v_owner_epoch;
    ELSIF v_expires_at <= clock_timestamp() THEN
        v_outcome := 'rejected';
        v_reason := 'expired';
        v_committed_at := clock_timestamp();
        v_pre_version := NULL;
        v_pre_max_epoch := v_owner_epoch;
    ELSE
        -- Fence passed, lock state and track max epoch
        SELECT version INTO v_pre_version
        FROM sink.state
        WHERE trial_id = p_trial_id AND target_key = p_target_key
        FOR UPDATE;

        IF v_pre_version IS NULL THEN
            v_pre_version := 0;
            INSERT INTO sink.state (trial_id, target_key, version)
            VALUES (p_trial_id, p_target_key, 0);
        END IF;

        v_pre_max_epoch := sink.advance_epoch(p_trial_id, p_stream_id, p_epoch);

        -- Try to insert with unique constraint
        BEGIN
            INSERT INTO sink.responses (trial_id, op_key, response)
            VALUES (p_trial_id, p_op_key, jsonb_build_object('accepted', true))
            ON CONFLICT (trial_id, op_key) DO NOTHING;

            IF NOT FOUND THEN
                v_outcome := 'rejected';
                v_reason := 'dup_key';
            ELSE
                INSERT INTO sink.effects (trial_id, business_key, op_key, version)
                VALUES (p_trial_id, p_business_key, p_op_key, p_source_version);
                UPDATE sink.state SET version = p_source_version
                WHERE trial_id = p_trial_id AND target_key = p_target_key;
                v_outcome := 'accepted';
                v_reason := NULL;
            END IF;
        EXCEPTION WHEN unique_violation THEN
            v_outcome := 'rejected';
            v_reason := 'dup_key';
        END;

        v_committed_at := clock_timestamp();
    END IF;

    -- Log attempt
    INSERT INTO sink.attempt_log (
        trial_id, condition, worker_id, incarnation, stream_id, epoch,
        op_key, business_key, target_key, source_version, prep_cpu_ns, at_risk,
        outcome, reason, pre_version, pre_max_epoch, committed_at
    ) VALUES (
        p_trial_id, p_condition, p_worker_id, p_incarnation, p_stream_id, p_epoch,
        p_op_key, p_business_key, p_target_key, p_source_version, p_prep_cpu_ns, p_at_risk,
        v_outcome, v_reason, v_pre_version, v_pre_max_epoch, v_committed_at
    );

    RETURN jsonb_build_object('outcome', v_outcome, 'reason', v_reason, 'committed_at', v_committed_at);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, sink, own;

-- Fenced unique cached sink (C4): fence with unique constraint and response caching
CREATE OR REPLACE FUNCTION sink.sink_fenced_unique_cached(
    p_trial_id text,
    p_condition text,
    p_worker_id text,
    p_incarnation uuid,
    p_stream_id text,
    p_epoch bigint,
    p_op_key text,
    p_business_key text,
    p_target_key text,
    p_source_version bigint,
    p_prep_cpu_ns bigint,
    p_at_risk boolean DEFAULT false
) RETURNS jsonb AS $$
DECLARE
    v_holder uuid;
    v_owner_epoch bigint;
    v_expires_at timestamptz;
    v_pre_version bigint;
    v_pre_max_epoch bigint;
    v_committed_at timestamptz;
    v_outcome text;
    v_reason text;
    v_cached_response jsonb;
    v_effect_id uuid;
BEGIN
    -- Lock owner row and check fence
    SELECT holder, epoch, expires_at INTO v_holder, v_owner_epoch, v_expires_at
    FROM own.owner
    WHERE stream_id = p_stream_id
    FOR UPDATE;

    -- Check fence conditions
    IF v_holder IS NULL OR v_holder <> p_incarnation::uuid THEN
        v_outcome := 'rejected';
        v_reason := 'not_holder';
        v_committed_at := clock_timestamp();
        v_pre_version := NULL;
        v_pre_max_epoch := v_owner_epoch;
    ELSIF v_owner_epoch <> p_epoch THEN
        v_outcome := 'rejected';
        v_reason := 'stale_epoch';
        v_committed_at := clock_timestamp();
        v_pre_version := NULL;
        v_pre_max_epoch := v_owner_epoch;
    ELSIF v_expires_at <= clock_timestamp() THEN
        v_outcome := 'rejected';
        v_reason := 'expired';
        v_committed_at := clock_timestamp();
        v_pre_version := NULL;
        v_pre_max_epoch := v_owner_epoch;
    ELSE
        -- Fence passed, check for cached response
        SELECT response INTO v_cached_response
        FROM sink.responses
        WHERE trial_id = p_trial_id AND op_key = p_op_key
        FOR UPDATE;

        IF v_cached_response IS NOT NULL THEN
            -- Replay from cache
            v_outcome := 'replayed';
            v_reason := NULL;
            v_committed_at := clock_timestamp();
            v_pre_version := NULL;
            v_pre_max_epoch := NULL;
        ELSE
            -- New submission
            SELECT version INTO v_pre_version
            FROM sink.state
            WHERE trial_id = p_trial_id AND target_key = p_target_key
            FOR UPDATE;

            IF v_pre_version IS NULL THEN
                v_pre_version := 0;
                INSERT INTO sink.state (trial_id, target_key, version)
                VALUES (p_trial_id, p_target_key, 0);
            END IF;

            v_pre_max_epoch := sink.advance_epoch(p_trial_id, p_stream_id, p_epoch);

            -- Insert effect
            INSERT INTO sink.effects (trial_id, business_key, op_key, version, committed_at)
            VALUES (p_trial_id, p_business_key, p_op_key, p_source_version, clock_timestamp())
            RETURNING effect_id INTO v_effect_id;

            UPDATE sink.state SET version = p_source_version
            WHERE trial_id = p_trial_id AND target_key = p_target_key;

            v_committed_at := clock_timestamp();

            -- Cache response
            v_cached_response := jsonb_build_object('effect_id', v_effect_id,
                                  'epoch', p_epoch, 'committed_at', v_committed_at);
            INSERT INTO sink.responses (trial_id, op_key, response, committed_at)
            VALUES (p_trial_id, p_op_key, v_cached_response, v_committed_at);

            v_outcome := 'accepted';
            v_reason := NULL;
        END IF;
    END IF;

    -- Log attempt
    INSERT INTO sink.attempt_log (
        trial_id, condition, worker_id, incarnation, stream_id, epoch,
        op_key, business_key, target_key, source_version, prep_cpu_ns, at_risk,
        outcome, reason, pre_version, pre_max_epoch, committed_at
    ) VALUES (
        p_trial_id, p_condition, p_worker_id, p_incarnation, p_stream_id, p_epoch,
        p_op_key, p_business_key, p_target_key, p_source_version, p_prep_cpu_ns, p_at_risk,
        v_outcome, v_reason, v_pre_version, v_pre_max_epoch, v_committed_at
    );

    RETURN jsonb_build_object('outcome', v_outcome, 'reason', v_reason,
                              'response', v_cached_response);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, sink, own;

-- Remote sink (C3r): remote fence with unique constraint
CREATE OR REPLACE FUNCTION rsink.sink_remote(
    p_trial_id text,
    p_condition text,
    p_worker_id text,
    p_incarnation uuid,
    p_stream_id text,
    p_epoch bigint,
    p_op_key text,
    p_business_key text,
    p_target_key text,
    p_source_version bigint,
    p_prep_cpu_ns bigint,
    p_at_risk boolean DEFAULT false
) RETURNS jsonb AS $$
DECLARE
    v_e_current bigint;
    v_pre_version bigint;
    v_pre_max_epoch bigint;
    v_committed_at timestamptz;
    v_outcome text;
    v_reason text;
BEGIN
    -- Lock fence row and check epoch
    SELECT e_current INTO v_e_current
    FROM rsink.fence
    WHERE trial_id = p_trial_id AND stream_id = p_stream_id
    FOR UPDATE;

    IF v_e_current IS NULL THEN
        v_e_current := 0;
        INSERT INTO rsink.fence (trial_id, stream_id, e_current)
        VALUES (p_trial_id, p_stream_id, 0);
    END IF;
    v_pre_max_epoch := v_e_current;

    -- Check epoch
    IF p_epoch < v_e_current THEN
        v_outcome := 'rejected';
        v_reason := 'stale_epoch';
        v_committed_at := clock_timestamp();
        v_pre_version := NULL;
    ELSE
        -- Epoch is current or newer, advance fence if needed
        IF p_epoch > v_e_current THEN
            UPDATE rsink.fence
            SET e_current = p_epoch, advanced_at = clock_timestamp()
            WHERE trial_id = p_trial_id AND stream_id = p_stream_id;
        END IF;

        -- Lock state and read pre_version
        SELECT version INTO v_pre_version
        FROM rsink.state
        WHERE trial_id = p_trial_id AND target_key = p_target_key
        FOR UPDATE;

        IF v_pre_version IS NULL THEN
            v_pre_version := 0;
            INSERT INTO rsink.state (trial_id, target_key, version)
            VALUES (p_trial_id, p_target_key, 0);
        END IF;

        -- Try to insert with unique constraint
        BEGIN
            INSERT INTO rsink.effects (trial_id, business_key, op_key, version, committed_at)
            VALUES (p_trial_id, p_business_key, p_op_key, p_source_version, clock_timestamp())
            ON CONFLICT (trial_id, op_key) DO NOTHING;

            IF NOT FOUND THEN
                v_outcome := 'rejected';
                v_reason := 'dup_key';
            ELSE
                UPDATE rsink.state SET version = p_source_version
                WHERE trial_id = p_trial_id AND target_key = p_target_key;
                v_outcome := 'accepted';
                v_reason := NULL;
            END IF;
        EXCEPTION WHEN unique_violation THEN
            v_outcome := 'rejected';
            v_reason := 'dup_key';
        END;

        v_committed_at := clock_timestamp();
    END IF;

    -- Log attempt
    INSERT INTO rsink.attempt_log (
        trial_id, condition, worker_id, incarnation, stream_id, epoch,
        op_key, business_key, target_key, source_version, prep_cpu_ns, at_risk,
        outcome, reason, pre_version, pre_max_epoch, committed_at
    ) VALUES (
        p_trial_id, p_condition, p_worker_id, p_incarnation, p_stream_id, p_epoch,
        p_op_key, p_business_key, p_target_key, p_source_version, p_prep_cpu_ns, p_at_risk,
        v_outcome, v_reason, v_pre_version, v_pre_max_epoch, v_committed_at
    );

    RETURN jsonb_build_object('outcome', v_outcome, 'reason', v_reason, 'committed_at', v_committed_at);
END;
$$ LANGUAGE plpgsql SECURITY INVOKER SET search_path = pg_catalog, rsink;

-- Grant execute on sink functions to worker_rw
GRANT EXECUTE ON FUNCTION sink.sink_plain(text, text, text, uuid, text, bigint, text, text, text, bigint, bigint, boolean) TO worker_rw;
GRANT EXECUTE ON FUNCTION sink.sink_unique(text, text, text, uuid, text, bigint, text, text, text, bigint, bigint, boolean) TO worker_rw;
GRANT EXECUTE ON FUNCTION sink.sink_version(text, text, text, uuid, text, bigint, text, text, text, bigint, bigint, boolean) TO worker_rw;
GRANT EXECUTE ON FUNCTION sink.sink_fenced(text, text, text, uuid, text, bigint, text, text, text, bigint, bigint, boolean) TO worker_rw;
GRANT EXECUTE ON FUNCTION sink.sink_fenced_unique(text, text, text, uuid, text, bigint, text, text, text, bigint, bigint, boolean) TO worker_rw;
GRANT EXECUTE ON FUNCTION sink.sink_fenced_unique_cached(text, text, text, uuid, text, bigint, text, text, text, bigint, bigint, boolean) TO worker_rw;

-- Grant execute on remote sink function to rsink_rw
GRANT EXECUTE ON FUNCTION rsink.sink_remote(text, text, text, uuid, text, bigint, text, text, text, bigint, bigint, boolean) TO rsink_rw;
