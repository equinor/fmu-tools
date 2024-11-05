"""Module for random sampling of parameter values from
distributions. For use in generation of design matrices
"""

import re
from math import exp

import numpy as np
import pandas as pd
import scipy.stats
from scipy.stats import qmc


def _check_dist_params_normal(dist_params):
    if len(dist_params) not in [2, 4]:
        status = False
        msg = (
            "Normal distribution must have 2 parameters"
            " or 4 for a truncated normal, "
            "but had " + str(len(dist_params)) + " parameters. "
        )
    elif not all(is_number(param) for param in dist_params):
        status = False
        msg = "Parameters for normal distribution must be numbers. "
    elif float(dist_params[1]) < 0:
        status = False
        msg = "Stddev for normal distribution must be >= 0. "
    elif len(dist_params) == 4 and float(dist_params[2]) >= float(dist_params[3]):
        status = False
        msg = (
            "For truncated normal distribution, "
            "lower bound must be less than upper bound, "
            f"but got [{dist_params[2]}, {dist_params[3]}]. "
        )
    else:
        status = True
        msg = ""

    return status, msg


def _check_dist_params_lognormal(dist_params):
    if len(dist_params) != 2:
        status = False
        msg = (
            "Lognormal distribution must have 2 parameters, "
            "but had " + str(len(dist_params)) + " parameters. "
        )
    elif not (is_number(dist_params[0]) and is_number(dist_params[1])):
        status = False
        msg = "Parameters for lognormal distribution must be numbers. "
    elif float(dist_params[1]) < 0:
        status = False
        msg = "Lognormal distribution must have stddev >= 0. "
    else:
        status = True
        msg = ""

    return status, msg


def _check_dist_params_uniform(dist_params):
    if len(dist_params) != 2:
        status = False
        msg = (
            "Uniform distribution must have 2 parameters, "
            "but had " + str(len(dist_params)) + " parameters. "
        )
    elif not (is_number(dist_params[0]) and is_number(dist_params[1])):
        status = False
        msg = "Parameters for uniform distribution must be numbers. "
    elif float(dist_params[1]) < float(dist_params[0]):
        status = False
        msg = "Uniform distribution must have dist_param2 >= dist_param1"
    else:
        status = True
        msg = ""

    return status, msg


def _check_dist_params_triang(dist_params):
    if len(dist_params) != 3:
        status = False
        msg = (
            "Triangular distribution must have 3 parameters, "
            "but had " + str(len(dist_params)) + " parameters. "
        )
    elif not all(is_number(param) for param in dist_params):
        status = False
        msg = "Parameters for triangular distribution must be numbers. "
    elif not (
        (float(dist_params[2]) >= float(dist_params[1]))
        and (float(dist_params[1]) >= float(dist_params[0]))
    ):
        status = False
        msg = "Triangular distribution must have: low <= mode <= high. "
    else:
        status = True
        msg = ""

    return status, msg


def _check_dist_params_pert(dist_params):
    if len(dist_params) not in [3, 4]:
        status = False
        msg = (
            "pert distribution must have 3 or 4 parameters, "
            "but had " + str(len(dist_params)) + " parameters. "
        )
    elif not all(is_number(param) for param in dist_params):
        status = False
        msg = "Parameters for pert distribution must be numbers. "
    elif not (
        (float(dist_params[2]) >= float(dist_params[1]))
        and (float(dist_params[1]) >= float(dist_params[0]))
    ):
        status = False
        msg = "Pert distribution must have: low <= mode <= high. "
    else:
        status = True
        msg = ""

    return status, msg


def _check_dist_params_logunif(dist_params):
    if len(dist_params) != 2:
        status = False
        msg = (
            "Log uniform distribution must have 2 parameters. "
            "but had " + str(len(dist_params)) + " parameters. "
        )
    elif not (is_number(dist_params[0]) and is_number(dist_params[1])):
        status = False
        msg = "Parameters for log uniform distribution must be numbers. "
    elif not (
        (float(dist_params[0]) > 0) and (float(dist_params[1]) >= float(dist_params[0]))
    ):
        status = False
        msg = "loguniform distribution must have low > 0 and high >=low. "
    else:
        status = True
        msg = ""

    return status, msg


