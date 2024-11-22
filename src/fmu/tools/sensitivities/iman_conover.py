# -*- coding: utf-8 -*-
"""
An implementation of the Iman-Conover transformation.

Sources include:
    - A distribution-free approach to inducing rank correlation among input variables
      https://www.tandfonline.com/doi/epdf/10.1080/03610918208812265?needAccess=true
    - https://blogs.sas.com/content/iml/2021/06/14/simulate-iman-conover-transformation.html
    - https://blogs.sas.com/content/iml/2021/06/16/geometry-iman-conover-transformation.html







Using Iman-Conover with Latin Hybercube sampling
------------------------------------------------


Sample on the unit hypercube using LatinHypercube

>>> import scipy as sp
>>> sampler = sp.stats.qmc.LatinHypercube(d=2, seed=42, scramble=True)
>>> samples = sampler.random(n=100)

Map to distributions

>>> X = np.vstack((sp.stats.triang(0.5).ppf(samples[:, 0]),
...                sp.stats.gamma.ppf(samples[:, 1], a=1))).T

Induce correlations

>>> sp.stats.pearsonr(*X.T).statistic
0.0658...
>>> correlation_matrix = np.array([[1, 0.3], [0.3, 1]])
>>> transform = ImanConover(correlation_matrix)
>>> X_transformed = transform(X)
>>> sp.stats.pearsonr(*X_transformed.T).statistic
0.2796...

"""

import numpy as np
import pytest
import scipy as sp

from fmu.tools.sensitivities.design_distributions import _is_positive_definite


class ImanConover:
    def __init__(self, correlation_matrix):
        """Create an Iman-Conover transform.

        Parameters
        ----------
        correlation_matrix : ndarray
            Target correlation matrix of shape (K, K). The Iman-Conover will
            try to induce a correlation on the data set X so that corr(X) is
            as close to `correlation_matrix` as possible.

        Examples
        --------
        Create a desired correction of 0.7 and a data set X with no correlation.
        >>> correlation_matrix = np.array([[1, 0.7], [0.7, 1]])
        >>> transform = ImanConover(correlation_matrix)
        >>> X = np.array([[0, 0  ],
        ...               [0, 0.5],
        ...               [0,  1 ],
        ...               [1, 0  ],
        ...               [1, 0.5],
        ...               [1, 1  ]])
        >>> X_transformed = transform(X)
        >>> X_transformed
        array([[0. , 0. ],
               [0. , 0. ],
               [0. , 0.5],
               [1. , 0.5],
               [1. , 1. ],
               [1. , 1. ]])

        The original data X has no correlation at all, while the transformed
        data has correlation that is closer to the desired correlation structure:

        >>> sp.stats.pearsonr(*X.T).statistic
        0.0
        >>> sp.stats.pearsonr(*X_transformed.T).statistic
        0.816...

        Achieving the exact correlation structure might be impossible. For the
        input matrix above, there is no permutation of the columns that yields
        the exact desired correlation of 0.7. Iman-Conover is a heuristic that
        tries to get as close as possible.

        With many samples, we get good results if the data are normal:

        >>> rng = np.random.default_rng(42)
        >>> X = rng.normal(size=(1000, 2))
        >>> X_transformed = transform(X)
        >>> sp.stats.pearsonr(*X_transformed.T).statistic
        0.6977...

        But if the data are far from normal (here:lognormal), the results are
        not as good. This is because correlation is induced in a normal space
        before the result is mapped back to the original marginal distributions.

        >>> rng = np.random.default_rng(42)
        >>> X = rng.lognormal(size=(1000, 2))
        >>> X_transformed = transform(X)
        >>> sp.stats.pearsonr(*X_transformed.T).statistic
        0.5925...
        """
        if not isinstance(correlation_matrix, np.ndarray):
            raise TypeError("Input argument `correlation_matrix` must be NumPy array.")
        if not correlation_matrix.ndim == 2:
            raise ValueError("Correlation matrix must be square.")
        if not correlation_matrix.shape[0] == correlation_matrix.shape[1]:
            raise ValueError("Correlation matrix must be square.")
        if not np.allclose(np.diag(correlation_matrix), 1.0):
            raise ValueError("Correlation matrix must have 1.0 on diagonal.")
        if not np.allclose(correlation_matrix.T, correlation_matrix):
            raise ValueError("Correlation matrix must be symmetric.")
        if not _is_positive_definite(correlation_matrix):
            raise ValueError("Correlation matrix must be positive definite.")

        self.C = correlation_matrix.copy()
        self.P = np.linalg.cholesky(self.C)

    def __call__(self, X):
        """Transform an input matrix X.

        The output will have the same marginal distributions, but with
        induced correlation.

        Parameters
        ----------
        X : ndarray
            Input matrix of shape (N, K). This is the data set that we want to
            induce correlation structure on. X must have at least K + 1
            independent rows, because corr(X) cannot be singular.

        Returns
        -------
        ndarray
            Output matrix of shape (N, K). This data set will have a
            correlation structure that is more similar to `correlation_matrix`.

        """
        if not isinstance(X, np.ndarray):
            raise TypeError("Input argument `X` must be NumPy array.")
        if not X.ndim == 2:
            raise ValueError("Correlation matrix must be square.")

        N, K = X.shape

        if self.P.shape[0] != K:
            msg = f"Shape of `X` ({X.shape}) does not match shape of "
            msg += f"correlation matrix ({self.P.shape})"
            raise ValueError(msg)

        if N <= K:
            msg = f"The matrix X must have rows > columns. Got shape: {X.shape}"
            raise ValueError(msg)

        # STEP ONE - Use van der Waerden scores to transform data to
        # approximately multivariate normal (but with correlations).
        # The new data has the same rank correlation as the original data.
        ranks = sp.stats.rankdata(X, axis=0) / (N + 1)
        normal_scores = sp.stats.norm.ppf(ranks)  # + np.random.randn(N, K) * epsilon

        # STEP TWO - Remove correlations from the transformed data
        empirical_correlation = np.corrcoef(normal_scores, rowvar=False)
        if not _is_positive_definite(empirical_correlation):
            msg = "Rank data correlation not positive definite."
            msg += "There are perfect correlations in the ranked data."
            msg += "Supply more data (rows in X) or sample differently."
            raise ValueError(msg)

        decorrelation_matrix = np.linalg.cholesky(empirical_correlation)

        # We exploit the fact that Q is lower-triangular and avoid the inverse.
        # X = N @ inv(Q)^T  =>  X @ Q^T = N  =>  (Q @ X^T)^T = N
        decorrelated_scores = sp.linalg.solve_triangular(
            decorrelation_matrix, normal_scores.T, lower=True
        ).T

        # STEP THREE - Induce correlations in transformed space
        correlated_scores = decorrelated_scores @ self.P.T

        # STEP FOUR - Map back to original space using ranks, ensuring
        # that marginal distributions are preserved
        result = np.empty_like(X)
        for k in range(K):
            # If row j is the k'th largest in `correlated_scores`, then
            # we map the k'th largest entry in X to row j.
            ranks = sp.stats.rankdata(correlated_scores[:, k]).astype(int) - 1
            result[:, k] = np.sort(X[:, k])[ranks]

        return result


