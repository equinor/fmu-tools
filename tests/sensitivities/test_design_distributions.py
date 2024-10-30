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
    rng = np.random.RandomState()
    correlation = 0.8
    n_samples = 1000

    # Generate correlated standard normal variables
    cov_matrix = [[1.0, correlation], [correlation, 1.0]]
    normal_scores = rng.multivariate_normal([0, 0], cov_matrix, size=n_samples)

    # Draw values using the correlated normal scores
    values1 = dists.draw_values_normal(dist_params, n_samples, rng, normal_scores[:, 0])
    values2 = dists.draw_values_normal(dist_params, n_samples, rng, normal_scores[:, 1])

    # Calculate the correlation between the transformed variables
    actual_correlation = np.corrcoef(values1, values2)[0, 1]

    # Test if the correlation is close to the expected value
    assert abs(actual_correlation - correlation) < 0.1


def test_draw_values_normal():
    rng = np.random.RandomState()
    values = dists.draw_values_normal([0, 1], 10, rng)
    assert len(values) == 10
    assert all(isinstance(value, numbers.Number) for value in values)

    with pytest.raises(
        ValueError,
        match=(
            "Normal distribution must have 2 parameters or 4 for a truncated normal, "
            "but had 3 parameters."
        ),
    ):
        values = dists.draw_values_normal([0, 1, 2], 10, rng)

    with pytest.raises(
        ValueError, match="Parameters for normal distribution must be numbers."
    ):
        values = dists.draw_values_normal([0, "b"], 10, rng)

    with pytest.raises(
        ValueError, match="Stddev for normal distribution must be >= 0."
    ):
        values = dists.draw_values_normal([0, -1], 10, rng)

    values = dists.draw_values_normal([0, 10, -1, 2], 50, rng)
    assert all(-1 <= value <= 2 for value in values)


def test_draw_values_lognormal():
    rng = np.random.RandomState()
    assert not dists.draw_values_lognormal([100, 10], 0, rng).size
    values = dists.draw_values_lognormal([100, 10], 10, rng)
    assert len(values) == 10
    assert all(isinstance(value, numbers.Number) for value in values)
    assert all(value > 0 for value in values)


def test_draw_uniform_with_correlation():
    rng = np.random.RandomState()
    correlation = 0.6
    n_samples = 1000

    cov_matrix = [[1.0, correlation], [correlation, 1.0]]
    normal_scores = rng.multivariate_normal([0, 0], cov_matrix, size=n_samples)

    values1 = dists.draw_values_uniform([0, 100], n_samples, rng, normal_scores[:, 0])
    values2 = dists.draw_values_uniform([10, 50], n_samples, rng, normal_scores[:, 1])

    actual_correlation = np.corrcoef(values1, values2)[0, 1]
    assert (actual_correlation - correlation) < 0.1


def test_draw_values_uniform():
    rng = np.random.RandomState()

    values = dists.draw_values_uniform([10, 100], 0, rng)
    assert len(values) == 0

    values = dists.draw_values_uniform([10, 100], 20, rng)
    assert len(values) == 20
    assert all(isinstance(value, numbers.Number) for value in values)
    assert all(10 <= value <= 100 for value in values)

    with pytest.raises(
        ValueError,
        match="Uniform distribution must have 2 parameters, but had 3 parameters.",
    ):
        values = dists.draw_values_uniform([10, 50, 100], 10, rng)

    with pytest.raises(
        ValueError, match="Uniform distribution must have dist_param2 >= dist_param1"
    ):
        values = dists.draw_values_uniform([50, 10], 10, rng)

    with pytest.raises(
        ValueError, match="Parameters for uniform distribution must be numbers."
    ):
        values = dists.draw_values_uniform(["a", 10], 10, rng)

    with pytest.raises(ValueError, match="numreal must be a positive integer"):
        values = dists.draw_values_uniform([10, 50], -10, rng)


def test_draw_values_triangular():
    rng = np.random.RandomState()

    assert not dists.draw_values_triangular([10, 100, 1000], 0, rng).size
    with pytest.raises(ValueError):
        assert not dists.draw_values_triangular([10, 100, 1000], -1, rng)

    with pytest.raises(TypeError):
        assert not dists.draw_values_triangular([10, 100, 1000], "somestring", rng)

    values = dists.draw_values_triangular([10, 100, 1000], 15, rng)
    assert len(values) == 15
    assert all(isinstance(value, numbers.Number) for value in values)
    assert all(10 <= value <= 1000 for value in values)


def test_draw_values_pert():
    rng = np.random.RandomState()

    assert not dists.draw_values_pert([10, 50, 100], 0, rng).size

    values = dists.draw_values_pert([10, 50, 100], 20, rng)
    assert len(values) == 20
    assert all(isinstance(value, numbers.Number) for value in values)
    assert all(10 <= value <= 100 for value in values)


def test_draw_values_loguniform():
    rng = np.random.RandomState()

    assert not dists.draw_values_uniform([10, 100], 0, rng).size

    values = dists.draw_values_uniform([10, 100], 20, rng)
    assert len(values) == 20
    assert all(isinstance(value, numbers.Number) for value in values)
    assert all(10 <= value <= 100 for value in values)


def test_sample_discrete():
    rng = np.random.RandomState()

    outcomes = ["foo", "bar.com"]

    # NB: return type from sample_discrete is different from the others,
    # it returns a 3-tuple with the values in the second element.
    values = dists.sample_discrete([",".join(outcomes)], 10, rng)[1]
    assert all(value in outcomes for value in values)

    assert not dists.sample_discrete([",".join(outcomes)], 0, rng)[1].size
    with pytest.raises(ValueError):
        # pylint: disable=expression-not-assigned
        dists.sample_discrete([",".join(outcomes)], -1, rng)[1]

    assert "foo" not in dists.sample_discrete([",".join(outcomes), "0,1"], 10, rng)[1]


def test_draw_values():
    """Test the wrapper function for drawing values"""
    rng = np.random.RandomState()

    values = dists.draw_values("unif", [0, 1], 10, rng)
    assert len(values) == 10
    assert all(isinstance(value, numbers.Number) for value in values)
    assert all(0 <= value <= 1 for value in values)

    values = dists.draw_values("UNIF", [0, 1], 10, rng)
    assert len(values) == 10

    values = dists.draw_values("unifORM", [0, 1], 10, rng)
    assert len(values) == 10

    values = dists.draw_values("UnifORMgarbagestillworks", [0, 1], 10, rng)
    assert len(values) == 10

    with pytest.raises(ValueError):
        dists.draw_values("non-existing-distribution", [0, 10], 100, rng)

    values = dists.draw_values("NORMAL", [0, 1], 10, rng)
    assert len(values) == 10

    values = dists.draw_values("LOGNORMAL", [0.1, 1], 10, rng)
    assert len(values) == 10

    values = dists.draw_values("Pert", [0.1, 1, 10], 10, rng)
    assert len(values) == 10

    values = dists.draw_values("triangular", [0.1, 1, 10], 10, rng)
    assert len(values) == 10

    values = dists.draw_values("logunif", [0.1, 1], 10, rng)
    assert len(values) == 10
