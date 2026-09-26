"""Series F: Serving capacity."""

from typing import Dict, List


class SeriesF:
    """Series F trials: Serving capacity at different replica counts."""

    @staticmethod
    def get_cells() -> List[Dict]:
        """Get all trial cells for Series F."""
        cells = []

        # Calibration would determine μ first
        # Then test at n_req - 1 and n_req replicas
        for n_replicas in [6, 7]:
            cells.append({
                "condition": "serving",
                "n_replicas": n_replicas,
                "lambda_peak": "5μ",  # Would be actual value after calibration
                "series": "F"
            })

        return cells

    @staticmethod
    def get_fault_config() -> Dict:
        """Get fault configuration for Series F."""
        return {
            "fault_type": "none",
            "trigger_type": "none",
        }
