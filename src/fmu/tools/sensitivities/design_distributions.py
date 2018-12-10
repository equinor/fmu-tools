# -*- coding: utf-8 -*-
"""Module for random sampling of parameter values from
distributions. For use in generation of design matrices
"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from math import exp
import re
import numpy
import numpy.linalg as la
import scipy.stats
import pandas as pd


def prepare_distribution(distname, dist_parameters):
    """
    Prepare scipy distributions with parameters

    To do -  Implement missing distributions
    lognormal

    Args:
        distname (str): distribution name 'normal',
                        'triang', 'uniform' or 'logunif'
        dist_parameters (list): list with parameters for distribution

    Returns:
        scipy.stats distribution with parameters
    """
    distribution = None
    if distname[0:4].lower() == 'norm':
        if len(dist_parameters) == 2:  # normal
            dist_mean = dist_parameters[0]
            dist_stddev = dist_parameters[1]
            if is_number(dist_mean) and is_number(dist_stddev):
                distribution = scipy.stats.norm(
                    float(dist_mean), float(dist_stddev))
        elif len(dist_parameters) == 4:  # truncated normal
            dist_mean = dist_parameters[0]
            dist_stddev = dist_parameters[1]
            clip1 = dist_parameters[2]
            clip2 = dist_parameters[3]
            if (
                    is_number(dist_mean) and
                    is_number(dist_stddev) and
                    is_number(clip1) and
                    is_number(clip2)
            ):
                low = (float(clip1)-float(dist_mean))/float(dist_stddev)
                high = (float(clip2)-float(dist_mean))/float(dist_stddev)
                distribution = scipy.stats.truncnorm(
                    low, high, loc=float(dist_mean), scale=float(dist_stddev))
    elif distname[0:4].lower() == 'logn':
        if len(dist_parameters) == 2:  # lognormal
            mean = dist_parameters[0]
            sigma = dist_parameters[1]
            if is_number(mean) and is_number(sigma):
                distribution = scipy.stats.lognorm(
                    s=float(sigma), scale=exp(float(mean)))
        if len(dist_parameters) == 4:  # lognormal
            raise ValueError(
                'Truncated lognormal is '
                'not implemented \n'
                'Exiting')
    elif distname[0:4].lower() == 'unif':
        low = dist_parameters[0]
        high = dist_parameters[1]
        uscale = high - low
        if is_number(low) and is_number(high):
            distribution = scipy.stats.uniform(loc=low, scale=uscale)
    elif distname[0:6].lower() == 'triang':
        low = dist_parameters[0]
        mode = dist_parameters[1]
        high = dist_parameters[2]
        dist_scale = high - low
        shape = (mode-low)/dist_scale
        if is_number(low) and is_number(mode) and is_number(high):
            distribution = scipy.stats.triang(
                shape, loc=low, scale=dist_scale)
    elif distname[0:7].lower() == 'logunif':
        low = float(dist_parameters[0])
        high = float(dist_parameters[1])
        if is_number(low) and is_number(high):
            loglow = numpy.log10(low)
            loghigh = numpy.log10(high)
            logscale = loghigh - loglow
            distribution = scipy.stats.uniform(
                loc=loglow, scale=logscale)
    else:
        raise ValueError(
            'distribution name {} is not implemented'
            .format(distname))
    return distribution


def sample_discrete(dist_params, numreals):
    """Sample from discrete distribution

    Args:
        dist_params(list): parameters for distribution
            dist_params[0] is possible outcomes separated
            by comma
            dist_params[1] is probabilities for each outcome,
            separated by comma
        numreals (int): number of realisations to draw

    Returns:
        numpy.ndarray: values drawn from distribution
    """

    outcomes = re.split(',', dist_params[0])
    if len(dist_params) == 2:  # non uniform
        fractions = re.split(',', dist_params[1])
        values = numpy.random.choice(
            outcomes, numreals,
            fractions)
    elif len(dist_params) == 1:  # uniform
        values = numpy.random.choice(
            outcomes, numreals)
    else:
        raise ValueError('Wrong input for discrete '
                         'distribution')
    return values


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


def is_number(teststring):
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
    correlations = None
    if 'inputfile' in corr_dict.keys() and \
       'corrsheet' in corr_dict.keys():
        filename = corr_dict['inputfile']
        if filename.endswith('.xlsx'):
            correlations = pd.read_excel(
                filename, corr_dict['corrsheet'])
        else:
            raise ValueError(
                'Correlation matrix filename should be on'
                'Excel format and end with .xlsx')
    else:
        raise ValueError('correlations specified but inputfile '
                         'not specified in configuration')
    return correlations


def mc_correlated(params, correls, numreals):
    """Generating random values when parameters are correlated

    Args:
        parameters (OrderedDict):
            dictionary of parameters and distributions
        correls: dataframe with correlations
        numreals: number of realisations to generate
    """
    multivariate_parameters = correls.index.values
    cov_matrix = make_covariance_matrix(correls)
    normalscoremeans = len(multivariate_parameters) * [0]
    normalscoresamples = numpy.random.multivariate_normal(
        normalscoremeans, cov_matrix, size=numreals)
    normalscoresamples_df = pd.DataFrame(
        data=normalscoresamples,
        columns=multivariate_parameters)
    samples_df = pd.DataFrame(columns=multivariate_parameters)
    for key in params.keys():
        dist_name = params[key][0].lower()
        dist_params = params[key][1]
        if key in multivariate_parameters:
            if dist_name == 'normal':
                if len(dist_params) == 2:  # normal
                    dist_mean = dist_params[0]
                    dist_stddev = dist_params[1]
                    if is_number(dist_mean) and is_number(dist_stddev):
                        samples_df[key] = scipy.stats.norm.ppf(
                            scipy.stats.norm.cdf(
                                normalscoresamples_df[key]),
                            loc=float(dist_mean),
                            scale=float(dist_stddev))
                elif len(dist_params) == 4:  # trunc normal
                    dist_mean = dist_params[0]
                    dist_stddev = dist_params[1]
                    clip1 = dist_params[2]
                    clip2 = dist_params[3]
                    if (
                            is_number(dist_mean) and
                            is_number(dist_stddev) and
                            is_number(clip1) and
                            is_number(clip2)
                    ):
                        low = (
                            float(clip1)-float(dist_mean))/float(dist_stddev)
                        high = (
                            float(clip2)-float(dist_mean))/float(dist_stddev)
                        samples_df[key] = scipy.stats.truncnorm.ppf(
                            scipy.stats.norm.cdf(
                                normalscoresamples_df[key]),
                            low,
                            high,
                            loc=float(dist_mean),
                            scale=float(dist_stddev))
            elif dist_name[0:6].lower() == 'triang':
                low = dist_params[0]
                mode = dist_params[1]
                high = dist_params[2]
                dist_scale = high - low
                shape = (mode-low)/dist_scale
                samples_df[key] = scipy.stats.triang.ppf(
                    scipy.stats.norm.cdf(
                        normalscoresamples_df[key]),
                    shape,
                    loc=low,
                    scale=dist_scale)
            elif dist_name[0:4].lower() == 'unif':
                low = dist_params[0]
                high = dist_params[1]
                uscale = high - low
                samples_df[key] = scipy.stats.uniform.ppf(
                    scipy.stats.norm.cdf(
                        normalscoresamples_df[key]),
                    loc=low,
                    scale=uscale)
            elif dist_name[0:7].lower() == 'logunif':
                low = dist_params[0]
                high = dist_params[1]
                loglow = numpy.log10(low)
                loghigh = numpy.log10(high)
                logscale = loghigh - loglow
                samples_df[key] = scipy.stats.uniform.ppf(
                    scipy.stats.norm.cdf(
                        normalscoresamples_df[key]),
                    loc=loglow,
                    scale=logscale)
                samples_df[key] = 10**samples_df[key]
            elif dist_name[0:4].lower() == 'logn':
                mean = dist_params[0]
                sigma = dist_params[1]
                samples_df[key] = scipy.stats.lognorm.ppf(
                    scipy.stats.norm.cdf(
                        normalscoresamples_df[key]),
                    s=sigma, loc=0, scale=exp(mean))
            else:
                raise ValueError(
                    'Parameter distribution {} assigned for {} '
                    'cannot be used when in correlation matrix  '
                    .format(dist_name, key))
            # Rounding if specified in config
            if len(params[key]) == 3:
                decimals = params[key][2]
                samples_df[key] = (samples_df[key].
                                   astype(float).round(int(decimals)))
        elif dist_name[0:5].lower() == 'const':
            samples_df[key] = [dist_params[0]] * numreals
        elif dist_name[0:4].lower() == 'disc':
            samples_df[key] = sample_discrete(
                dist_params, numreals)
        else:
            raise ValueError('Parameter {} defined with distribution but '
                             'not found in correlation matrix '
                             'and not defined as a constant or discrete'
                             .format(key))
    return samples_df


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

    Returns:
        covariance matrix
    """

    corr_matrix = numpy.array(df_correlations.values)

    # Assume upper triangular is empty, fill it:
    i_upper = numpy.triu_indices(len(df_correlations.columns), 1)
    corr_matrix[i_upper] = corr_matrix.T[i_upper]

    # Project to nearest symmetric positive definite matrix
    corr_matrix = _nearest_positive_definite(corr_matrix)
    # Previously negative eigenvalues are now close to zero,
    # but might still be negative, that can be ignored

    # Support unity standard devistions
    if not stddevs:
        stddevs = len(corr_matrix) * [1]

    # Now generate the covariance matrix
    dim = len(stddevs)
    diag = numpy.identity(dim)
    diag[range(dim), range(dim)] = stddevs
    cov_matrix = numpy.dot(diag, corr_matrix)
    cov_matrix = numpy.dot(cov_matrix, diag)

    return cov_matrix


def _nearest_positive_definite(a_mat):
    """Implementation taken from:
    https://stackoverflow.com/questions/43238173/
    python-convert-matrix-to-positive-semi-definite/43244194#43244194
    """

    b_mat = (a_mat + a_mat.T) / 2
    _, s_mat, v_mat = la.svd(b_mat)

    h_mat = numpy.dot(v_mat.T, numpy.dot(numpy.diag(s_mat), v_mat))

    a2_mat = (b_mat + h_mat) / 2

    a3_mat = (a2_mat + a2_mat.T) / 2

    if _is_positive_definite(a3_mat):
        return a3_mat

    spacing = numpy.spacing(la.norm(a_mat))
    identity = numpy.eye(a_mat.shape[0])
    kiter = 1
    while not _is_positive_definite(a3_mat):
        mineig = numpy.min(numpy.real(la.eigvals(a3_mat)))
        a3_mat += identity * (-mineig * kiter**2 + spacing)
        kiter += 1

    return a3_mat


def _is_positive_definite(b_mat):
    """Returns true when input is positive-definite, via Cholesky"""
    try:
        _ = la.cholesky(b_mat)
        return True
    except la.LinAlgError:
        return False
