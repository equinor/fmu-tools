# -*- coding: utf-8 -*-
"""Testing fmu-ensemble."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import os
import pandas as pd

from fmu import config
from fmu.tools.sensitivities import calc_tornadoinput, find_combinations
from collections import OrderedDict

fmux = config.etc.Interaction()
logger = fmux.basiclogger(__name__)

if not fmux.testsetup():
    raise SystemExit()


def test_combine_selectors():

    """Test finding all combinations of values in ordered dictionary"""

    # Short test on combination of two lists
    shortdict = OrderedDict()
    shortdict['key1'] = [1, 2, 3]
    shortdict['key2'] = ['a', 'b', 'c']
    shortcomb = find_combinations(shortdict)
    assert len(shortcomb) == 9

    # Test on combinations of lists of lists, typical tornado usage
    selections = OrderedDict()
    selections['ITER'] = [
                         ['iter-0']
                         ]
    selections['ZONE'] = [
                         ['Nansen', 'Larsson'],
                         ['Eiriksson2.13'],
                         ['Eiriksson2.12'],
                         ['all']
                         ]

    selections['REGION'] = [
                           ['oil_zone_Nansen_Larsson'],
                           ['gas_zone_P1'],
                           ['all']
                           ]

    comb = find_combinations(selections)

    # Check correct number of combinations 1*4*3 and result of (1,1,1)
    assert len(comb) == 12
    assert comb[0] == [['iter-0'], ['Nansen', 'Larsson'], ['oil_zone_Nansen_Larsson']]


def test_calc_tornadoinput():
    """Test calculating values for webviz TornadoPlot"""

    if '__file__' in globals():
        # Easen up copying test code into interactive sessions
        testdir = os.path.dirname(os.path.abspath(__file__))
    else:
        testdir = os.path.abspath('.')

    # Read file with summary of design
    summary = pd.read_csv(
              testdir +
              '/data/sensitivities/distributions/designsummary.csv',
              na_values='nan')
    des_summary = summary.where(pd.notnull(summary), None)

    # Read resultfile for the test ensemble
    results = pd.read_csv(
              testdir +
              '/data/sensitivities/results/geovolumes_collected.csv')

    # Calculate and check results of one tornado calculation
    (tornadotable, ref_value) = calc_tornadoinput(
                                des_summary, results,
                                'STOIIP_OIL',
                                ['ITER', 'ZONE', 'REGION'],
                                [
                                 ['iter-0'],
                                 ['Nansen', 'Larsson'],
                                 ['oil_zone_Nansen_Larsson']
                                ],
                                'rms_seed', 'percentage')

    assert int(tornadotable['low'].sum()) == -21
    assert int(tornadotable['high'].sum()) == 11
    assert int(ref_value) == 9330662

    # Check summing over all zones and regions before calculations
    (tornadotable, ref_value) = calc_tornadoinput(
                                des_summary, results,
                                'STOIIP_OIL',
                                ['ITER', 'ZONE', 'REGION'],
                                [['all'], ['all'], ['all']],
                                'rms_seed', 'absolute')

    assert int(tornadotable['low'].sum()) == -2142167
    assert int(tornadotable['high'].sum()) == 1478053
    assert int(ref_value) == 12855200
