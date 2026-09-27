"""Worker lifecycle state machine."""

import os
import signal
import time
import uuid
from enum import Enum
from typing import Optional

import psycopg


class WorkerState(Enum):
    """Worker lifecycle states."""
    STANDBY = "standby"
    CANDIDATE = "candidate"
    ACTIVE = "active"
    DRAINING = "draining"
    FAILED = "failed"


class LifecycleManager:
    """Manages worker lifecycle state transitions."""

    def __init__(self, conn: psycopg.Connection, config, incarnation: uuid.UUID):
        self.conn = conn
        self.config = config
        self.trial_id = config.trial_id
        self.worker_id = config.worker_id
        self.incarnation = incarnation
        self.state = WorkerState.STANDBY
        self.transition_queue = []

    def register_incarnation(self, pid: Optional[int] = None):
        """Register this incarnation in the database."""
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO ctl.incarnations (trial_id, worker_id, incarnation, started_at, pid)
                VALUES (%s, %s, %s, clock_timestamp(), %s)
            """, (self.trial_id, self.worker_id, self.incarnation, pid))

        # Write PID to shared file on kind platform
        if self.config.platform == "kind" and self.config.shared_dir:
            pid_file = os.path.join(self.config.shared_dir, "worker.pid")
            with open(pid_file, "w") as f:
                f.write(str(os.getpid()))

    def transition(self, to_state: WorkerState, event: str):
        """Transition to a new state and log it."""
        from_state = self.state
        self.state = to_state

        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO ctl.transitions (trial_id, incarnation, from_state, to_state, event, at)
                VALUES (%s, %s, %s, %s, %s, clock_timestamp())
            """, (self.trial_id, self.incarnation, from_state.value, to_state.value, event))

    def get_state(self) -> WorkerState:
        """Get current state."""
        return self.state

    def set_failed(self, reason: str):
        """Transition to failed state."""
        self.transition(WorkerState.FAILED, f"failed: {reason}")

    def stop_submission(self):
        """Stop submission and transition to draining."""
        if self.state == WorkerState.ACTIVE:
            self.transition(WorkerState.DRAINING, "stop_admission")

    def go_standby(self):
        """Transition to standby."""
        self.transition(WorkerState.STANDBY, "go_standby")

    def self_stop(self):
        """Self-stop with SIGSTOP (for fault injection)."""
        self.transition(WorkerState.FAILED, "self_stop")
        os.kill(os.getpid(), signal.SIGSTOP)

    def self_kill(self):
        """Self-kill with SIGKILL (for fault injection)."""
        self.transition(WorkerState.FAILED, "self_kill")
        os.kill(os.getpid(), signal.SIGKILL)