def generate_stratified_samples(numreals, rng):
    """Generate stratified samples in [0,1] by dividing the interval
    into equal-probability strata.

    This is equivalent to one-dimensional Latin Hypercube Sampling
    where the [0,1] interval is divided into numreals equal segments,
    and one random sample is drawn from each segment.

    Parameters:
        numreals: int, number of samples to generate
        rng: numpy.random.RandomState, random number generator instance

    Returns:
        numpy.ndarray: Array of stratified samples in [0,1]
    """
    if numreals < 0:
        raise ValueError("numreal must be a positive integer")

    if numreals == 0:
        return np.array([])

    sampler = qmc.LatinHypercube(d=1, seed=rng)
    samples = sampler.random(n=numreals)
    scaled = qmc.scale(samples, 0, 1)
    return scaled.flatten()


def draw_values_normal(dist_parameters, numreals, rng, normalscoresamples=None):
    status, msg = _check_dist_params_normal(dist_parameters)

    if not status:
        raise ValueError(msg)

    mean = float(dist_parameters[0])
    stddev = float(dist_parameters[1])

    if len(dist_parameters) == 2:  # normal
        if normalscoresamples is not None:
            values = scipy.stats.norm.ppf(
                scipy.stats.norm.cdf(normalscoresamples), loc=mean, scale=stddev
            )
        else:
            uniform_samples = generate_stratified_samples(numreals, rng)
            values = scipy.stats.norm.ppf(uniform_samples, loc=mean, scale=stddev)

    else:  # truncated normal
        clip1 = float(dist_parameters[2])
        clip2 = float(dist_parameters[3])
        low = (clip1 - mean) / stddev
        high = (clip2 - mean) / stddev

        if normalscoresamples is not None:
            values = scipy.stats.truncnorm.ppf(
                scipy.stats.norm.cdf(normalscoresamples),
                low,
                high,
                loc=mean,
                scale=stddev,
            )
        else:
            uniform_samples = generate_stratified_samples(numreals, rng)
            values = scipy.stats.truncnorm.ppf(
                uniform_samples.flatten(), low, high, loc=mean, scale=stddev
            )

    return values


def draw_values_lognormal(dist_parameters, numreals, rng, normalscoresamples=None):
    """Draws values from lognormal distribution.
    Args:
        dist_parameters(list): [mu, sigma] for the logarithm of the variable
        numreals(int): number of realisations to draw
        rng: numpy.random.RandomState instance
        normalscoresamples(list): samples for correlated parameters
    Returns:
        list of values
    """
    status, msg = _check_dist_params_lognormal(dist_parameters)
    if not status:
        raise ValueError(msg)

    mean = float(dist_parameters[0])
    sigma = float(dist_parameters[1])
    if normalscoresamples is not None:
        values = scipy.stats.lognorm.ppf(
            scipy.stats.norm.cdf(normalscoresamples),
            s=sigma,
            loc=0,
            scale=exp(mean),
        )
    else:
        uniform_samples = generate_stratified_samples(numreals, rng)
        values = scipy.stats.lognorm.ppf(
            uniform_samples, s=sigma, loc=0, scale=exp(mean)
        )

    return values


def draw_values_uniform(dist_parameters, numreals, rng, normalscoresamples=None):
    """Draws values from uniform distribution.
    Args:
        dist_parameters(list): [minimum, maximum]
        numreals(int): number of realisations to draw
        rng: numpy.random.RandomState instance
        normalscoresamples(list): samples for correlated parameters
    Returns:
        list of values
    """
    if numreals < 0:
        raise ValueError("numreal must be a positive integer")

    if numreals == 0:
        return np.array([])

    status, msg = _check_dist_params_uniform(dist_parameters)
    if not status:
        raise ValueError(msg)

    low = float(dist_parameters[0])
    high = float(dist_parameters[1])
    uscale = high - low

    if normalscoresamples is not None:
        return scipy.stats.uniform.ppf(
            scipy.stats.norm.cdf(normalscoresamples), loc=low, scale=uscale
        )

    uniform_samples = generate_stratified_samples(numreals, rng)
    return scipy.stats.uniform.ppf(uniform_samples, loc=low, scale=uscale)


