"""Testing statistical helper functions for the design matrix generator"""

import numbers

import numpy as np
import pytest

from fmu.tools.sensitivities import design_distributions as dists

# pylint: disable=protected-access


def test_check_dist_params_normal():
    """Test normal dist param checker"""
    # First element in returned 2-tuple is True or False:
    assert not dists._check_dist_params_normal([])[0]
    assert not dists._check_dist_params_normal(())[0]

    assert not dists._check_dist_params_normal([0])[0]
    assert not dists._check_dist_params_normal([0, 0, 0])[0]
    assert not dists._check_dist_params_normal([0, 0, 0, 0, 0])[0]

    assert not dists._check_dist_params_normal(["mean", "mu"])[0]

    assert dists._check_dist_params_normal([0, 1])[0]
    assert not dists._check_dist_params_normal([0, -1])[0]
    assert dists._check_dist_params_normal([0, 0])[0]  # edge case

    # Truncated
    assert dists._check_dist_params_normal([0, 1, 0, 1])[0]


def test_check_dist_params_lognormal():
    """Test lognormal dist param checker"""
    assert not dists._check_dist_params_lognormal([])[0]
    assert not dists._check_dist_params_lognormal(())[0]

    assert not dists._check_dist_params_lognormal([0])[0]
    assert not dists._check_dist_params_lognormal([0, 0, 0])[0]

    assert not dists._check_dist_params_lognormal(["mean", "mu"])[0]

    assert dists._check_dist_params_lognormal([0, 1])[0]
    assert not dists._check_dist_params_lognormal([0, -1])[0]

    assert dists._check_dist_params_lognormal([0, 0])[0]  # edge case


def test_check_dist_params_uniform():
    """Test lognormal dist param checker"""
    assert not dists._check_dist_params_uniform([])[0]
    assert not dists._check_dist_params_uniform(())[0]

    assert not dists._check_dist_params_uniform([0])[0]
    assert not dists._check_dist_params_uniform([0, 0, 0])[0]

    assert not dists._check_dist_params_uniform(["mean", "mu"])[0]

    assert dists._check_dist_params_uniform([0, 1])[0]
    assert not dists._check_dist_params_uniform([0, -1])[0]

    assert dists._check_dist_params_uniform([0, 0])[0]  # edge case


def test_check_dist_params_triang():
    """Test triang dist param checker"""
    assert not dists._check_dist_params_triang([])[0]
    assert not dists._check_dist_params_triang(())[0]

    assert not dists._check_dist_params_triang([0])[0]
    assert not dists._check_dist_params_triang([0, 0])[0]
    assert not dists._check_dist_params_triang([0, 0, 0, 0])[0]

    assert not dists._check_dist_params_triang(["foo", "bar", 0])[0]

    assert dists._check_dist_params_triang([0, 1, 2])[0]
    assert not dists._check_dist_params_triang([0, -1, -4])[0]
    assert not dists._check_dist_params_triang([0, 1000, 999.99])[0]

    assert dists._check_dist_params_triang([0, 0, 0])[0]  # edge case


def test_check_dist_params_pert():
    """Test pert dist param checker"""
    assert not dists._check_dist_params_pert([])[0]
    assert not dists._check_dist_params_pert(())[0]

    assert not dists._check_dist_params_pert([0])[0]
    assert not dists._check_dist_params_pert([0, 0])[0]
    assert not dists._check_dist_params_pert([0, 0, 0, 0, 0])[0]

    assert not dists._check_dist_params_pert(["foo", "bar", 0])[0]

    assert dists._check_dist_params_pert([0, 1, 2])[0]
    assert not dists._check_dist_params_pert([0, -1, -4])[0]
    assert not dists._check_dist_params_pert([0, 1000, 999.99])[0]
    assert dists._check_dist_params_pert([0, 1000, 1000, 999.99])[0]

    assert dists._check_dist_params_pert([0, 0, 0])[0]  # edge case


