# -*- coding: utf-8 -*-
"""Test code for RMS volumetrics parsing"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import os
import glob

from fmu.tools.rms import volumetrics


def test_volumetrics():
    """Test parsing of many real examples from RMS"""

    if "__file__" in globals():
        # Easen up copying test code into interactive sessions
        testdir = os.path.dirname(os.path.abspath(__file__))
    else:
        testdir = os.path.abspath(".")

    volfiles = glob.glob(testdir + "/data/rmsvolumetrics/*txt")

    for file in volfiles:
        dframe = volumetrics.rmsvolumetrics_txt2df(file)

        # Check that we did get some data:
        assert len(dframe) > 0

        # Check for no non-uppercase column names:
        collist = list(dframe.columns)
        assert [x.upper() for x in collist] == collist

        # Check for no string 'Totals' in any cell
        assert "Totals" not in dframe.to_string()

    # Test zone renamer:
    def myrenamer(a_zone):
        """Callback function for zone renaming"""
        return a_zone.replace("Larsson", "E")

    dframe = volumetrics.rmsvolumetrics_txt2df(
        testdir + "/data/rmsvolumetrics/" + "14_geo_gas_1.txt", zonerenamer=myrenamer
    )
    assert "Larsson" not in dframe.to_string()
    assert "E3_1" in dframe.to_string()

    # Test columnrenamer:
    columnrenamer = {"Region index": "FAULTSEGMENT"}  # this will override
    dframe = volumetrics.rmsvolumetrics_txt2df(
        testdir + "/data/rmsvolumetrics/" + "14_geo_gas_1.txt",
        columnrenamer=columnrenamer,
    )
    assert "FAULTSEGMENT" in dframe.columns
