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


def prepare_distribution(distname, dist_parameters):
    """
    Prepare scipy distributions with parameters

    TO DO:
        -Implement exceptions
        -Implement missing distributions:
            discrete uniform,
            discrete123,
            discrete uniform with weights

    Args:
        distname (str): distribution name 'normal',
                        'triang', 'uniform' or 'logunif'
    Returns:
        scipy.stats distribution with parameters
    """
    if distname == 'normal':
        dist_mean = dist_parameters[0]
        dist_stddev = dist_parameters[1]
        if is_number(dist_mean) and is_number(dist_stddev):
            return scipy.stats.norm(float(dist_mean), float(dist_stddev))
    elif distname == 'uniform':
        low = dist_parameters[0]
        high = dist_parameters[1]
        uscale = high - low
        if is_number(low) and is_number(high):
            return scipy.stats.uniform(loc=low, scale=uscale)
    elif distname == 'triang':
        low = dist_parameters[0]
        mode = dist_parameters[1]
        high = dist_parameters[2]
        dist_scale = high - low
        shape = (mode-low)/dist_scale
        if is_number(low) and is_number(mode) and is_number(high):
            return scipy.stats.triang(shape, loc=low, scale=dist_scale)
    elif distname == 'logunif':
        low = dist_parameters[0]
        high = dist_parameters[1]
        if is_number(low) and is_number(high):
            loglow = numpy.log10(low)
            loghigh = numpy.log10(high)
            logscale = loghigh - loglow
            print(loglow, loghigh, logscale)
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


def is_number(teststring):
    """ Test if a string can be parsed as a float"""
    try:
        if not numpy.isnan(float(teststring)):
            return True
        return False  # It was a "number", but it was NaN.
    except ValueError:
        return False
