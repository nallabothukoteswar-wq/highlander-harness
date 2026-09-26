"""Local platform implementation for fast iteration."""

import os
import subprocess
import signal
import time
import uuid
from typing import List, Optional
import psycopg


class LocalPlatform:
    """Local platform: PostgreSQL in Docker, workers as host processes."""

    def __init__(self):
        self.postgres_container = None
        self.worker_processes = {}

    def setup(self):
        """Set up the local platform."""
        # Start PostgreSQL in Docker
        self._start_postgres()

        # Wait for PostgreSQL to be ready
        self._wait_for_postgres()

        # Run schema migrations
        self._run_migrations()

    def _start_postgres(self):
        """Start PostgreSQL container."""
        cmd = [
            "docker", "run", "-d",
            "--name", "highlander-postgres",
            "-e", "POSTGRES_DB=highlander",
            "-e", "POSTGRES_USER=worker_rw",
            "-e", "POSTGRES_PASSWORD=worker_password",
            "-e", "POSTGRES_USER_REMOTE=rsink_rw",
            "-e", "POSTGRES_PASSWORD_REMOTE=rsink_password",
            "-p", "5432:5432",
            "postgres:16"
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Failed to start PostgreSQL: {result.stderr}")

        self.postgres_container = result.stdout.strip()

    def _wait_for_postgres(self, timeout: int = 30):
        """Wait for PostgreSQL to be ready."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                conn = psycopg.connect(
                    host="localhost",
                    port=5432,
                    dbname="highlander",
                    user="worker_rw",
                    password="worker_password",
                    autocommit=True
                )
                conn.close()
                return
            except Exception:
                time.sleep(1)

        raise RuntimeError("PostgreSQL did not become ready in time")

    def _run_migrations(self):
        """Run SQL schema migrations."""
        conn = psycopg.connect(
            host="localhost",
            port=5432,
            dbname="highlander",
            user="worker_rw",
            password="worker_password",
            autocommit=True
        )

        sql_dir = os.path.join(os.path.dirname(__file__), '..', 'sql')
        sql_files = [
            '00_roles.sql',
            '01_schemas.sql',
            '02_ownership.sql',
            '03_queue.sql',
            '04_sinks_colocated.sql',
            '05_sink_remote.sql',
            '06_control.sql',
            '07_views.sql',
            '08_sink_functions.sql'
        ]

        for sql_file in sql_files:
            filepath = os.path.join(sql_dir, sql_file)
            with open(filepath, 'r') as f:
                sql_content = f.read()
                conn.execute(sql_content)

        conn.close()

    def start_workers(self, trial_id: str, condition: str, workload: str, num_workers: int = 3) -> List[int]:
        """Start worker processes."""
        worker_pids = []

        for i in range(num_workers):
            worker_id = f"worker-{i}"
            env = os.environ.copy()
            env.update({
                "TRIAL_ID": trial_id,
                "CONDITION": condition,
                "WORKLOAD": workload,
                "WORKER_ID": worker_id,
                "NUM_WORKERS": str(num_workers),
                "PLATFORM": "local",
                "DB_HOST": "localhost",
                "DB_PORT": "5432",
                "DB_NAME": "highlander",
                "DB_USER": "worker_rw",
                "DB_PASSWORD": "worker_password",
                "RSINK_DB_HOST": "localhost",
                "RSINK_DB_PORT": "5432",
                "RSINK_DB_NAME": "highlander",
                "RSINK_DB_USER": "rsink_rw",
                "RSINK_DB_PASSWORD": "rsink_password",
            })

            # Start worker process
            proc = subprocess.Popen(
                ["python3", "-m", "worker"],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )

            worker_pids.append(proc.pid)
            self.worker_processes[worker_id] = proc

        return worker_pids

    def stop_workers(self, worker_ids: List[str]):
        """Stop worker processes."""
        for worker_id in worker_ids:
            if worker_id in self.worker_processes:
                proc = self.worker_processes[worker_id]
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()
                del self.worker_processes[worker_id]

    def signal_worker(self, worker_id: str, signal: signal.Signals):
        """Send a signal to a worker process."""
        if worker_id in self.worker_processes:
            proc = self.worker_processes[worker_id]
            proc.send_signal(signal)

    def verify_worker_stopped(self, worker_id: str) -> bool:
        """Verify that a worker process is in stopped state."""
        if worker_id not in self.worker_processes:
            return False

        proc = self.worker_processes[worker_id]
        try:
            with open(f"/proc/{proc.pid}/status", "r") as f:
                content = f.read()
                return "State:\tT" in content
        except (FileNotFoundError, IOError):
            return False

    def restart_worker(self, worker_id: str) -> int:
        """Restart a worker process with a new incarnation."""
        if worker_id in self.worker_processes:
            proc = self.worker_processes[worker_id]
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
            del self.worker_processes[worker_id]

        # Re-start the worker (this would need the original configuration)
        # For now, return None as this needs more context
        return None

    def cleanup(self):
        """Clean up the local platform."""
        # Stop all workers
        for worker_id in list(self.worker_processes.keys()):
            self.stop_workers([worker_id])

        # Stop PostgreSQL container
        if self.postgres_container:
            subprocess.run(["docker", "stop", self.postgres_container], capture_output=True)
            subprocess.run(["docker", "rm", self.postgres_container], capture_output=True)

    def get_db_connection(self, user: str = "worker_rw", password: str = "worker_password") -> psycopg.Connection:
        """Get a database connection."""
        return psycopg.connect(
            host="localhost",
            port=5432,
            dbname="highlander",
            user=user,
            password=password,
            autocommit=True
        )
