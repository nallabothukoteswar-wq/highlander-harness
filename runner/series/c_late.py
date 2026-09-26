"""Series C: Late accepts (after_grant trigger)."""

from typing import Dict, List


class SeriesC:
    """Series C trials: Late accepts with after_grant trigger."""

    @staticmethod
    def get_cells() -> List[Dict]:
        """Get all trial cells for Series C."""
        cells = []

        for condition in ["C3", "C3r"]:
            for d in [0, 1, 5]:
                cells.append({
                    "condition": condition,
                    "workload": "ordered",
                    "d": d,
                    "series": "C"
                })

        return cells

    @staticmethod
    def get_fault_config() -> Dict:
        """Get fault configuration for Series C."""
        return {
            "fault_type": "pause",
            "trigger_type": "after_grant",  # Different trigger from Series A
            "victim": "worker-0",
        }