def test_check_dist_params_logunif():
    """Test logunif dist param checker"""
    assert not dists._check_dist_params_logunif([])[0]
    assert not dists._check_dist_params_logunif(())[0]

    assert not dists._check_dist_params_logunif([0])[0]
    assert not dists._check_dist_params_logunif([0, 0, 0])[0]

    assert not dists._check_dist_params_logunif(["foo", "bar"])[0]

    assert not dists._check_dist_params_logunif([0, 1])[0]
    assert dists._check_dist_params_logunif([0.00001, 1])[0]
    assert dists._check_dist_params_logunif([0.0000001, 0.00001])[0]
    assert not dists._check_dist_params_logunif([0.00001, 0.0000001])[0]

    assert dists._check_dist_params_logunif([1, 1])[0]


@pytest.mark.parametrize(
    "dist_params",
    [
        [10.0, 2.0],  # normal distribution params [mean, std_dev]
        [10.0, 2.0, 5.0, 15.0],  # truncated normal params [mean, std_dev, min, max]
    ],
)
def test_draw_values_normal_correlation(dist_params):
    # Create two sets of correlated normal scores
    rng = np.random.default_rng()
    correlation = 0.8
    n_samples = 1000

    # Generate correlated standard normal variables
    cov_matrix = [[1.0, correlation], [correlation, 1.0]]
    normal_scores = rng.multivariate_normal([0, 0], cov_matrix, size=n_samples)

    # Draw values using the correlated normal scores
    values1 = dists.draw_values_normal(dist_params, n_samples, normal_scores[:, 0])
    values2 = dists.draw_values_normal(dist_params, n_samples, normal_scores[:, 1])

    # Calculate the correlation between the transformed variables
    actual_correlation = np.corrcoef(values1, values2)[0, 1]

    # Test if the correlation is close to the expected value
    assert abs(actual_correlation - correlation) < 0.1


def test_draw_values_normal():
    """Test drawing values"""
    values = dists.draw_values_normal([0, 1], 10)
    assert len(values) == 10
    assert all(isinstance(value, numbers.Number) for value in values)

    values = dists.draw_values_normal([0, 10, -1, 2], 50)
    assert all(-1 <= value <= 2 for value in values)


def test_draw_values_lognormal():
    """Test drawing lognormal values"""
    assert not dists.draw_values_lognormal([100, 10], 0).size
    values = dists.draw_values_lognormal([100, 10], 10)
    assert len(values) == 10
    assert all(isinstance(value, numbers.Number) for value in values)
    assert all(value > 0 for value in values)


def test_draw_values_uniform():
    """Test drawing uniform values"""
    assert not dists.draw_values_uniform([10, 100], 0).size

    values = dists.draw_values_uniform([10, 100], 20)
    assert len(values) == 20
    assert all(isinstance(value, numbers.Number) for value in values)
    assert all(10 <= value <= 100 for value in values)


def test_draw_values_triangular():
    """Test drawing triangular values"""
    assert not dists.draw_values_triangular([10, 100, 1000], 0).size
    with pytest.raises(ValueError):
        assert not dists.draw_values_triangular([10, 100, 1000], -1)

    with pytest.raises(TypeError):
        assert not dists.draw_values_triangular([10, 100, 1000], "somestring")

    values = dists.draw_values_triangular([10, 100, 1000], 15)
    assert len(values) == 15
    assert all(isinstance(value, numbers.Number) for value in values)
    assert all(10 <= value <= 1000 for value in values)


def test_draw_values_pert():
    """Test drawing pert values"""
    assert not dists.draw_values_pert([10, 50, 100], 0).size

    values = dists.draw_values_pert([10, 50, 100], 20)
    assert len(values) == 20
    assert all(isinstance(value, numbers.Number) for value in values)
    assert all(10 <= value <= 100 for value in values)


