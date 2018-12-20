# -*- coding: utf-8 -*-
"""Test code for RMS volumetrics parsing"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import os
import glob

from fmu import config
from fmu.tools.rms import volumetrics 

fmux = config.etc.Interaction()
logger = fmux.basiclogger(__name__)

if not fmux.testsetup():
    raise SystemExit()


def test_volumetrics():
    """Test parsing of many real examples from RMS"""

    if '__file__' in globals():
        # Easen up copying test code into interactive sessions
        testdir = os.path.dirname(os.path.abspath(__file__))
    else:
        testdir = os.path.abspath('.')

    volfiles = glob.glob(testdir + '/data/rmsvolumetrics/*txt')

    for file in volfiles:
        df = volumetrics.rmsvolumetrics_txt2df(file)

        # Check that we did get some data: 
        assert len(df) > 0
        
        # Check for no non-uppercase column names:
        collist = list(df.columns)
        assert [x.upper() for x in collist] == collist

        # Check for no string 'Totals' in any cell
        assert 'Totals' not in str(df)
        
    
