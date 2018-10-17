# -*- coding: utf-8 -*-
"""Module for random sampling of parameter values from
distributions. For use in generation of design matrices
"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
import numpy
import numpy.linalg
import scipy.stats
import pandas as pd


def prepare_distribution(distname, dist_parameters):
    """
    Prepare scipy distributions with parameters

    TO DO
    1) Implement exceptions
    2) Implement missing distributions
    discrete uniform,
    discrete123,
    discrete uniform with weights

    Args:
        distname (str): distribution name 'normal',
                        'triang', 'uniform' or 'logunif'
        dist_parameters (list): list with parameters for distribution

    Returns:
        scipy.stats distribution with parameters
    """
    if distname == 'normal':
        dist_mean = dist_parameters[0]
        dist_stddev = dist_parameters[1]
        if _is_number(dist_mean) and _is_number(dist_stddev):
            return scipy.stats.norm(float(dist_mean), float(dist_stddev))
    elif distname == 'uniform':
        low = dist_parameters[0]
        high = dist_parameters[1]
        uscale = high - low
        if _is_number(low) and _is_number(high):
            return scipy.stats.uniform(loc=low, scale=uscale)
    elif distname == 'triang':
        low = dist_parameters[0]
        mode = dist_parameters[1]
        high = dist_parameters[2]
        dist_scale = high - low
        shape = (mode-low)/dist_scale
        if _is_number(low) and _is_number(mode) and _is_number(high):
            return scipy.stats.triang(shape, loc=low, scale=dist_scale)
    elif distname == 'logunif':
        low = dist_parameters[0]
        high = dist_parameters[1]
        if _is_number(low) and _is_number(high):
            loglow = numpy.log10(low)
            loghigh = numpy.log10(high)
            logscale = loghigh - loglow
            return scipy.stats.uniform(loc=loglow, scale=logscale)


def generate_mcvalues(distribution, mcreals):
    """
    Generate monte carlo values for given distribution
    and number of realisations

    Args:
        distribution (scipy.stats distribution):
        mcreals (int): Number of realisations to draw

    Returns:
        numpy.ndarray: values drawn from distribution
    """

    montecarlo_values = distribution.rvs(size=mcreals)
    return montecarlo_values


def _is_number(teststring):
    """ Test if a string can be parsed as a float"""
    try:
        if not numpy.isnan(float(teststring)):
            return True
        return False  # It was a "number", but it was NaN.
    except ValueError:
        return False


def read_correlations(corr_dict):
    """Reading correlation info for a
    monte carlo sensitivity

    Args:
        corr_dict (OrderedDict): correlation info

    Returns:
        pandas DataFrame with parameter names
            as column and index
    """
    correlations = pd.DataFrame()
    if 'input' in corr_dict.keys():
        filename = corr_dict['inputfile']
        if filename.endswith('.xlsx'):
            correlations = pd.read_excel(filename)
        elif filename.endswith('.csv'):
            correlations = pd.read_csv(filename)
        else:
            raise ValueError(
                'Design matrix filename should be on Excel or csv format'
                ' and end with .xlsx or .csv')
        return correlations


def make_covariance_matrix(df_correlations, stddevs=None):
    """Read a Pandas DataFrame defining correlation coefficients for
    a set of multivariate normally distributed parameters, and build
    covariance matrix.

    The diagonal of the correlation coefficients matrix should be all
    ones. Variances are combined with the correlation coefficients to
    compute the covariance matrix.

    If the correlation matrix is not symmetric positive definite (SDP),
    the matrix is projected onto the SDP manifold and returned (together
    with a warning). The algorithm is according to Higham (2000)

    Args:
        df_correlations (DataFrame): correlation coefficients where
            columns and index are both parameter names. All parameter
            names in keys must also exist in index and vice versa.
    """

    corr_matrix = numpy.matrix(df_correlations.values)

    # Assume upper triangular is empty, fill it:
    i_upper = numpy.triu_indices(len(df_correlations.columns), 1)
    corr_matrix[i_upper] = corr_matrix.T[i_upper]

    # Project to nearest symmetric positive definite matrix
    corr_matrix = nearPD(corr_matrix)
    # Previously negative eigenvalues are now close to zero,
    # but might still be negative, that can be ignored

    # Support unity standard devistions
    if not stddevs:
        stddevs = len(corr_matrix) * [1]

    # Now generate the covariance matrix
    n = len(stddevs)
    D = numpy.identity(n)
    D[range(n), range(n)] = stddevs
    cov_matrix = numpy.dot(D, corr_matrix)
    cov_matrix = numpy.dot(cov_matrix, D)

    return cov_matrix

# Implementation based on Higham (2000), used in make_covariance_matrix
# Taken from:
#  https://stackoverflow.com/questions/10939213/how-can-i-calculate-the-nearest-positive-semi-definite-matrix


def _getAplus(A):
    eigval, eigvec = numpy.linalg.eig(A)
    Q = numpy.matrix(eigvec)
    xdiag = numpy.matrix(numpy.diag(numpy.maximum(eigval, 0)))
    return Q*xdiag*Q.T


def _getPs(A, W=None):
    W05 = numpy.matrix(W**.5)
    return W05.I * _getAplus(W05 * A * W05) * W05.I


def _getPu(A, W=None):
    Aret = numpy.array(A.copy())
    Aret[W > 0] = numpy.array(W)[W > 0]
    return numpy.matrix(Aret)


def nearPD(A, nit=10):
    n = A.shape[0]
    W = numpy.identity(n)
    # W is the matrix used for the norm (assumed to be Identity matrix here)
    # the algorithm should work for any diagonal W
    deltaS = 0
    Yk = A.copy()
    for k in range(nit):
        Rk = Yk - deltaS
        Xk = _getPs(Rk, W=W)
        deltaS = Xk - Rk
        Yk = _getPu(Xk, W=W)
    return Yk
