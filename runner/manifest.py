"""Manifest recording for Highlander experiments."""

import os
import json
import subprocess
import platform
from datetime import datetime


class ManifestRecorder:
    """Records experiment manifest with system information."""

    def __init__(self, campaign_dir: str):
        self.campaign_dir = campaign_dir
        self.manifest_file = os.path.join(campaign_dir, "manifest.json")
        self.manifest = {}

    def record_start(self):
        """Record manifest at campaign start."""
        self.manifest = {
            "start_time": datetime.now().isoformat(),
            "end_time": None,
            "host": self._get_host_info(),
            "docker": self._get_docker_info(),
            "kubernetes": self._get_kubernetes_info(),
            "images": self._get_image_info(),
            "postgres": self._get_postgres_info(),
            "python": self._get_python_info(),
            "go": self._get_go_info(),
            "git": self._get_git_info(),
            "config": self._get_config_info(),
        }

        self._save_manifest()

    def record_end(self):
        """Record manifest at campaign end."""
        self.manifest["end_time"] = datetime.now().isoformat()
        self._save_manifest()

    def _get_host_info(self) -> dict:
        """Get host system information."""
        return {
            "cpu_model": platform.processor(),
            "cpu_cores": os.cpu_count(),
            "ram_gb": None,  # Would need psutil
            "kernel": platform.release(),
            "os": platform.system(),
            "os_version": platform.version(),
        }

    def _get_docker_info(self) -> dict:
        """Get Docker version."""
        try:
            result = subprocess.run(["docker", "--version"], capture_output=True, text=True)
            return {"version": result.stdout.strip()}
        except FileNotFoundError:
            return {"version": "not installed"}

    def _get_kubernetes_info(self) -> dict:
        """Get Kubernetes information."""
        info = {}

        try:
            result = subprocess.run(["kubectl", "version", "--client"], capture_output=True, text=True)
            info["kubectl_version"] = result.stdout.strip()
        except FileNotFoundError:
            info["kubectl_version"] = "not installed"

        try:
            result = subprocess.run(["kind", "version"], capture_output=True, text=True)
            info["kind_version"] = result.stdout.strip()
        except FileNotFoundError:
            info["kind_version"] = "not installed"

        return info

    def _get_image_info(self) -> dict:
        """Get Docker image digests."""
        # This would get the actual digests from the running containers
        return {
            "postgres": "postgres:16",  # Would be actual digest
            "worker": "highlander-worker:latest",  # Would be actual digest
        }

    def _get_postgres_info(self) -> dict:
        """Get PostgreSQL version and settings."""
        # This would connect to PostgreSQL and get version
        return {
            "version": "16",
            "settings": {
                "max_connections": 100,
                "shared_buffers": "128MB",
                # ... other settings
            }
        }

    def _get_python_info(self) -> dict:
        """Get Python version."""
        return {
            "version": platform.python_version(),
        }

    def _get_go_info(self) -> dict:
        """Get Go version."""
        try:
            result = subprocess.run(["go", "version"], capture_output=True, text=True)
            return {"version": result.stdout.strip()}
        except FileNotFoundError:
            return {"version": "not installed"}

    def _get_git_info(self) -> dict:
        """Get git commit and dirty flag."""
        try:
            result = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True)
            commit = result.stdout.strip()

            result = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True)
            dirty = len(result.stdout.strip()) > 0

            return {"commit": commit, "dirty": dirty}
        except FileNotFoundError:
            return {"commit": "unknown", "dirty": False}

    def _get_config_info(self) -> dict:
        """Get experiment configuration."""
        # This would capture the actual config used
        return {
            "num_workers": 3,
            "num_items": 1000,
            "batch_size": 10,
            "lease_secs": 10,
            # ... other config
        }

    def _save_manifest(self):
        """Save manifest to file."""
        with open(self.manifest_file, 'w') as f:
            json.dump(self.manifest, f, indent=2)
