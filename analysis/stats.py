"""Statistical analysis for Highlander experiments."""

import numpy as np
from scipy.stats import beta
from typing import List, Tuple
import pandas as pd


class StatisticsEngine:
    """Statistical analysis with bootstrap CI and safety bounds."""

    def __init__(self, seed: int = 2026):
        self.rng = np.random.Generator(np.random.PCG64(seed))

    def bootstrap_ci(
        self,
        data: np.ndarray,
        n_bootstrap: int = 10000,
        ci_level: float = 0.95
    ) -> Tuple[float, float, float, float, float]:
        """Compute bootstrap CI for mean, median, and p95.

        Returns (mean, mean_ci_lower, mean_ci_upper, median, p95).
        """
        bootstrap_means = np.array([
            np.mean(self.rng.choice(data, size=len(data), replace=True))
            for _ in range(n_bootstrap)
        ])

        bootstrap_medians = np.array([
            np.median(self.rng.choice(data, size=len(data), replace=True))
            for _ in range(n_bootstrap)
        ])

        bootstrap_p95 = np.array([
            np.percentile(self.rng.choice(data, size=len(data), replace=True), 95)
            for _ in range(n_bootstrap)
        ])

        alpha = (1 - ci_level) / 2
        mean_ci_lower = np.percentile(bootstrap_means, alpha * 100)
        mean_ci_upper = np.percentile(bootstrap_means, (1 - alpha) * 100)

        return (
            np.mean(data),
            mean_ci_lower,
            mean_ci_upper,
            np.median(data),
            np.percentile(data, 95)
        )

    def clopper_pearson_upper_bound(
        self,
        x: int,
        n: int,
        confidence: float = 0.95
    ) -> float:
        """Compute one-sided Clopper-Pearson upper bound for binomial proportion.

        Args:
            x: Number of successes (e.g., violations)
            n: Total number of trials
            confidence: Confidence level (default 0.95)

        Returns:
            Upper bound on the true proportion
        """
        if n == 0:
            return 0.0

        if x == n:
            return 1.0

        return beta.ppf(confidence, x + 1, n - x)

    def analyze_zero_count_safety(
        self,
        violations: int,
        total: int,
        confidence: float = 0.95
    ) -> dict:
        """Analyze zero-count safety outcomes.

        Returns dict with upper bound and whether it's below threshold.
        """
        upper_bound = self.clopper_pearson_upper_bound(violations, total, confidence)

        return {
            "violations": violations,
            "total": total,
            "upper_bound": upper_bound,
            "is_zero": violations == 0,
            "formula": f"scipy.stats.beta.ppf({confidence}, {violations + 1}, {total - violations})"
        }

    def compare_groups(
        self,
        group1: np.ndarray,
        group2: np.ndarray,
        n_bootstrap: int = 10000
    ) -> dict:
        """Compare two groups using bootstrap.

        Returns difference with CI.
        """
        bootstrap_diff = np.array([
            np.mean(self.rng.choice(group1, size=len(group1), replace=True)) -
            np.mean(self.rng.choice(group2, size=len(group2), replace=True))
            for _ in range(n_bootstrap)
        ])

        ci_lower = np.percentile(bootstrap_diff, 2.5)
        ci_upper = np.percentile(bootstrap_diff, 97.5)

        return {
            "mean_diff": np.mean(group1) - np.mean(group2),
            "ci_lower": ci_lower,
            "ci_upper": ci_upper,
            "significant": ci_lower > 0 or ci_upper < 0
        }
