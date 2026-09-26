"""Heartbeat thread for worker liveness."""

import threading
import time
import uuid

import psycopg


class HeartbeatThread(threading.Thread):
    """Background thread that writes heartbeats to the database."""

    def __init__(self, conn: psycopg.Connection, config, stop_event: threading.Event):
        super().__init__(daemon=True)
        self.conn = conn
        self.config = config
        self.trial_id = config.trial_id
        self.worker_id = config.worker_id
        self.incarnation = uuid.uuid4()
        self.stop_event = stop_event
        self.interval = 0.2  # 200 ms

    def run(self):
        """Run heartbeat loop until stop event is set."""
        while not self.stop_event.is_set():
            try:
                self._write_heartbeat()
            except Exception as e:
                # Log error but continue
                print(f"Heartbeat error: {e}")

            time.sleep(self.interval)

    def _write_heartbeat(self):
        """Write a heartbeat to the database."""
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO ctl.heartbeats (trial_id, worker_id, incarnation, beat_at)
                VALUES (%s, %s, %s, clock_timestamp())
            """, (self.trial_id, self.worker_id, self.incarnation))
