"""Sink operations for different conditions."""

import time
import uuid
from typing import Optional

import psycopg


class SinkManager:
    """Manages sink operations."""

    def __init__(self, conn: psycopg.Connection, rsink_conn: Optional[psycopg.Connection], config):
        self.conn = conn
        self.rsink_conn = rsink_conn
        self.config = config
        self.trial_id = config.trial_id
        self.condition = config.condition
        self.worker_id = config.worker_id
        self.incarnation = uuid.uuid4()
        self.stream_id = config.stream_id

    def _get_sink_function(self) -> str:
        """Get the appropriate sink function name for the condition."""
        sink_map = {
            "C1": "sink.sink_plain",
            "C2": "sink.sink_plain",
            "C1u": "sink.sink_unique",
            "C1v": "sink.sink_version",
            "C2f": "sink.sink_fenced",
            "C3": "sink.sink_fenced_unique",
            "C4": "sink.sink_fenced_unique_cached",
            "C3r": "rsink.sink_remote",
        }
        return sink_map.get(self.condition, "sink.sink_plain")

    def submit(
        self,
        op_key: str,
        business_key: str,
        target_key: str,
        source_version: int,
        prep_cpu_ns: int,
        at_risk: bool = False,
        epoch: Optional[int] = None
    ) -> dict:
        """Submit an item to the sink.

        Returns the sink response.
        """
        sink_func = self._get_sink_function()
        conn = self.rsink_conn if self.condition == "C3r" else self.conn

        with conn.cursor() as cur:
            cur.execute(
                f"SELECT * FROM {sink_func}(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    self.trial_id,
                    self.condition,
                    self.worker_id,
                    self.incarnation,
                    self.stream_id,
                    epoch,
                    op_key,
                    business_key,
                    target_key,
                    source_version,
                    prep_cpu_ns,
                    at_risk
                )
            )
            result = cur.fetchone()
            return result[0] if result else {}

    def submit_and_mark_done(
        self,
        item_id: int,
        op_key: str,
        business_key: str,
        target_key: str,
        source_version: int,
        prep_cpu_ns: int,
        at_risk: bool = False,
        epoch: Optional[int] = None
    ) -> dict:
        """Submit to sink and mark item done in one transaction (for colocated sinks)."""
        if self.condition == "C3r":
            # Remote sink cannot mark done in same transaction
            response = self.submit(op_key, business_key, target_key, source_version, prep_cpu_ns, at_risk, epoch)
            return response

        sink_func = self._get_sink_function()

        with self.conn.cursor() as cur:
            # Submit to sink
            cur.execute(
                f"SELECT * FROM {sink_func}(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    self.trial_id,
                    self.condition,
                    self.worker_id,
                    self.incarnation,
                    self.stream_id,
                    epoch,
                    op_key,
                    business_key,
                    target_key,
                    source_version,
                    prep_cpu_ns,
                    at_risk
                )
            )
            result = cur.fetchone()
            response = result[0] if result else {}

            # Mark item done
            cur.execute("""
                UPDATE src.items
                SET done = true, done_at = clock_timestamp(), claimed_by = NULL
                WHERE trial_id = %s AND item_id = %s
            """, (self.trial_id, item_id))

            return response

    def retry_with_lost_ack(
        self,
        item_id: int,
        op_key: str,
        business_key: str,
        target_key: str,
        source_version: int,
        prep_cpu_ns: int,
        at_risk: bool = False,
        epoch: Optional[int] = None,
        lost_ack_rate: float = 0.05
    ) -> dict:
        """Submit with simulated lost acknowledgment.

        Returns the final response after any retries.
        """
        import random

        # First submission
        response = self.submit_and_mark_done(
            item_id, op_key, business_key, target_key, source_version, prep_cpu_ns, at_risk, epoch
        )

        # Simulate lost ack
        if random.random() < lost_ack_rate and response.get("outcome") == "accepted":
            # Discard response and retry after 50ms
            time.sleep(0.05)
            retry_response = self.submit_and_mark_done(
                item_id, op_key, business_key, target_key, source_version, prep_cpu_ns, at_risk, epoch
            )

            # Classify retry outcome
            outcome = retry_response.get("outcome")
            if outcome == "accepted":
                response["retry_outcome"] = "duplicate_accepted"
            elif outcome == "rejected" and retry_response.get("reason") == "dup_key":
                response["retry_outcome"] = "unresolved_ambiguous"
            elif outcome == "replayed":
                # Compare responses
                if retry_response == response:
                    response["retry_outcome"] = "replay_stable"
                else:
                    response["retry_outcome"] = "replay_mismatch"
            else:
                response["retry_outcome"] = "unknown"

            response["original_response"] = response
            response["retry_response"] = retry_response

        return response