def decorrelate(X, remove_variance=True):
    """Removes correlations or covariance from data X.

    Examples
    --------
    >>> X = np.array([[1. , 1. ],
    ...               [2. , 1.1],
    ...               [2.1, 3. ]])
    >>> X_decorr = decorrelate(X)
    >>> np.cov(X_decorr, rowvar=False).round(6)
    array([[1., 0.],
           [0., 1.]])
    >>> np.allclose(np.mean(X, axis=0), np.mean(X_decorr, axis=0))
    True

    >>> X_decorr = decorrelate(X, remove_variance=False)
    >>> np.cov(X_decorr, rowvar=False).round(6)
    array([[0.246667, 0.      ],
           [0.      , 0.846667]])
    >>> np.allclose(np.mean(X, axis=0), np.mean(X_decorr, axis=0))
    True
    """
    mean = np.mean(X, axis=0)
    var = np.var(X, axis=0)
    cov = np.cov(X, rowvar=False)

    L = np.linalg.cholesky(cov)  # L @ L.T = cov
    if not remove_variance:
        L = L / np.sqrt(var)

    # Computes X = (X - mean) @ inv(L).T
    X = sp.linalg.solve_triangular(L, (X - mean).T, lower=True).T

    return mean + X


class TestImanConover:
    @pytest.mark.parametrize("seed", range(100))
    def test_marginals_and_correlation_distance(self, seed):
        rng = np.random.default_rng(seed)

        n_variables = rng.integers(2, 10)
        n_observations = n_variables * 10

        # Create a random correlation matrix and a random data matrix
        A = rng.normal(size=(n_variables * 2, n_variables))
        desired_corr = 0.9 * np.corrcoef(A, rowvar=False) + 0.1 * np.eye(n_variables)
        X = rng.normal(size=(n_observations, n_variables))

        # Tranform the data
        transform = ImanConover(desired_corr)
        X_transformed = transform(X)

        # Check that all columns (variables) have equal marginals.
        # In other words, Iman-Conover can permute each column individually,
        # but they should have identical entries before and after.
        for j in range(X.shape[1]):
            assert np.allclose(np.sort(X[:, j]), np.sort(X_transformed[:, j]))

        # After the Iman-Conover transform, the distance between the desired
        # correlation matrix should be smaller than it was before.
        X_corr = np.corrcoef(X, rowvar=False)
        distance_before = sp.linalg.norm(X_corr - desired_corr, ord="fro")

        X_trans_corr = np.corrcoef(X_transformed, rowvar=False)
        distance_after = sp.linalg.norm(X_trans_corr - desired_corr, ord="fro")

        assert distance_after <= distance_before

    def test_identity_correlation_matrix(self):
        rng = np.random.default_rng(42)

        n_observations = 5
        n_variables = 3
        rng = np.random.default_rng(42)

        # Create a random correlation matrix and a random data matrix
        desired_corr = np.identity(n_variables)
        transform = ImanConover(desired_corr)

        # Create data and decorrelate it completely
        X = rng.normal(size=(n_observations, n_variables))
        X = decorrelate(X, remove_variance=True)
        assert np.allclose(np.corrcoef(X, rowvar=False), np.eye(n_variables))

        # Transform it to identity correlation, which it already has
        transform = ImanConover(desired_corr)
        X_transformed = transform(X)

        assert np.allclose(X, X_transformed)

    def test_dataset_with_unity_correlation_in_ranks(self):
        # This dataset is interesting because while the correlation
        # between the variables is ~0.6, when the data is ranked the
        # correlation becomes 1. Rank(row) = [1, 2, 3] for both rows.
        X = np.array([[1.0, 1], [2.0, 1.1], [2.1, 3]])

        desired_corr = np.identity(2)

        transform = ImanConover(desired_corr)
        with pytest.raises(ValueError):
            transform(X)


if __name__ == "__main__":
    pytest.main(args=[__file__, "--doctest-modules", "-v", "-l"])
