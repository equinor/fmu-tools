import pytest
import numpy as np
from fmu.tools import nearcorr, ExceededMaxIterationsError

# References
# [1] 'Computing the nearest correlation matrix - a problem from finance': Higham, IMA Journal of Numerical Analysis (2002) 22, 329.343


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


def test_restart():
    """Test that restarting calculation gives same results"""
    A = np.array([[1, 1, 0], [1, 1, 1], [0, 1, 1]])

    # Do 3 iterations on A and gather the result
    try:
        Y = nearcorr(A, max_iterations=3)
    except ExceededMaxIterationsError as e:
        result3 = np.copy(e.matrix)

    # Do 1 iteration on A
    try:
        X = nearcorr(A, max_iterations=1)
    except ExceededMaxIterationsError as e:
        restart = e

    # restart from previous result and do another iteration
    try:
        X = nearcorr(restart, max_iterations=1)
    except ExceededMaxIterationsError as e:
        restart = e

    # restart from previous result and do another iteration
    try:
        X = nearcorr(restart, max_iterations=1)
    except ExceededMaxIterationsError as e:
        result1 = e.matrix

    assert np.all(result1 == result3)


def test_assert_symmetric():
    """Test that non-symmetric matrix raises ValueError"""
    A = np.array([[1, 1, 0], [1, 1, 1], [1, 1, 1]])

    with pytest.raises(ValueError):
        nearcorr(A)


def test_exceeded_max_iterations():
    """Test that exceeding max iterations raises ExceededMaxIterationsError"""
    A = np.array([[1, 1, 0], [1, 1, 1], [0, 1, 1]])

    with pytest.raises(ExceededMaxIterationsError):
        nearcorr(A, max_iterations=10)


def test_exceeded_max_iterations_false():
    """Test that exceeding max iterations doesn't raise exception when flag is False"""
    A = np.array([[1, 1, 0], [1, 1, 1], [0, 1, 1]])

    X = nearcorr(A, max_iterations=10, except_on_too_many_iterations=False)
    # No assertion needed - test passes if no exception is raised