def draw_values_triangular(dist_parameters, numreals, rng, normalscoresamples=None):
    """Draws values from triangular distribution.
    Args:
        dist_parameters(list): [min, mode, max]
        numreals(int): number of realisations to draw
        rng: numpy.random.RandomState instance
        normalscoresamples(list): samples for correlated parameters
    Returns:
        list of values
    """
    status, msg = _check_dist_params_triang(dist_parameters)
    if not status:
        raise ValueError(msg)

    low = float(dist_parameters[0])
    mode = float(dist_parameters[1])
    high = float(dist_parameters[2])

    if high == low:  # collapsed distribution
        print(
            "Low and high parameters for triangular distribution"
            " are equal. Using constant {}".format(low)
        )
        if normalscoresamples is not None:
            values = scipy.stats.uniform.ppf(
                scipy.stats.norm.cdf(normalscoresamples), loc=low, scale=0
            )
        else:
            values = np.full(numreals, low)
    else:
        dist_scale = high - low
        shape = (mode - low) / dist_scale

        if normalscoresamples is not None:
            values = scipy.stats.triang.ppf(
                scipy.stats.norm.cdf(normalscoresamples),
                shape,
                loc=low,
                scale=dist_scale,
            )
        else:
            uniform_samples = generate_stratified_samples(numreals, rng)
            values = scipy.stats.triang.ppf(
                uniform_samples, shape, loc=low, scale=dist_scale
            )

    return values


def draw_values_pert(dist_parameters, numreals, rng, normalscoresamples=None):
    """Draws values from pert distribution.
    Args:
        dist_parameters(list): [min, mode, max, scale]
        where scale is only specified
        for a 4 parameter pert distribution
        numreals(int): number of realisations to draw
        rng: numpy.random.RandomState instance
        normalscoresamples(list): samples for correlated parameters
    Returns:
        list of values
    """
    status, msg = _check_dist_params_pert(dist_parameters)
    if not status:
        raise ValueError(msg)

    low = float(dist_parameters[0])
    mode = float(dist_parameters[1])
    high = float(dist_parameters[2])
    scale = (
        float(dist_parameters[3])
        if len(dist_parameters) == 4
        else 4  # pert 3 parameter distribution
    )

    if high == low:  # collapsed distribution
        print(
            "Low and high parameters for pert distribution"
            " are equal. Using constant {}".format(low)
        )
        if normalscoresamples is not None:
            values = scipy.stats.uniform.ppf(
                scipy.stats.norm.cdf(normalscoresamples), loc=low, scale=0
            )
        else:
            values = np.full(numreals, low)
    else:
        muval = (low + high + scale * mode) / (scale + 2)
        if np.isclose(muval, mode):
            alpha1 = (scale / 2) + 1
        else:
            alpha1 = ((muval - low) * (2 * mode - low - high)) / (
                (mode - muval) * (high - low)
            )
        alpha2 = alpha1 * (high - muval) / (muval - low)

        if normalscoresamples is not None:
            values = scipy.stats.beta.ppf(
                scipy.stats.norm.cdf(normalscoresamples), alpha1, alpha2
            )
        else:
            uniform_samples = generate_stratified_samples(numreals, rng)
            values = scipy.stats.beta.ppf(uniform_samples, alpha1, alpha2)

    # Scale the beta distribution to the desired range
    return values * (high - low) + low


def draw_values_loguniform(dist_parameters, numreals, rng, normalscoresamples=None):
    """Draws values from loguniform distribution.
    Args:
        dist_parameters(list): [minimum, maximum]
        numreals(int): number of realisations to draw
        rng: numpy.random.RandomState instance
        normalscoresamples(list): samples for correlated parameters
    Returns:
        list of values
    """
    status, msg = _check_dist_params_logunif(dist_parameters)
    if not status:
        raise ValueError(msg)

    low = float(dist_parameters[0])
    high = float(dist_parameters[1])

    if normalscoresamples is not None:
        values = scipy.stats.reciprocal.ppf(
            scipy.stats.norm.cdf(normalscoresamples), low, high
        )
    else:
        uniform_samples = generate_stratified_samples(numreals, rng)
        values = scipy.stats.reciprocal.ppf(uniform_samples, low, high)

    return values


