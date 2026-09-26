"""Trial management for Highlander experiments."""

import os
import uuid
import json
import random
from typing import Dict, List, Optional
from datetime import datetime
import csv


class TrialRunner:
    """Manages trial execution for Highlander experiments."""

    def __init__(self, platform, campaign_dir: str, pilot: bool, trials_per_cell: int):
        self.platform = platform
        self.campaign_dir = campaign_dir
        self.pilot = pilot
        self.trials_per_cell = trials_per_cell
        self.completed_trials = set()
        self.invalid_trials = []

        # Load completed trials if resuming
        self._load_completed_trials()

    def _load_completed_trials(self):
        """Load completed trials from trials.csv."""
        trials_file = os.path.join(self.campaign_dir, "trials.csv")
        if os.path.exists(trials_file):
            with open(trials_file, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    trial_id = row['trial_id']
                    if row['valid'] == 'true':
                        self.completed_trials.add(trial_id)
                    else:
                        self.invalid_trials.append(row)

    def run_series(self, series: str):
        """Run all trials for a given series."""
        series_config = self._get_series_config(series)

        for cell in series_config['cells']:
            for replicate in range(1, self.trials_per_cell + 1):
                trial_id = self._generate_trial_id(series, cell, replicate)

                if trial_id in self.completed_trials:
                    print(f"Skipping completed trial: {trial_id}")
                    continue

                self._run_trial(trial_id, series, cell, replicate)

    def _get_series_config(self, series: str) -> Dict:
        """Get configuration for a series."""
        configs = {
            "A": {
                "cells": [
                    {"condition": "C1", "workload": "dup"},
                    {"condition": "C1", "workload": "ordered"},
                    {"condition": "C1u", "workload": "dup"},
                    {"condition": "C1u", "workload": "ordered"},
                    {"condition": "C1v", "workload": "ordered"},
                    {"condition": "C2", "workload": "dup"},
                    {"condition": "C2", "workload": "ordered"},
                    {"condition": "C2f", "workload": "dup"},
                    {"condition": "C2f", "workload": "ordered"},
                    {"condition": "C3", "workload": "dup"},
                    {"condition": "C3", "workload": "ordered"},
                    {"condition": "C3r", "workload": "dup"},
                    {"condition": "C3r", "workload": "ordered"},
                    {"condition": "C4", "workload": "dup"},
                    {"condition": "C4", "workload": "ordered"},
                ]
            },
            "B": {
                "cells": [
                    {"condition": "C1", "workload": "dup", "b": 1, "d": 0},
                    {"condition": "C1", "workload": "dup", "b": 1, "d": 1},
                    {"condition": "C1", "workload": "dup", "b": 1, "d": 5},
                    # ... more combinations
                ]
            },
            "C": {
                "cells": [
                    {"condition": "C3", "workload": "ordered", "d": 0},
                    {"condition": "C3", "workload": "ordered", "d": 1},
                    {"condition": "C3", "workload": "ordered", "d": 5},
                    {"condition": "C3r", "workload": "ordered", "d": 0},
                    {"condition": "C3r", "workload": "ordered", "d": 1},
                    {"condition": "C3r", "workload": "ordered", "d": 5},
                ]
            },
            "D": {
                "cells": [
                    {"condition": "C2f", "workload": "dup"},
                    {"condition": "C3", "workload": "dup"},
                    {"condition": "C4", "workload": "dup"},
                ]
            },
            "E": {
                "cells": [
                    {"condition": "C3", "workload": "dup", "L": 5},
                    {"condition": "C3", "workload": "dup", "L": 10},
                    {"condition": "C3", "workload": "dup", "L": 15},
                    {"condition": "C3", "workload": "dup", "L": 30},
                ]
            },
            "F": {
                "cells": [
                    {"condition": "serving", "n_replicas": 6},
                    {"condition": "serving", "n_replicas": 7},
                ]
            },
            "G": {
                "cells": [
                    {"condition": "release", "mechanism": "rolling"},
                    {"condition": "release", "mechanism": "blue-green"},
                    {"condition": "release", "mechanism": "canary"},
                ]
            }
        }

        return configs.get(series, {"cells": []})

    def _generate_trial_id(self, series: str, cell: Dict, replicate: int) -> str:
        """Generate a deterministic trial ID."""
        cell_str = json.dumps(cell, sort_keys=True)
        cell_hash = hash(cell_str) % 10000
        return f"{series}_{cell_hash}_{replicate}"

    def _run_trial(self, trial_id: str, series: str, cell: Dict, replicate: int):
        """Run a single trial."""
        print(f"Running trial: {trial_id}")

        # Reset database state
        self._reset_trial_state(trial_id, cell)

        # Set up fault plan if needed
        if series in ["A", "B"]:
            self._setup_fault_plan(trial_id, cell)

        # Start workers
        worker_ids = self.platform.start_workers(
            trial_id,
            cell["condition"],
            cell["workload"],
            num_workers=3
        )

        try:
            # Wait for trial completion or timeout
            self._wait_for_trial_completion(trial_id, worker_ids)

            # Verify fault if applicable
            valid = True
            invalid_reason = None
            if series in ["A", "B"]:
                valid, invalid_reason = self._verify_fault(trial_id, worker_ids)

            # Export trial data
            self._export_trial_data(trial_id)

            # Record trial result
            self._record_trial(trial_id, series, cell, replicate, valid, invalid_reason)

            if valid:
                self.completed_trials.add(trial_id)
            else:
                self.invalid_trials.append({
                    "trial_id": trial_id,
                    "reason": invalid_reason
                })

        finally:
            # Stop workers
            self.platform.stop_workers(worker_ids)

    def _reset_trial_state(self, trial_id: str, cell: Dict):
        """Reset database state for a trial."""
        conn = self.platform.get_db_connection()

        # Recreate trial tables based on condition
        condition = cell["condition"]

        # Clear attempt logs
        conn.execute("TRUNCATE TABLE sink.attempt_log, rsink.attempt_log CASCADE")

        # Clear effects
        conn.execute("TRUNCATE TABLE sink.effects, rsink.effects CASCADE")

        # Clear state
        conn.execute("TRUNCATE TABLE sink.state, rsink.state CASCADE")

        # Clear ownership
        conn.execute("TRUNCATE TABLE own.grants, own.renewals CASCADE")
        conn.execute("UPDATE own.owner SET holder = NULL, epoch = 0, expires_at = '-infinity'")

        # Clear control tables
        conn.execute("TRUNCATE TABLE ctl.incarnations, ctl.heartbeats, ctl.transitions, ctl.fault_plan, ctl.fault_events, ctl.fault_markers, ctl.kill_markers CASCADE")

        # Set up unique constraint if needed
        if condition in ["C1u", "C3", "C3r", "C4"]:
            conn.execute("""
                ALTER TABLE sink.effects ADD CONSTRAINT IF NOT EXISTS effects_op_key_unique UNIQUE (trial_id, op_key)
            """)
        else:
            conn.execute("""
                ALTER TABLE sink.effects DROP CONSTRAINT IF EXISTS effects_op_key_unique
            """)

        # Set up response cache if needed
        if condition == "C4":
            conn.execute("TRUNCATE TABLE sink.responses CASCADE")
        else:
            conn.execute("TRUNCATE TABLE sink.responses CASCADE")

        conn.close()

    def _setup_fault_plan(self, trial_id: str, cell: Dict):
        """Set up fault plan for a trial."""
        conn = self.platform.get_db_connection()

        # For Series A, fault worker-0 after warm-up
        conn.execute("""
            INSERT INTO ctl.fault_plan (trial_id, worker_id, incarnation, fault_type, trigger_type, armed)
            VALUES (%s, 'worker-0', NULL, 'pause', 'after_first_accept', false)
        """, (trial_id,))

        conn.close()

    def _wait_for_trial_completion(self, trial_id: str, worker_ids: List[str]):
        """Wait for trial completion."""
        # Poll database for completion
        conn = self.platform.get_db_connection()

        timeout = 300  # 5 minutes
        start_time = time.time()

        while time.time() - start_time < timeout:
            # Check if all items are done
            result = conn.execute("""
                SELECT COUNT(*) FROM src.items WHERE trial_id = %s AND done = false
            """, (trial_id,)).fetchone()

            if result[0] == 0:
                break

            time.sleep(1)

        conn.close()

    def _verify_fault(self, trial_id: str, worker_ids: List[str]) -> tuple:
        """Verify fault injection."""
        # Check fault markers
        conn = self.platform.get_db_connection()

        # Check that cont marker exists
        result = conn.execute("""
            SELECT COUNT(*) FROM ctl.fault_markers WHERE trial_id = %s AND marker_type = 'cont'
        """, (trial_id,)).fetchone()

        if result[0] == 0:
            conn.close()
            return False, "No cont marker found"

        # Check heartbeat gap
        result = conn.execute("""
            SELECT COUNT(*) FROM ctl.heartbeat_summary
            WHERE trial_id = %s AND beat_count < 10
        """, (trial_id,)).fetchone()

        if result[0] == 0:
            conn.close()
            return False, "No heartbeat gap detected"

        conn.close()
        return True, None

    def _export_trial_data(self, trial_id: str):
        """Export trial data to CSV files."""
        conn = self.platform.get_db_connection()

        # Export attempts
        with open(os.path.join(self.campaign_dir, "attempts.csv"), 'a') as f:
            writer = csv.writer(f)
            result = conn.execute("""
                SELECT * FROM sink.attempt_log WHERE trial_id = %s
            """, (trial_id,))

            for row in result:
                writer.writerow(row)

        # Export grants
        with open(os.path.join(self.campaign_dir, "grants.csv"), 'a') as f:
            writer = csv.writer(f)
            result = conn.execute("""
                SELECT * FROM own.grants WHERE stream_id = 'S1'
            """)

            for row in result:
                writer.writerow(row)

        # Export renewals
        with open(os.path.join(self.campaign_dir, "renewals.csv"), 'a') as f:
            writer = csv.writer(f)
            result = conn.execute("""
                SELECT * FROM own.renewals WHERE stream_id = 'S1'
            """)

            for row in result:
                writer.writerow(row)

        conn.close()

    def _record_trial(self, trial_id: str, series: str, cell: Dict, replicate: int, valid: bool, invalid_reason: Optional[str]):
        """Record trial result to trials.csv."""
        trials_file = os.path.join(self.campaign_dir, "trials.csv")

        file_exists = os.path.exists(trials_file)

        with open(trials_file, 'a') as f:
            writer = csv.writer(f)

            if not file_exists:
                writer.writerow([
                    "trial_id", "series", "condition", "workload", "parameters",
                    "seed", "platform", "valid", "invalid_reason"
                ])

            writer.writerow([
                trial_id,
                series,
                cell["condition"],
                cell["workload"],
                json.dumps(cell, sort_keys=True),
                random.randint(0, 2**32 - 1),
                self.platform.__class__.__name__,
                valid,
                invalid_reason
            ])


import time
