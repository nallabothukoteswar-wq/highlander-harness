"""Series A: Main ablation (pause fault)."""

from typing import Dict, List


class SeriesA:
    """Series A trials: Main ablation with pause fault."""

    CONDITIONS = ["C1", "C1u", "C1v", "C2", "C2f", "C3", "C3r", "C4"]
    WORKLOADS = ["dup", "ordered"]

    @staticmethod
    def get_cells() -> List[Dict]:
        """Get all trial cells for Series A."""
        cells = []

        for condition in SeriesA.CONDITIONS:
            for workload in SeriesA.WORKLOADS:
                # C1v only applies to ordered workload
                if condition == "C1v" and workload != "ordered":
                    continue

                cells.append({
                    "condition": condition,
                    "workload": workload,
                    "series": "A"
                })

        return cells

    @staticmethod
    def get_fault_config() -> Dict:
        """Get fault configuration for Series A."""
        return {
            "fault_type": "pause",
            "trigger_type": "after_first_accept",
            "victim": "worker-0",
            "resume_delay": 1.0,
        }
