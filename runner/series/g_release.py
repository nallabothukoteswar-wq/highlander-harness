"""Series G: Release overhead."""

from typing import Dict, List


class SeriesG:
    """Series G trials: Release overhead for different mechanisms."""

    @staticmethod
    def get_cells() -> List[Dict]:
        """Get all trial cells for Series G."""
        cells = []

        for mechanism in ["rolling", "blue-green", "canary"]:
            cells.append({
                "condition": "release",
                "mechanism": mechanism,
                "series": "G"
            })

        return cells

    @staticmethod
    def get_fault_config() -> Dict:
        """Get fault configuration for Series G."""
        return {
            "fault_type": "none",
            "trigger_type": "none",
        }
