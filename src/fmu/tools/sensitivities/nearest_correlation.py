import numpy as np
from numpy import inf
from numpy import copy
from numpy.linalg import norm


def nearcorr(
    A,
    tol=None,
    flag=0,
    max_iterations=100,
    weights=None,
):
    """
    Finds the nearest correlation matrix to the symmetric matrix A.

    ARGUMENTS
    ~~~~~~~~~
    A: symmetric numpy array
    tol: convergence tolerance
    flag: 0 for full eigendecomposition (only option supported)
    max_iterations: maximum number of iterations (default 100)
    weights: optional vector defining a diagonal weight matrix diag(W)
    """
    eps = np.spacing(1)
    if not np.all((np.transpose(A) == A)):
        raise ValueError("Input Matrix is not symmetric")

    if not tol:
        tol = eps * np.shape(A)[0] * np.array([1, 1])
    if weights is None:
        weights = np.ones(np.shape(A)[0])

    X = copy(A)
    Y = copy(A)
    ds = np.zeros(np.shape(A))
    rel_diffY = inf
    rel_diffX = inf
    rel_diffXY = inf

    Whalf = np.sqrt(np.outer(weights, weights))

    iteration = 0
    while max(rel_diffX, rel_diffY, rel_diffXY) > tol[0]:
        iteration += 1
        if iteration > max_iterations:
            raise ValueError(f"No convergence after {max_iterations} iterations")

        Xold = copy(X)
        R = X - ds
        R_wtd = Whalf * R
        if flag == 0:
            X = proj_spd(R_wtd)
        elif flag == 1:
            raise NotImplementedError(
                "Setting 'flag' to 1 is currently not implemented."
            )

        X = X / Whalf
        ds = X - R
        Yold = copy(Y)
        Y = copy(X)
        np.fill_diagonal(Y, 1)
        normY = norm(Y, "fro")
        rel_diffX = norm(X - Xold, "fro") / norm(X, "fro")
        rel_diffY = norm(Y - Yold, "fro") / normY
        rel_diffXY = norm(Y - X, "fro") / normY

        X = copy(Y)

    return X


def proj_spd(A):
    # NOTE: the input matrix is assumed to be symmetric
    d, v = np.linalg.eigh(A)
    A = (v * np.maximum(d, 0)).dot(v.T)
    A = (A + A.T) / 2
    return A
