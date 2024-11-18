# -*- coding: utf-8 -*-
"""
An implementation of the Iman-Conover transformation.

Sources include:
    - A distribution-free approach to inducing rank correlation among input variables
      https://www.tandfonline.com/doi/epdf/10.1080/03610918208812265?needAccess=true
    - https://blogs.sas.com/content/iml/2021/06/14/simulate-iman-conover-transformation.html
    - https://blogs.sas.com/content/iml/2021/06/16/geometry-iman-conover-transformation.html


"""

import numpy as np
import scipy as sp
import pandas as pd
import requests
import io
import matplotlib.pyplot as plt
import pytest


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
        >>> X = np.array([[0, 0],
        ...               [0, 0.5],
        ...               [0,  1],
        ...               [1, 0],
        ...               [1,  1],
        ...               [1, 0.5]])
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

        self.C = correlation_matrix.copy()
        self.P = np.linalg.cholesky(self.C)

    def __call__(self, X):
        """Transform an input matrix X.

        The output will have the same marginal distributions, but with
        induced correlation.

        Parameters
        ----------
        X : ndarray
            Input matrix of shape (N, K).

        Returns
        -------
        ndarray
            Input matrix of shape (N, K).

        """
        if not isinstance(X, np.ndarray):
            raise TypeError("Input argument `X` must be NumPy array.")
        if not X.ndim == 2:
            raise ValueError("Correlation matrix must be square.")

        N, K = X.shape

        if not K == self.P.shape[0]:
            msg = f"Shape of `X` ({X.shape}) does not match shape of "
            msg += f"correlation matrix ({self.P.shape})"
            raise ValueError(msg)

        # Step one - use van der Waerden scores to transform data into new data
        # that are approximately multivariate normal.
        # The new data has the same rank correlation as the original data.
        ranks = sp.stats.rankdata(X, method="average", axis=0) / (N + 1)
        normal_scores = sp.stats.norm.ppf(ranks)

        spearman_before = sp.stats.spearmanr(X).statistic
        spearman_after = sp.stats.spearmanr(normal_scores).statistic
        msg = "Spearman correlation before and after ranking should be equal"
        assert np.allclose(spearman_before, spearman_after), msg

        # Step two - Remove correlations from the input data set
        I = np.corrcoef(normal_scores, rowvar=False)
        Q = np.linalg.cholesky(I)
        decorrelated_scores = np.linalg.solve(Q, normal_scores.T).T

        # Step three - Induce correlations
        correlated_scores = decorrelated_scores @ self.P.T

        # correlations = np.corrcoef(correlated_scores, rowvar=False)
        # assert np.allclose(correlations, self.C)

        # Step four - Restore marginal distributions using ranks
        result = np.empty_like(X)
        for k in range(K):
            ranks = sp.stats.rankdata(correlated_scores[:, k]).astype(int) - 1
            result[:, k] = np.sort(X[:, k])[ranks]

        return result


class TestImanConover:
    @pytest.mark.parametrize("seed", range(100))
    def test_marginals_and_correlation_distance(self, seed):
        rng = np.random.default_rng(42)

        n_variables = rng.integers(2, 100)
        n_observations = 10 * n_variables
        rng = np.random.default_rng(42)

        # Create a random correlation matrix and a random data matrix
        A = rng.normal(size=(n_variables * 2, n_variables))
        corr = np.corrcoef(A, rowvar=False)
        X = rng.normal(size=(n_observations, n_variables))

        # Tranform the data
        transform = ImanConover(corr)
        X_transformed = transform(X)

        # Check that all columns (variables) have equal marginals.
        # In other words, Iman-Conover can permute each column individually,
        # but they should have the same entries before and after.
        for j in range(X.shape[1]):
            assert np.allclose(np.sort(X[:, j]), np.sort(X_transformed[:, j]))

        # After the Iman-Conover transform, the distance between the desired
        # correlation matrix should be smaller than it was before.
        distance_before = sp.linalg.norm(np.corrcoef(X, rowvar=False) - corr)
        distance_after = sp.linalg.norm(np.corrcoef(X_transformed, rowvar=False) - corr)
        assert distance_after <= distance_before


if __name__ == "__main__":
    import pytest

    pytest.main(
        args=[
            __file__,
            "--doctest-modules",
            "-v",
        ]
    )


