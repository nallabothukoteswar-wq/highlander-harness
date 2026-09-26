"""Series B: Exposure sweep."""

from typing import Dict, List


class SeriesB:
    """Series B trials: Exposure sweep with varying batch size and resume delay."""

    @staticmethod
    def get_cells() -> List[Dict]:
        """Get all trial cells for Series B."""
        cells = []

        # dup workload: C1, C2
        for condition in ["C1", "C2"]:
            for b in [1, 10, 100]:
                for d in [0, 1, 5]:
                    cells.append({
                        "condition": condition,
                        "workload": "dup",
                        "b": b,
                        "d": d,
                        "series": "B"
                    })

        # ordered workload: C1, C1u, C2
        for condition in ["C1", "C1u", "C2"]:
            for b in [1, 10, 100]:
                for d in [0, 1, 5]:
                    cells.append({
                        "condition": condition,
                        "workload": "ordered",
                        "b": b,
                        "d": d,
                        "series": "B"
                    })

        return cells

    @staticmethod
    def get_fault_config() -> Dict:
        """Get fault configuration for Series B."""
        return {
            "fault_type": "pause",
            "trigger_type": "after_first_accept",
            "victim": "worker-0",
        }
