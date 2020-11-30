"""Test code for RMS volumetrics parsing"""

import sys
import subprocess
from pathlib import Path

import pytest

import pandas as pd

from fmu.tools.rms import volumetrics


TESTDIR = Path(__file__).parent / "volumetricsdata"


def test_volumetrics():
    """Test parsing of many real examples from RMS"""

    for filename in TESTDIR.glob("*.txt"):
        dframe = volumetrics.rmsvolumetrics_txt2df(filename)

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
        TESTDIR / "14_geo_gas_1.txt", zonerenamer=myrenamer
    )
    assert "Larsson" not in dframe.to_string()
    assert "E3_1" in dframe.to_string()

    # Test columnrenamer:
    columnrenamer = {"Region index": "FAULTSEGMENT"}  # this will override
    dframe = volumetrics.rmsvolumetrics_txt2df(
        TESTDIR / "14_geo_gas_1.txt",
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

    tmpdir.chdir()

    sys.argv = [
        "rmsvolumetrics2csv",
        str(TESTDIR / "1_geogrid_vol_oil_1.txt"),
        "--output",
        "geogrid_oil.csv",
    ]
    volumetrics.rmsvolumetrics2csv_main()

    disk_df = pd.read_csv("geogrid_oil.csv")
    assert "STOIIP_OIL" in disk_df

    sys.argv = [
        "rmsvolumetrics2csv",
        str(TESTDIR / "14_geo_gas_1.txt"),
        "--output",
        "geo_gas.csv",
    ]
    volumetrics.rmsvolumetrics2csv_main()
    disk_df = pd.read_csv("geo_gas.csv")
    assert "GIIP_GAS" in disk_df

    # Test that --phase will override the inferral

    sys.argv = [
        "rmsvolumetrics2csv",
        str(TESTDIR / "14_geo_gas_1.txt"),
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
        str(TESTDIR / "14_geo_gas_1.txt"),
        "--output",
        "foo/bar/com.csv",
    ]
    volumetrics.rmsvolumetrics2csv_main()
    disk_df = pd.read_csv("foo/bar/com.csv")
    assert "GIIP_GAS" in disk_df
