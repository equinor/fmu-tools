import numpy as np
import pytest
from scipy.stats import spearmanr

from fmu.tools import iman_conover


@pytest.fixture
def rng():
    return np.random.RandomState()


@pytest.fixture
def sample_data(rng):
    N = 1000
    K = 3
    X = np.zeros((N, K))
    X[:, 0] = rng.normal(0, 1, N)
    X[:, 1] = rng.exponential(1, N)
    X[:, 2] = rng.uniform(0, 1, N)

    # Ensure positive definite correlation matrix by constructing from random matrix
    A = rng.randn(K, K)
    C = A @ A.T  # This creates a positive definite matrix
    # Convert to correlation matrix
    d = np.sqrt(np.diag(C))
    C = C / d[:, None] / d[None, :]

    return X, C


def test_preserves_marginal_distributions(rng, sample_data):
    X, C = sample_data
    X_transformed = iman_conover(X, C, rng)

    for k in range(X.shape[1]):
        assert np.allclose(np.sort(X[:, k]), np.sort(X_transformed[:, k]))


def test_achieves_target_correlations(rng, sample_data):
    X, C = sample_data
    X_transformed = iman_conover(X, C, rng)

    rank_corr = spearmanr(X_transformed)[0]
    assert np.allclose(rank_corr, C, atol=0.05)


def test_invalid_correlation_matrix(rng):
    N, K = 100, 3
    X = np.random.randn(N, K)
    C_invalid = np.array(
        [
            [1.0, 0.7, -0.3],
            [0.8, 1.0, 0.5],  # Non-symmetric
            [-0.3, 0.5, 1.0],
        ]
    )

    with pytest.raises((ValueError, np.linalg.LinAlgError)):
        iman_conover(X, C_invalid, rng)


def test_extreme_correlations(rng):
    N, K = 1000, 3
    X = rng.randn(N, K)

    # Create extreme but valid correlation matrix
    # Using the fact that a correlation matrix with ones on diagonal
    # and same value rho everywhere else is positive definite if
    # rho > -1/(K-1) where K is matrix size
    rho = 0.99  # High correlation but still allows matrix to be positive definite
    C_extreme = np.ones((K, K)) * rho
    np.fill_diagonal(C_extreme, 1.0)

    # Verify matrix is positive definite before test
    eigenvals = np.linalg.eigvals(C_extreme)
    assert np.all(eigenvals > 0), "Test correlation matrix is not positive definite"

    X_extreme = iman_conover(X, C_extreme, rng)
    rank_corr_extreme = spearmanr(X_extreme)[0]
    assert np.allclose(rank_corr_extreme, C_extreme, atol=0.05)


def test_small_sample(rng):
    N = 10
    K = 3
    X = np.random.randn(N, K)

    # Create valid correlation matrix
    A = rng.randn(K, K)
    C = A @ A.T
    d = np.sqrt(np.diag(C))
    C = C / d[:, None] / d[None, :]

    X_transformed = iman_conover(X, C, rng)
    assert X_transformed.shape == (N, K)
    for k in range(K):
        assert np.allclose(np.sort(X[:, k]), np.sort(X_transformed[:, k]))


def test_large_sample(rng):
    N = 10000
    K = 3
    X = np.random.randn(N, K)

    # Create valid correlation matrix
    A = rng.randn(K, K)
    C = A @ A.T
    d = np.sqrt(np.diag(C))
    C = C / d[:, None] / d[None, :]

    X_transformed = iman_conover(X, C, rng)
    rank_corr = spearmanr(X_transformed)[0]
    assert np.allclose(rank_corr, C, atol=0.1)


def test_correlation_matrix_validation(rng):
    N = 100
    K = 3
    X = np.random.randn(N, K)

    # Create non-positive definite matrix
    C_invalid = np.array([[1.0, 2.0, 0.3], [2.0, 1.0, 0.2], [0.3, 0.2, 1.0]])

    with pytest.raises(np.linalg.LinAlgError):
        iman_conover(X, C_invalid, rng)


def test_input_validation():
    rng = np.random.RandomState(42)
    N = 100
    K = 3
    X = np.random.randn(N, K)
    C = np.array(
        [
            [1.0, 0.5],  # Wrong size
            [0.5, 1.0],
        ]
    )

    with pytest.raises(ValueError):
        iman_conover(X, C, rng)


def test_orthogonality_precision(rng):
    """Test that uncorrelated variables remain very close to orthogonal"""
    N = 100
    K = 4

    # Create target correlation matrix with some zeros
    C_target = np.array(
        [
            [1.0, 0.0, 0.5, 0.0],
            [0.0, 1.0, 0.0, 0.5],
            [0.5, 0.0, 1.0, 0.0],
            [0.0, 0.5, 0.0, 1.0],
        ]
    )

    X = rng.randn(N, K)
    X_transformed = iman_conover(X, C_target, rng)
    rank_corr = spearmanr(X_transformed)[0]

    # Get the elements that should be zero
    zero_mask = C_target == 0
    achieved_zeros = rank_corr[zero_mask]

    # With variance reduction, these should be very close to zero
    # Using much tighter tolerance than regular correlation tests
    # Threshold found by running thousands of tests.
    # This will fail much more often if we do not use the variance
    # reduction technique described in the paper.
    assert np.all(
        np.abs(achieved_zeros) < 0.12
    ), "Zero correlations not maintained with sufficient precision"
