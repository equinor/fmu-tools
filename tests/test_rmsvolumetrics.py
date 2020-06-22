# -*- coding: utf-8 -*-
"""Test code for RMS volumetrics parsing"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import os
import sys
import glob
import subprocess

import pytest

import pandas as pd

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


@pytest.mark.integration
def test_commandlineclient_installed():
    """Test endpoint is installed"""
    assert subprocess.check_output(["rmsvolumetrics2csv", "-h"])


@pytest.mark.integration
def test_commandlineclient(tmpdir):
    """Test endpoint"""

    testdir = os.path.dirname(os.path.abspath(__file__))
    tmpdir.chdir()

    sys.argv = [
        "rmsvolumetrics2csv",
        os.path.join(testdir, "data/rmsvolumetrics/1_geogrid_vol_oil_1.txt"),
        "--output",
        "geogrid_oil.csv",
    ]
    volumetrics.rmsvolumetrics2csv_main()

    disk_df = pd.read_csv("geogrid_oil.csv")
    assert "STOIIP_OIL" in disk_df

    sys.argv = [
        "rmsvolumetrics2csv",
        os.path.join(testdir, "data/rmsvolumetrics/14_geo_gas_1.txt"),
        "--output",
        "geo_gas.csv",
    ]
    volumetrics.rmsvolumetrics2csv_main()
    disk_df = pd.read_csv("geo_gas.csv")
    assert "GIIP_GAS" in disk_df

    # Test that --phase will override the inferral

    sys.argv = [
        "rmsvolumetrics2csv",
        os.path.join(testdir, "data/rmsvolumetrics/14_geo_gas_1.txt"),
        "--output",
        "geo_foophase.csv",
        "--phase",
        "FOOBAR",
    ]
    volumetrics.rmsvolumetrics2csv_main()
    disk_df = pd.read_csv("geo_foophase.csv")
    assert "GIIP_FOOBAR" in disk_df

    # Test that parent directories will be created for output
    sys.argv = [
        "rmsvolumetrics2csv",
        os.path.join(testdir, "data/rmsvolumetrics/14_geo_gas_1.txt"),
        "--output",
        "foo/bar/com.csv",
    ]
    volumetrics.rmsvolumetrics2csv_main()
    disk_df = pd.read_csv("foo/bar/com.csv")
    assert "GIIP_GAS" in disk_df
