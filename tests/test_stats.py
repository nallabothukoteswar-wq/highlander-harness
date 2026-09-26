"""Statistics tests for Highlander analysis."""

import numpy as np
from scipy.stats import beta
import pytest


def test_bootstrap_ci():
    """Test that bootstrap CI is deterministic with seed."""
    # Set seed for reproducibility
    rng = np.random.Generator(np.random.PCG64(2026))

    # Generate test data
    data = rng.normal(100, 15, 100)

    # Compute bootstrap CI
    n_bootstrap = 10000
    bootstrap_means = np.array([
        np.mean(rng.choice(data, size=len(data), replace=True))
        for _ in range(n_bootstrap)
    ])

    ci_lower = np.percentile(bootstrap_means, 2.5)
    ci_upper = np.percentile(bootstrap_means, 97.5)

    # Verify CI is reasonable
    assert ci_lower < ci_upper, "CI lower bound should be less than upper bound"
    assert 90 < ci_lower < 110, f"CI lower bound {ci_lower} should be around 100"
    assert 90 < ci_upper < 110, f"CI upper bound {ci_upper} should be around 100"

    # Test determinism: run again with same seed
    rng2 = np.random.Generator(np.random.PCG64(2026))
    data2 = rng2.normal(100, 15, 100)
    bootstrap_means2 = np.array([
        np.mean(rng2.choice(data2, size=len(data2), replace=True))
        for _ in range(n_bootstrap)
    ])
    ci_lower2 = np.percentile(bootstrap_means2, 2.5)
    ci_upper2 = np.percentile(bootstrap_means2, 97.5)

    assert ci_lower == ci_lower2, "Bootstrap should be deterministic with same seed"
    assert ci_upper == ci_upper2, "Bootstrap should be deterministic with same seed"


def test_clopper_pearson_upper_bound():
    """Test Clopper-Pearson upper bound for zero-count safety outcomes."""
    # Test case from spec: x = 0, n = 30
    x = 0
    n = 30
    upper_bound = beta.ppf(0.95, x + 1, n - x)
    expected = 1 - 0.05 ** (1 / n)

    assert abs(upper_bound - expected) < 0.0001, f"Expected {expected}, got {upper_bound}"
    assert abs(upper_bound - 0.0950) < 0.001, f"Expected ~0.0950, got {upper_bound}"

    # Test with some failures
    x = 1
    n = 30
    upper_bound = beta.ppf(0.95, x + 1, n - x)
    assert upper_bound > 0.0950, "Upper bound should be higher with some failures"

    # Test with all failures
    x = 30
    n = 30
    upper_bound = 1.0 if x == n else beta.ppf(0.95, x + 1, n - x)
    assert upper_bound == 1.0, "Upper bound should be 1.0 when all fail"


def test_percentile_bootstrap():
    """Test percentile bootstrap for median and p95."""
    rng = np.random.Generator(np.random.PCG64(2026))

    # Generate test data
    data = rng.normal(100, 15, 100)

    # Compute bootstrap CI for median
    n_bootstrap = 10000
    bootstrap_medians = np.array([
        np.median(rng.choice(data, size=len(data), replace=True))
        for _ in range(n_bootstrap)
    ])

    ci_lower = np.percentile(bootstrap_medians, 2.5)
    ci_upper = np.percentile(bootstrap_medians, 97.5)

    assert ci_lower < ci_upper, "CI lower bound should be less than upper bound"

    # Compute bootstrap CI for p95
    bootstrap_p95 = np.array([
        np.percentile(rng.choice(data, size=len(data), replace=True), 95)
            for _ in range(n_bootstrap)
    ])

    ci_lower_p95 = np.percentile(bootstrap_p95, 2.5)
    ci_upper_p95 = np.percentile(bootstrap_p95, 97.5)

    assert ci_lower_p95 < ci_upper_p95, "CI lower bound should be less than upper bound"
