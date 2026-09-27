"""Fault injection handling."""

import os
import signal
import time
import uuid
from typing import Optional

import psycopg


class FaultManager:
    """Manages fault injection for workers."""

    def __init__(self, conn: psycopg.Connection, config, incarnation: uuid.UUID):
        self.conn = conn
        self.config = config
        self.trial_id = config.trial_id
        self.worker_id = config.worker_id
        self.incarnation = incarnation
        self.fault_armed = False
        self.captured_batch = None
        self.at_risk = False

    def check_fault_plan(self) -> Optional[dict]:
        """Check if this worker has a fault plan and if it's armed."""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT fault_type, trigger_type, armed
                FROM ctl.fault_plan
                WHERE trial_id = %s AND worker_id = %s AND incarnation = %s
            """, (self.trial_id, self.worker_id, self.incarnation))

            row = cur.fetchone()
            if row:
                return {
                    "fault_type": row[0],
                    "trigger_type": row[1],
                    "armed": row[2]
                }
            return None

    def arm_fault(self):
        """Arm the fault for this worker."""
        self.fault_armed = True
        with self.conn.cursor() as cur:
            cur.execute("""
                UPDATE ctl.fault_plan
                SET armed = true
                WHERE trial_id = %s AND worker_id = %s AND incarnation = %s
            """, (self.trial_id, self.worker_id, self.incarnation))

    def log_prepared_batch(self, op_keys: list):
        """Log that a batch has been prepared before fault."""
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO ctl.fault_events (trial_id, worker_id, incarnation, event_type, op_keys, at)
                VALUES (%s, %s, %s, 'prepared_batch', %s, clock_timestamp())
            """, (self.trial_id, self.worker_id, self.incarnation, op_keys))

    def self_stop(self):
        """Self-stop with SIGSTOP."""
        self.at_risk = True
        os.kill(os.getpid(), signal.SIGSTOP)

    def resume_after_delay(self, delay: float):
        """Resume after delay and log the resume marker."""
        time.sleep(delay)

        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO ctl.fault_markers (trial_id, worker_id, incarnation, marker_type, at)
                VALUES (%s, %s, %s, 'cont', clock_timestamp())
            """, (self.trial_id, self.worker_id, self.incarnation))

    def verify_stopped(self) -> bool:
        """Verify that the process is in stopped state (state T in /proc)."""
        try:
            with open(f"/proc/{os.getpid()}/status", "r") as f:
                content = f.read()
                return "State:\tT" in content
        except (FileNotFoundError, IOError):
            return False

    def check_should_pause(self, items_done: int) -> bool:
        """Check if fault should be triggered based on warm-up items."""
        if not self.fault_armed:
            return False

        fault_plan = self.check_fault_plan()
        if not fault_plan or not fault_plan["armed"]:
            return False

        # Arm after warm-up items are done
        if items_done >= self.config.warmup_items:
            return True

        return False

    def handle_fault(self, batch: list, op_keys: list):
        """Handle fault injection: log batch, stop, then resume after delay."""
        self.captured_batch = batch
        self.log_prepared_batch(op_keys)
        self.self_stop()
        self.resume_after_delay(self.config.resume_delay)
