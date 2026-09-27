"""Main worker entry point."""

import os
import signal
import sys
import threading
import time
import uuid
import hashlib
import random

import psycopg

from worker.config import WorkerConfig
from worker.ownership import OwnershipManager
from worker.queue import QueueManager
from worker.sinks import SinkManager
from worker.workloads import WorkloadGenerator, ItemPreparer
from worker.lifecycle import LifecycleManager, WorkerState
from worker.heartbeat import HeartbeatThread
from worker.faults import FaultManager


def main():
    """Main worker loop."""
    config = WorkerConfig.from_env()
    # Derive each worker's reproducible retry stream from the canonical trial ID.
    random.seed(int(hashlib.sha256(f'{config.trial_id}:{config.worker_id}'.encode()).hexdigest()[:16], 16))

    # Establish database connections
    conn = psycopg.connect(
        host=config.db_host,
        port=config.db_port,
        dbname=config.db_name,
        user=config.db_user,
        password=config.db_password,
        autocommit=True
    )

    rsink_conn = None
    if config.condition == "C3r":
        rsink_conn = psycopg.connect(
            host=config.rsink_db_host,
            port=config.rsink_db_port,
            dbname=config.rsink_db_name,
            user=config.rsink_db_user,
            password=config.rsink_db_password,
            autocommit=True
        )

    # A process has exactly one fencing identity across all managers.
    incarnation = uuid.uuid4()
    # Initialize managers
    lifecycle = LifecycleManager(conn, config, incarnation)
    ownership = OwnershipManager(conn, config, incarnation)
    queue = QueueManager(conn, config)
    sink = SinkManager(conn, rsink_conn, config, incarnation)
    preparer = ItemPreparer(config, incarnation)
    fault = FaultManager(conn, config, incarnation)

    # Register incarnation
    lifecycle.register_incarnation()

    # Start heartbeat thread
    stop_event = threading.Event()
    heartbeat = HeartbeatThread(conn, config, stop_event, incarnation)
    heartbeat.start()

    # Start renewal thread (for lease mode)
    renewal_stop_event = threading.Event()
    renewal_thread = None
    if config.condition in ["C2", "C2f", "C3", "C3r", "C4"]:
        renewal_thread = threading.Thread(
            target=renewal_loop,
            args=(ownership, renewal_stop_event, config.lease_secs),
            daemon=True
        )
        renewal_thread.start()

    try:
        run_worker_loop(config, lifecycle, ownership, queue, sink, preparer, fault)
    finally:
        stop_event.set()
        if renewal_thread:
            renewal_stop_event.set()
        conn.close()
        if rsink_conn:
            rsink_conn.close()


def renewal_loop(ownership: OwnershipManager, stop_event: threading.Event, lease_secs: float):
    """Renewal loop for lease mode."""
    interval = lease_secs / 3  # Renew every L/3

    while not stop_event.is_set():
        time.sleep(interval)

        success = ownership.renew()
        if not success:
            # Renewal failed, stop admission
            print("Renewal failed, stopping admission")
            break


def run_worker_loop(
    config: WorkerConfig,
    lifecycle: LifecycleManager,
    ownership: OwnershipManager,
    queue: QueueManager,
    sink: SinkManager,
    preparer: ItemPreparer,
    fault: FaultManager
):
    """Main worker processing loop."""
    items_done = 0
    last_submit_time = time.time()
    throttle_interval = 1.0 / config.throttle_per_sec

    # Check if this worker should acquire ownership
    use_lease = config.condition in ["C2", "C2f", "C3", "C3r", "C4"]

    while True:
        # Check fault plan
        fault_plan = fault.check_fault_plan()
        if fault_plan and fault_plan["armed"]:
            fault.arm_fault()

        # Try to acquire ownership if in lease mode
        if use_lease:
            epoch = ownership.acquire()
            if epoch is not None:
                lifecycle.transition(WorkerState.ACTIVE, "acquired")
            else:
                lifecycle.transition(WorkerState.STANDBY, "not_owner")
                time.sleep(config.acquire_interval)
                continue
        else:
            lifecycle.transition(WorkerState.ACTIVE, "uncoordinated")

        # Fetch or claim items
        if use_lease:
            items = queue.fetch_items()
        else:
            items = queue.claim_items(config.worker_id)

        if not items:
            # No more items
            if queue.get_undone_count() == 0:
                break
            time.sleep(0.1)
            continue

        # Prepare batch
        prepared = preparer.prepare_batch(items)
        op_keys = [preparer.get_op_key(item) for item in prepared]

        # Check if fault should trigger
        if fault.check_should_pause(items_done):
            fault.handle_fault(prepared, op_keys)
            lifecycle.stop_submission()
            continue

        # Submit items
        for item in prepared:
            # Throttle
            elapsed = time.time() - last_submit_time
            if elapsed < throttle_interval:
                time.sleep(throttle_interval - elapsed)
            last_submit_time = time.time()

            # Check safety deadline
            if ownership.last_renewal_at:
                time_since_renewal = time.time() - ownership.last_renewal_at
                if time_since_renewal > config.lease_secs - config.safety_delta:
                    lifecycle.stop_submission()
                    break

            # Get op_key
            op_key = preparer.get_op_key(item)

            # Submit to sink
            epoch = ownership.current_epoch if use_lease else None
            at_risk = fault.at_risk

            if config.condition in ["C2f", "C3", "C4"] and config.lost_ack_rate > 0:
                # Series D: lost ack simulation
                response = sink.retry_with_lost_ack(
                    item["item_id"],
                    op_key,
                    item["business_key"],
                    item["target_key"],
                    item["source_version"],
                    item["prep_cpu_ns"],
                    at_risk,
                    epoch,
                    config.lost_ack_rate
                )
            else:
                response = sink.submit_and_mark_done(
                    item["item_id"],
                    op_key,
                    item["business_key"],
                    item["target_key"],
                    item["source_version"],
                    item["prep_cpu_ns"],
                    at_risk,
                    epoch
                )

            items_done += 1

        # Check if should stop admission
        if lifecycle.get_state() == WorkerState.DRAINING:
            lifecycle.go_standby()
            break


if __name__ == "__main__":
    main()
