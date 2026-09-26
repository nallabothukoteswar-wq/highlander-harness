"""Kind platform implementation for paper testbed."""

import subprocess
import time
from typing import List, Optional
import signal


class KindPlatform:
    """Kind platform: Kubernetes cluster with in-cluster PostgreSQL and worker pods."""

    def __init__(self):
        self.cluster_name = "highlander"

    def setup(self):
        """Set up the kind platform."""
        # Create kind cluster
        self._create_cluster()

        # Apply PostgreSQL manifest
        self._apply_postgres()

        # Wait for PostgreSQL to be ready
        self._wait_for_postgres()

        # Run schema migrations
        self._run_migrations()

    def _create_cluster(self):
        """Create kind cluster."""
        cmd = [
            "kind", "create", "cluster",
            "--name", self.cluster_name,
            "--config", "k8s/kind-config.yaml"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Failed to create kind cluster: {result.stderr}")

    def _apply_postgres(self):
        """Apply PostgreSQL StatefulSet."""
        cmd = ["kubectl", "apply", "-f", "k8s/postgres.yaml"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Failed to apply PostgreSQL: {result.stderr}")

    def _wait_for_postgres(self, timeout: int = 300):
        """Wait for PostgreSQL to be ready."""
        cmd = [
            "kubectl", "wait",
            "--for=condition=ready",
            "pod", "-l", "app=postgres",
            "--timeout", f"{timeout}s"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"PostgreSQL did not become ready: {result.stderr}")

    def _run_migrations(self):
        """Run SQL schema migrations."""
        # Port-forward to PostgreSQL
        port_forward = subprocess.Popen(
            ["kubectl", "port-forward", "svc/postgres", "5432:5432"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        time.sleep(2)  # Wait for port-forward to establish

        # Run migrations (this would use psycopg like in local platform)
        # For now, just cleanup
        port_forward.terminate()
        port_forward.wait()

    def start_workers(self, trial_id: str, condition: str, workload: str, num_workers: int = 3) -> List[str]:
        """Start worker pods."""
        # Apply worker StatefulSet
        # This would create/patch the worker StatefulSet with trial-specific config
        # For now, return placeholder pod names
        return [f"worker-{i}" for i in range(num_workers)]

    def stop_workers(self, worker_ids: List[str]):
        """Stop worker pods."""
        # Delete worker pods
        for worker_id in worker_ids:
            cmd = ["kubectl", "delete", "pod", worker_id]
            subprocess.run(cmd, capture_output=True)

    def signal_worker(self, worker_id: str, signal: signal.Signals):
        """Send a signal to a worker process via helper container."""
        # Execute helper script in helper container
        cmd = [
            "kubectl", "exec", "-c", "helper", worker_id,
            "--", f"/helper/{signal.name.lower()}.sh"
        ]
        subprocess.run(cmd, capture_output=True)

    def verify_worker_stopped(self, worker_id: str) -> bool:
        """Verify that a worker process is in stopped state."""
        # Execute verify_stopped.sh in helper container
        cmd = [
            "kubectl", "exec", "-c", "helper", worker_id,
            "--", "/helper/verify_stopped.sh"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.returncode == 0

    def restart_worker(self, worker_id: str) -> str:
        """Restart a worker pod (delete and wait for recreation)."""
        # Delete pod (StatefulSet will recreate it)
        cmd = ["kubectl", "delete", "pod", worker_id]
        subprocess.run(cmd, capture_output=True)

        # Wait for pod to be ready
        cmd = [
            "kubectl", "wait",
            "--for=condition=ready",
            "pod", worker_id,
            "--timeout", "60s"
        ]
        subprocess.run(cmd, capture_output=True)

        return worker_id

    def cleanup(self):
        """Clean up the kind platform."""
        # Delete kind cluster
        cmd = ["kind", "delete", "cluster", "--name", self.cluster_name]
        subprocess.run(cmd, capture_output=True)

    def get_db_connection(self, user: str = "worker_rw", password: str = "worker_password"):
        """Get a database connection (via port-forward)."""
        # This would set up port-forward and return connection
        # For now, return None as placeholder
        return None
