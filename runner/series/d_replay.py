"""Series D: Ambiguous retry (lost acks, no pause)."""

from typing import Dict, List


class SeriesD:
    """Series D trials: Ambiguous retry with lost acknowledgments."""

    @staticmethod
    def get_cells() -> List[Dict]:
        """Get all trial cells for Series D."""
        cells = []

        for condition in ["C2f", "C3", "C4"]:
            cells.append({
                "condition": condition,
                "workload": "dup",
                "lost_ack_rate": 0.05,
                "retry_delay_s": 0.05,
                "series": "D"
            })

        return cells

    @staticmethod
    def get_fault_config() -> Dict:
        """Get fault configuration for Series D."""
        return {
            "fault_type": "none",  # No pause fault, only lost acks
            "trigger_type": "none",
        }
