"""Work queue management."""

import time
from typing import List, Optional

import psycopg


class QueueManager:
    """Manages work queue operations."""

    def __init__(self, conn: psycopg.Connection, config):
        self.conn = conn
        self.config = config
        self.trial_id = config.trial_id
        self.batch_size = config.batch_size
        self.visibility_timeout = config.visibility_timeout

    def claim_items(self, worker_id: str) -> List[dict]:
        """Claim items using SKIP LOCKED (uncoordinated mode).

        Returns list of claimed items.
        """
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT item_id, stream_id, business_key, target_key, source_version, payload
                FROM src.items
                WHERE trial_id = %s
                  AND done = false
                  AND (visible_at IS NULL OR visible_at <= clock_timestamp())
                ORDER BY item_id
                FOR UPDATE SKIP LOCKED
                LIMIT %s
            """, (self.trial_id, self.batch_size))

            items = []
            for row in cur.fetchall():
                items.append({
                    "item_id": row[0],
                    "stream_id": row[1],
                    "business_key": row[2],
                    "target_key": row[3],
                    "source_version": row[4],
                    "payload": row[5]
                })

            # Mark as claimed with visibility timeout
            if items:
                item_ids = [item["item_id"] for item in items]
                cur.execute("""
                    UPDATE src.items
                    SET claimed_by = %s,
                        visible_at = clock_timestamp() + make_interval(secs => %s)
                    WHERE trial_id = %s AND item_id = ANY(%s)
                """, (worker_id, self.visibility_timeout, self.trial_id, item_ids))

            return items

    def fetch_items(self) -> List[dict]:
        """Fetch next undone items in order (lease mode).

        Returns list of items.
        """
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT item_id, stream_id, business_key, target_key, source_version, payload
                FROM src.items
                WHERE trial_id = %s AND done = false
                ORDER BY item_id
                LIMIT %s
            """, (self.trial_id, self.batch_size))

            items = []
            for row in cur.fetchall():
                items.append({
                    "item_id": row[0],
                    "stream_id": row[1],
                    "business_key": row[2],
                    "target_key": row[3],
                    "source_version": row[4],
                    "payload": row[5]
                })

            return items

    def mark_done(self, item_id: int, conn: Optional[psycopg.Connection] = None):
        """Mark an item as done.

        If conn is provided, use that connection (for in-transaction marking).
        """
        target_conn = conn if conn else self.conn
        with target_conn.cursor() as cur:
            cur.execute("""
                UPDATE src.items
                SET done = true, done_at = clock_timestamp(), claimed_by = NULL
                WHERE trial_id = %s AND item_id = %s
            """, (self.trial_id, item_id))

    def get_undone_count(self) -> int:
        """Get count of undone items."""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT COUNT(*) FROM src.items
                WHERE trial_id = %s AND done = false
            """, (self.trial_id,))
            return cur.fetchone()[0]
