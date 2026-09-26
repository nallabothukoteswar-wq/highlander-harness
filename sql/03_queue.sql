-- Work queue schema
-- Manages the items to be processed by workers

CREATE TABLE IF NOT EXISTS src.items (
    trial_id       text NOT NULL,
    item_id        bigint NOT NULL,
    stream_id      text NOT NULL,
    business_key   text NOT NULL,
    target_key     text NOT NULL,
    source_version bigint NOT NULL,
    payload        jsonb,
    done           boolean NOT NULL DEFAULT false,
    done_at        timestamptz,
    claimed_by     uuid,
    visible_at     timestamptz,
    PRIMARY KEY (trial_id, item_id)
);

-- Index for claiming with SKIP LOCKED
CREATE INDEX IF NOT EXISTS src_items_claim_idx ON src.items (trial_id, done, visible_at)
WHERE done = false;

-- Index for fetching undone items in order (lease mode)
CREATE INDEX IF NOT EXISTS src_items_fetch_idx ON src.items (trial_id, item_id)
WHERE done = false;

-- Grant privileges to worker_rw
GRANT SELECT, INSERT, UPDATE ON src.items TO worker_rw;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA src TO worker_rw;
