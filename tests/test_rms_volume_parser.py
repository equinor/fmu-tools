# -*- coding: utf-8 -*-
"""Testing fmu-tools."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import fmu.config as config
from fmu.tools.parsers import RmsVolumeFileParser
import pandas as pd
import os

fmux = config.etc.Interaction()
logger = fmux.basiclogger(__name__)

# always this statement
if not fmux.testsetup():
    raise SystemExit()

def test_rms_volume_parser():
	scratchdir = '/scratch/fmu/sago/3_r001_reek_seismatch'
	real = 'realization-0'
	iteration = 'iter-0'
	voldir = 'share/results/volumes'
	volfile = 'simgrid_vol_oil_1.txt'

	fn = os.path.join(scratchdir, real, iteration, voldir, volfile)

	data = RmsVolumeFileParser(fn).as_df

	assert data['BULK_OIL'][0] == 323940508.21
	assert data['STOIIP_OIL'].mean() == 8605391.909999998