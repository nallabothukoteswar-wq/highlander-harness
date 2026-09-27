"""Ownership lease management."""

import time
import uuid
from typing import Optional

import psycopg


class OwnershipManager:
    """Manages ownership lease acquisition and renewal."""

    def __init__(self, conn: psycopg.Connection, config, incarnation: uuid.UUID):
        self.conn = conn
        self.config = config
        self.incarnation: uuid.UUID = incarnation
        self.stream_id: str = config.stream_id
        self.lease_secs: float = config.lease_secs
        self.current_epoch: Optional[int] = None
        self.last_renewal_at: Optional[float] = None

    def acquire(self) -> Optional[int]:
        """Attempt to acquire ownership lease.

        Returns the new epoch if successful, None otherwise.
        """
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT own.acquire(%s, %s, %s)",
                (self.stream_id, self.incarnation, self.lease_secs)
            )
            result = cur.fetchone()
            if result and result[0] is not None:
                self.current_epoch = result[0]
                return self.current_epoch
            return None

    def renew(self) -> bool:
        """Attempt to renew ownership lease.

        Returns True if successful, False otherwise.
        """
        if self.current_epoch is None:
            return False

        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT own.renew(%s, %s, %s, %s)",
                (self.stream_id, self.incarnation, self.current_epoch, self.lease_secs)
            )
            result = cur.fetchone()
            if result and result[0] is not None:
                self.last_renewal_at = time.time()
                return True
            return False

    def get_current_owner(self) -> Optional[dict]:
        """Get the current owner information."""
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT holder, epoch, expires_at, granted_at FROM own.owner WHERE stream_id = %s",
                (self.stream_id,)
            )
            row = cur.fetchone()
            if row:
                return {
                    "holder": row[0],
                    "epoch": row[1],
                    "expires_at": row[2],
                    "granted_at": row[3]
                }
            return None

    def is_current_owner(self) -> bool:
        """Check if this worker is the current owner."""
        owner = self.get_current_owner()
        if owner is None:
            return False
        return owner["holder"] == self.incarnation and owner["epoch"] == self.current_epoch