def test_draw_values_loguniform():
    """Test drawing loguniform values"""
    assert not dists.draw_values_uniform([10, 100], 0).size

    values = dists.draw_values_uniform([10, 100], 20)
    assert len(values) == 20
    assert all(isinstance(value, numbers.Number) for value in values)
    assert all(10 <= value <= 100 for value in values)


def test_that_discrete_matches_with_expected_probabilities():
    n_samples = 20
    outcomes = ["a", "b", "c"]
    probabilities = "0.2,0.3,0.5"
    dist_params = [",".join(outcomes), probabilities]
    status, values = dists.sample_discrete(dist_params, n_samples)
    assert status

    from collections import Counter

    counts = Counter(values)
    actual_fractions = [counts[outcome] / n_samples for outcome in outcomes]
    expected_fractions = [float(p) for p in probabilities.split(",")]

    tolerance = 0.02
    for expected, actual in zip(expected_fractions, actual_fractions):
        assert (
            abs(expected - actual) < tolerance
        ), f"Expected fraction {expected:.3f} but got {actual:.3f}"


def test_that_discrete_raises_errors():
    # Add tests for invalid probabilities
    outcomes = ["a", "b"]

    dist_params = [",".join(outcomes)]
    # Test negative samples
    with pytest.raises(ValueError, match="numreal must be a positive integer"):
        _ = dists.sample_discrete(dist_params, -1)[1]

    # Test probabilities that don't sum to 1
    with pytest.raises(ValueError, match="Probabilities must sum to 1"):
        dist_params = [",".join(outcomes), "0.3,0.3"]
        dists.sample_discrete(dist_params, 10)

    # Test probabilities outside [0,1] range
    with pytest.raises(ValueError, match="All probabilities must be between 0 and 1"):
        dist_params = [",".join(outcomes), "1.2,-0.2"]
        dists.sample_discrete(dist_params, 10)

    # Test non-float weights
    with pytest.raises(
        ValueError, match="All weights must be valid floating point numbers"
    ):
        dist_params = [",".join(outcomes), "0.5,abc"]
        dists.sample_discrete(dist_params, 10)


def test_sample_discrete():
    # Test uniform distribution
    outcomes = ["foo", "bar.com"]
    dist_params = [",".join(outcomes)]
    status, values = dists.sample_discrete(dist_params, 10)
    assert status
    assert all(value in outcomes for value in values)

    # Test zero samples
    status, values = dists.sample_discrete(dist_params, 0)
    assert status
    assert len(values) == 0

    # Test non-uniform distribution with extreme probabilities
    dist_params = [",".join(outcomes), "0,1"]
    status, values = dists.sample_discrete(dist_params, 10)
    assert "foo" not in values


def test_draw_values():
    """Test the wrapper function for drawing values"""

    values = dists.draw_values("unif", [0, 1], 10)
    assert len(values) == 10
    assert all(isinstance(value, numbers.Number) for value in values)
    assert all(0 <= value <= 1 for value in values)

    values = dists.draw_values("UNIF", [0, 1], 10)
    assert len(values) == 10

    values = dists.draw_values("unifORM", [0, 1], 10)
    assert len(values) == 10

    values = dists.draw_values("UnifORMgarbagestillworks", [0, 1], 10)
    assert len(values) == 10

    with pytest.raises(ValueError):
        dists.draw_values("non-existing-distribution", [0, 10], 100)

    values = dists.draw_values("NORMAL", [0, 1], 10)
    assert len(values) == 10

    values = dists.draw_values("LOGNORMAL", [0.1, 1], 10)
    assert len(values) == 10

    values = dists.draw_values("Pert", [0.1, 1, 10], 10)
    assert len(values) == 10

    values = dists.draw_values("triangular", [0.1, 1, 10], 10)
    assert len(values) == 10

    values = dists.draw_values("logunif", [0.1, 1], 10)
    assert len(values) == 10
