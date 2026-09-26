"""Series E: Takeover (SIGKILL, no lease release)."""

from typing import Dict, List


class SeriesE:
    """Series E trials: Takeover with SIGKILL fault."""

    @staticmethod
    def get_cells() -> List[Dict]:
        """Get all trial cells for Series E."""
        cells = []

        for L in [5, 10, 15, 30]:
            cells.append({
                "condition": "C3",
                "workload": "dup",
                "L": L,
                "continuous_source": True,
                "series": "E"
            })

        return cells

    @staticmethod
    def get_fault_config() -> Dict:
        """Get fault configuration for Series E."""
        return {
            "fault_type": "kill",
            "trigger_type": "random_in_renewal_interval",
            "victim": "current_owner",
        }
