"""Workload generation and item preparation."""

import hashlib
import time
import uuid
from typing import List

import psycopg


class WorkloadGenerator:
    """Generates work items for different workload types."""

    def __init__(self, conn: psycopg.Connection, config, incarnation: uuid.UUID):
        self.conn = conn
        self.config = config
        self.trial_id = config.trial_id
        self.num_items = config.num_items
        self.workload = config.workload
        self.stream_id = config.stream_id
        self.incarnation = incarnation

    def generate_and_populate(self):
        """Generate items and populate the work queue."""
        items = self._generate_items()
        self._populate_queue(items)

    def _generate_items(self) -> List[dict]:
        """Generate items based on workload type."""
        if self.workload == "dup":
            return self._generate_dup_workload()
        elif self.workload == "ordered":
            return self._generate_ordered_workload()
        else:
            raise ValueError(f"Unknown workload: {self.workload}")

    def _generate_dup_workload(self) -> List[dict]:
        """Generate duplicate workload: 1,000 items with distinct business keys."""
        items = []
        for i in range(self.num_items):
            items.append({
                "item_id": i,
                "stream_id": self.stream_id,
                "business_key": f"key-{i}",
                "target_key": f"target-{i % 20}",  # Distribute across 20 targets
                "source_version": 1,
                "payload": {"data": f"item-{i}"}
            })
        return items

    def _generate_ordered_workload(self) -> List[dict]:
        """Generate ordered workload: 1,000 items over 20 target keys with monotone versions."""
        items = []
        for i in range(self.num_items):
            target_key = f"target-{i % 20}"
            source_version = (i // 20) + 1  # Monotone per target
            items.append({
                "item_id": i,
                "stream_id": self.stream_id,
                "business_key": f"key-{i}",
                "target_key": target_key,
                "source_version": source_version,
                "payload": {"data": f"item-{i}"}
            })
        return items

    def _populate_queue(self, items: List[dict]):
        """Populate the work queue with generated items."""
        with self.conn.cursor() as cur:
            for item in items:
                cur.execute("""
                    INSERT INTO src.items
                    (trial_id, item_id, stream_id, business_key, target_key, source_version, payload, done)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, false)
                """, (
                    self.trial_id,
                    item["item_id"],
                    item["stream_id"],
                    item["business_key"],
                    item["target_key"],
                    item["source_version"],
                    item["payload"]
                ))


class ItemPreparer:
    """Prepares items before submission to sink."""

    def __init__(self, config, incarnation: uuid.UUID):
        self.config = config
        self.prep_cpu_ms = config.prep_cpu_ms
        self.incarnation = incarnation

    def prepare_batch(self, items: List[dict]) -> List[dict]:
        """Prepare a batch of items with synthetic CPU work.

        Returns items with prep_cpu_ns recorded.
        """
        prepared = []
        for item in items:
            start_cpu = time.thread_time_ns()

            # Synthetic CPU work (e.g., SHA-256 loop)
            self._do_cpu_work(self.prep_cpu_ms)

            end_cpu = time.thread_time_ns()
            prep_cpu_ns = end_cpu - start_cpu

            prepared.append({
                **item,
                "prep_cpu_ns": prep_cpu_ns
            })

        return prepared

    def _do_cpu_work(self, duration_ms: float):
        """Perform synthetic CPU work for specified duration."""
        target_time = time.thread_time_ns() + (duration_ms * 1_000_000)
        data = b"dummy data for cpu work"

        while time.thread_time_ns() < target_time:
            # SHA-256 hash loop
            for _ in range(100):
                hashlib.sha256(data).digest()

    def get_op_key(self, item: dict) -> str:
        """Generate operation key based on workload type."""
        if self.config.workload == "dup":
            # Dup workload: op_key = business_key (same across workers)
            return item["business_key"]
        elif self.config.workload == "ordered":
            # Ordered workload: op_key = incarnation:item_id (unique per worker)
            return f"{self.incarnation}:{item['item_id']}"
        else:
            raise ValueError(f"Unknown workload: {self.config.workload}")