if False:

    def plotmat(mat, title):
        """Plot a matrix."""
        plt.figure()
        plt.title(title)
        plt.scatter(*mat.T)
        plt.show()

    # Download the CARS dataset used in
    # https://blogs.sas.com/content/iml/2021/06/16/geometry-iman-conover-transformation.html
    csv = requests.get(
        "https://raw.githubusercontent.com/sassoftware/sas-viya-programming/refs/heads/master/data/cars.csv"
    ).text
    filepath = io.StringIO(csv)
    df = pd.read_csv(filepath)  # .sample(5, random_state=42)
    X = df[["EngineSize", "MPG_Highway"]].to_numpy()

    # Add some noise to tie-break variables
    # TODO: look more into what happens when ties are not broken
    X = X + np.random.randn(*X.shape) * 0.1

    # TODO: Another interesting data set is
    if False:
        theta = np.random.rand(100) * np.pi * 2
        x = np.cos(theta) + np.random.randn(len(theta)) * 0.1
        y = np.sin(theta) + np.random.randn(len(theta)) * 0.1
        X = np.vstack((x, y)).T

    # TODO: Look into QMC methods like LatinHypercube
    if True:
        # LatinHypercube or Sobol
        sampler = sp.stats.qmc.Sobol(d=2, seed=42, scramble=False)
        lhs_samples = sampler.random(n=100)  # on interval [0, 1]
        lhs_samples = np.clip(lhs_samples, a_min=1e-3, a_max=1 - 1e-3)
        plotmat(lhs_samples, "lhs_samples")
        X = sp.stats.norm.ppf(lhs_samples)  # map to normal
        X = np.vstack(
            (
                sp.stats.norm.ppf(lhs_samples[:, 0]),
                sp.stats.gamma.ppf(lhs_samples[:, 1], a=1),
            )
        ).T

    # Create a correlation matrix that we want to replicate
    C = np.eye(2)
    C[0, 1] = C[1, 0] = 0.6

    plotmat(X, "input data X")

    # Step one - Map data to normal scores
    N, K = X.shape
    ranks = sp.stats.rankdata(X, method="average", axis=0) / (N + 1)
    normal_scores = sp.stats.norm.ppf(ranks)
    plotmat(normal_scores, "normal_scores")

    assert np.isclose(
        sp.stats.spearmanr(X).statistic, sp.stats.spearmanr(normal_scores).statistic
    ), "spearman corr before and after should be the same"

    # Step two - Remove correlations
    I = np.corrcoef(normal_scores, rowvar=False)
    Q = np.linalg.cholesky(I)  # QQ' = I
    decorrelated_scores = normal_scores @ np.linalg.inv(Q).T
    plotmat(decorrelated_scores, "decorrelated_scores")
    assert np.allclose(np.corrcoef(decorrelated_scores, rowvar=False), np.eye(K))

    decorrelated_scores2 = np.linalg.solve(Q, normal_scores.T).T
    assert np.allclose(decorrelated_scores, decorrelated_scores2)

    # Step three - Induce correlations
    P = np.linalg.cholesky(C)  # PP' = C
    correlated_scores = decorrelated_scores @ P.T
    assert np.allclose(np.corrcoef(correlated_scores, rowvar=False), C)
    plotmat(correlated_scores, "correlated_scores")

    corr = sp.stats.spearmanr(correlated_scores).statistic
    print(f"Rank correlation of correlated_scores: {corr:.6f}")
    corr = sp.stats.pearsonr(*correlated_scores.T).statistic
    print(f"Correlation of correlated_scores: {corr:.6f}")

    # Step four - Restore marginal distributions
    result = np.empty_like(X)
    for k in range(K):
        # sorted_idx = np.argsort(R_star[:, k])
        # result[:, k] = np.sort(X[:, k])[sorted_idx] # X[sorted_idx, k]
        ranks = sp.stats.rankdata(correlated_scores[:, k]).astype(int) - 1
        result[:, k] = np.sort(X[:, k])[ranks]

    plotmat(result, "result")

    assert np.allclose(np.sort(X[:, 0]), np.sort(result[:, 0])), "Marginal must match"

    corr = sp.stats.pearsonr(*result.T).statistic
    print(f"Correlation of result: {corr:.6f}")
    corr = sp.stats.spearmanr(result).statistic
    print(f"Rank correlation of result: {corr:.6f}")

    obs_corr = sp.stats.pearsonr(*result.T).statistic
    assert np.isclose(obs_corr, 0.6, atol=0.1)