def draw_values(distname, dist_parameters, numreals, rng, normalscoresamples=None):
    """
    Prepare scipy distributions with parameters
    Args:
        distname (str): distribution name 'normal', 'lognormal', 'triang',
        'uniform', 'logunif', 'discrete', 'pert'
        dist_parameters (list): list with parameters for distribution
        numreals (int): number of realizations to generate
        rng (numpy.random.RandomState): random number generator instance
        normalscoresamples (array, optional): samples for correlated distributions
    Returns:
        scipy.stats distribution with parameters
    """
    if distname[0:4].lower() == "norm":
        values = draw_values_normal(dist_parameters, numreals, rng, normalscoresamples)
    elif distname[0:4].lower() == "logn":
        values = draw_values_lognormal(
            dist_parameters, numreals, rng, normalscoresamples
        )
    elif distname[0:4].lower() == "unif":
        values = draw_values_uniform(dist_parameters, numreals, rng, normalscoresamples)
    elif distname[0:6].lower() == "triang":
        values = draw_values_triangular(
            dist_parameters, numreals, rng, normalscoresamples
        )
    elif distname[0:4].lower() == "pert":
        values = draw_values_pert(dist_parameters, numreals, rng, normalscoresamples)
    elif distname[0:7].lower() == "logunif":
        values = draw_values_loguniform(
            dist_parameters, numreals, rng, normalscoresamples
        )
    elif distname[0:5].lower() == "const":
        if normalscoresamples is not None:
            raise ValueError(
                "Parameter with const distribution "
                "was defined in correlation matrix "
                "but const distribution cannot "
                "be used with correlation. "
            )
        values = [dist_parameters[0]] * numreals
    elif distname[0:4].lower() == "disc":
        if normalscoresamples is not None:
            raise ValueError(
                "Parameter with discrete distribution "
                "was defined in correlation matrix, "
                "but discrete distribution cannot "
                "be used with correlation. "
            )
        status, result = sample_discrete(dist_parameters, numreals, rng)
        if status:
            values = result
        else:
            raise ValueError(result)
    else:
        raise ValueError(f"distribution name {distname} is not implemented")
    return values


def sample_discrete(dist_params, numreals, rng):
    """Sample from discrete distribution.
    Args:
        dist_params(list): parameters for distribution
        dist_params[0] is possible outcomes separated
        by comma
        dist_params[1] is probabilities for each outcome,
        separated by comma
        numreals (int): number of realisations to draw
        rng: numpy.random.RandomState instance
    Returns:
        tuple: (status, np.ndarray of values drawn from distribution)
    """
    status = True
    outcomes = re.split(",", dist_params[0])
    outcomes = [item.strip() for item in outcomes]

    if numreals == 0:
        return status, np.array([])

    if numreals < 0:
        raise ValueError("numreal must be a positive integer")

    if len(dist_params) == 2:  # non uniform
        weights = re.split(",", dist_params[1])
        if len(outcomes) != len(weights):
            raise ValueError(
                "Number of weights for discrete distribution "
                "is not the same as number of values."
            )

        try:
            probabilities = [float(weight) for weight in weights]
        except ValueError as e:
            raise ValueError(
                "All weights must be valid floating point numbers. "
                f"Got weights: {weights}"
            ) from e

        # Validate probabilities
        if not all(0 <= p <= 1 for p in probabilities):
            raise ValueError("All probabilities must be between 0 and 1")
        if not np.isclose(sum(probabilities), 1.0):
            raise ValueError("Probabilities must sum to 1")

        fractions = probabilities

    elif len(dist_params) == 1:  # uniform
        fractions = [1.0 / len(outcomes)] * len(outcomes)

    else:
        status = False
        values = "Wrong input for discrete distribution"
        return status, values

    uniform_samples = generate_stratified_samples(numreals, rng)

    cum_prob = np.cumsum(fractions)

    # Map samples to outcomes
    values = np.array([outcomes[np.searchsorted(cum_prob, s)] for s in uniform_samples])

    return status, values


def is_number(teststring):
    """Test if a string can be parsed as a float"""
    try:
        return not np.isnan(float(teststring))
    except ValueError:
        return False


def read_correlations(corr_dict, corrsheet):
    """Reading correlation info for a
    monte carlo sensitivity

    Args:
        corr_dict (OrderedDict): correlation info

    Returns:
        pd.DataFrame: Dataframe with correlations, parameter names
            as column and index
    """
    correlations = None
    filename = corr_dict["inputfile"]
    if corrsheet in corr_dict["sheetnames"]:
        if str(filename).endswith(".xlsx"):
            correlations = pd.read_excel(
                filename, corrsheet, index_col=0, engine="openpyxl"
            )
            correlations.dropna(axis=0, how="all", inplace=True)
            correlations = correlations.loc[
                :, ~correlations.columns.str.contains("^Unnamed")
            ]
        else:
            raise ValueError(
                "Correlation matrix filename should be on "
                "Excel format and end with .xlsx "
            )
    else:
        raise ValueError(
            "Corr_sheet {} specified but cannot be "
            "found in list of sheetnames".format(corrsheet)
        )

    return correlations
