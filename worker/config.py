"""Worker configuration parameters."""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class WorkerConfig:
    """Configuration for a worker process."""

    # Database connection
    db_host: str = os.getenv("DB_HOST", "localhost")
    db_port: int = int(os.getenv("DB_PORT", "5432"))
    db_name: str = os.getenv("DB_NAME", "highlander")
    db_user: str = os.getenv("DB_USER", "worker_rw")
    db_password: str = os.getenv("DB_PASSWORD", "worker_password")

    # For remote sink (C3r)
    rsink_db_host: str = os.getenv("RSINK_DB_HOST", "localhost")
    rsink_db_port: int = int(os.getenv("RSINK_DB_PORT", "5432"))
    rsink_db_name: str = os.getenv("RSINK_DB_NAME", "highlander")
    rsink_db_user: str = os.getenv("RSINK_DB_USER", "rsink_rw")
    rsink_db_password: str = os.getenv("RSINK_DB_PASSWORD", "rsink_password")

    # Worker identity
    worker_id: str = os.getenv("WORKER_ID", "worker-0")
    trial_id: str = os.getenv("TRIAL_ID", "trial-0")

    # Experiment parameters
    num_workers: int = int(os.getenv("NUM_WORKERS", "3"))
    num_items: int = int(os.getenv("NUM_ITEMS", "1000"))
    batch_size: int = int(os.getenv("BATCH_SIZE", "10"))
    lease_secs: float = float(os.getenv("LEASE_SECS", "10"))
    acquire_interval: float = float(os.getenv("ACQUIRE_INTERVAL", "0.5"))
    safety_delta: float = float(os.getenv("SAFETY_DELTA", "0.5"))
    visibility_timeout: float = float(os.getenv("VISIBILITY_TIMEOUT", "10"))
    prep_cpu_ms: float = float(os.getenv("PREP_CPU_MS", "2"))
    throttle_per_sec: int = int(os.getenv("THROTTLE_PER_SEC", "100"))
    warmup_items: int = int(os.getenv("WARMUP_ITEMS", "200"))

    # Fault parameters
    resume_delay: float = float(os.getenv("RESUME_DELAY", "1"))
    lost_ack_rate: float = float(os.getenv("LOST_ACK_RATE", "0"))

    # Condition and workload
    condition: str = os.getenv("CONDITION", "C1")
    workload: str = os.getenv("WORKLOAD", "dup")
    stream_id: str = os.getenv("STREAM_ID", "S1")

    # Platform
    platform: str = os.getenv("PLATFORM", "local")

    # For local platform: shared directory path
    shared_dir: Optional[str] = os.getenv("SHARED_DIR")

    @classmethod
    def from_env(cls) -> "WorkerConfig":
        """Create config from environment variables."""
        return cls()
