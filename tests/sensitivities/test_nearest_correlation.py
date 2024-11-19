import numpy as np
import pytest

from fmu.tools import nearcorr

# References
# [1] 'Computing the nearest correlation matrix -
# a problem from finance': Higham, IMA Journal of Numerical Analysis (2002) 22, 329.343


def test_nag_example():
    """Test from NAG Mark 24 documentation for g02aa, originally from [1]"""
    A = np.array([[2, -1, 0, 0], [-1, 2, -1, 0], [0, -1, 2, -1], [0, 0, -1, 2]])

    X = nearcorr(A)

    expected_result = np.array(
        [
            [1.0, -0.8084125, 0.1915875, 0.10677505],
            [-0.8084125, 1.0, -0.65623269, 0.1915875],
            [0.1915875, -0.65623269, 1.0, -0.8084125],
            [0.10677505, 0.1915875, -0.8084125, 1.0],
        ]
    )

    assert (np.abs((X - expected_result)) < 1e-8).all()


def test_higham_example_2002():
    """Example taken from [1]"""
    A = np.array([[1, 1, 0], [1, 1, 1], [0, 1, 1]])

    X = nearcorr(A)

    expected_result = np.array(
        [
            [1.0, 0.76068985, 0.15729811],
            [0.76068985, 1.0, 0.76068985],
            [0.15729811, 0.76068985, 1.0],
        ]
    )

    assert (np.abs((X - expected_result)) < 1e-8).all()


def test_weights():
    """Test with weights vector"""
    A = np.array([[1, 1, 0], [1, 1, 1], [0, 1, 1]])
    weights = np.array([1, 2, 3])

    X = nearcorr(A, weights=weights)

    expected_result = np.array(
        [
            [1.0, 0.66774961, 0.16723692],
            [0.66774961, 1.0, 0.84557496],
            [0.16723692, 0.84557496, 1.0],
        ]
    )

    assert (np.abs((X - expected_result)) < 1e-8).all()


def test_assert_symmetric():
    """Test that non-symmetric matrix raises ValueError"""
    A = np.array([[1, 1, 0], [1, 1, 1], [1, 1, 1]])

    with pytest.raises(ValueError):
        nearcorr(A)


def test_exceeded_max_iterations():
    """Test that exceeding max iterations raises ValueError"""
    A = np.array([[1, 1, 0], [1, 1, 1], [0, 1, 1]])
    with pytest.raises(ValueError, match="No convergence after 10 iterations"):
        nearcorr(A, max_iterations=10)


def test_weights_documented_example():
    """Test weights using the exact example from examples:
    https://github.com/mikecroucher/nearest_correlation"""
    A = np.array([[1, 1, 0], [1, 1, 1], [0, 1, 1]])
    weights = np.array([1, 2, 3])
    X = nearcorr(A, weights=weights)

    expected_result = np.array(
        [
            [1.0, 0.66774961, 0.16723692],
            [0.66774961, 1.0, 0.84557496],
            [0.16723692, 0.84557496, 1.0],
        ]
    )

    assert np.allclose(X, expected_result, atol=1e-8), (
        f"Result doesn't match documented example.\n"
        f"Expected:\n{expected_result}\n"
        f"Got:\n{X}"
    )
