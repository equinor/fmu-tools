"""Test code for RMS volumetrics parsing"""

import sys
import subprocess
from pathlib import Path

import pytest

import pandas as pd

from fmu.tools.rms import volumetrics


TESTDIR = Path(__file__).parent / "volumetricsdata"


@pytest.mark.parametrize(
    "multiline_str, filename, expected_df",
    [
        pytest.param(
            "",
            "foo.txt",
            None,
            marks=pytest.mark.xfail(raises=pd.errors.EmptyDataError),
        ),
        pytest.param(
            "foo bar",
            "foo.txt",
            None,
            marks=pytest.mark.xfail(raises=pd.errors.EmptyDataError),
        ),
        pytest.param(
            "Zone Bulk\nUpper 1",
            "foo.txt",
            pd.DataFrame([{"BULK": 1}]),
            marks=pytest.mark.xfail(
                raises=ValueError, reason="Not able to guess phase"
            ),
        ),
        pytest.param(
            "Zone Bulk\nUpper 1",
            "oil.txt",
            # This "fails" as there was not a double space between Zone and Bulk
            pd.DataFrame([{"Zone Bulk": "Upper 1"}]),
        ),
        (
            # Two spaces:
            "Zone  Bulk\nUpper  1.0",
            "oil.txt",
            pd.DataFrame([{"ZONE": "Upper", "BULK_OIL": 1.0}]),
        ),
        (
            # Three spaces:
            "Zone   Bulk\nUpper  1.0",
            "oil.txt",
            pd.DataFrame([{"ZONE": "Upper", "BULK_OIL": 1.0}]),
        ),
        (
            # Tabs don't work:
            "Zone\tBulk\nUpper\t1.0",
            "oil.txt",
            pd.DataFrame([{"Zone\tBulk": "Upper\t1.0"}]),
        ),
        (
            "Zone  Bulk\nUpper  1.0",
            "gas.txt",
            pd.DataFrame([{"ZONE": "Upper", "BULK_GAS": 1.0}]),
        ),
        (
            # All supported columns:
            "Zone  Region index  Facies  License boundaries  "
            "Bulk  Net  Hcpv  Pore  Stoiip  Assoc.Gas\n"
            "Upper  West  GoodSand  NO  2  1  1  1  1  0.1",
            "oil.txt",
            pd.DataFrame(
                [
                    {
                        "ZONE": "Upper",
                        "REGION": "West",
                        "FACIES": "GoodSand",
                        "LICENSE": "NO",
                        "BULK_OIL": 2,
                        "NET_OIL": 1,
                        "HCPV_OIL": 1,
                        "PORV_OIL": 1,
                        "STOIIP_OIL": 1,
                        "ASSOCIATEDGAS_OIL": 0.1,
                    }
                ]
            ),
        ),
        (
            # All supported columns:
            "Zone  Region index  Facies  License boundaries  "
            "Bulk  Net  Hcpv  Pore  Giip  Assoc.Liquid\n"
            "Upper  West  GoodSand  NO  2  1  1  1  1  0.1",
            "gas.txt",
            pd.DataFrame(
                [
                    {
                        "ZONE": "Upper",
                        "REGION": "West",
                        "FACIES": "GoodSand",
                        "LICENSE": "NO",
                        "BULK_GAS": 2,
                        "NET_GAS": 1,
                        "HCPV_GAS": 1,
                        "PORV_GAS": 1,
                        "GIIP_GAS": 1,
                        "ASSOCIATEDOIL_GAS": 0.1,
                    }
                ]
            ),
        ),
    ],
)
def test_rms_to_volumetrics(multiline_str, filename, expected_df, tmpdir):
    tmpdir.chdir()
    Path(filename).write_text(multiline_str)
    pd.testing.assert_frame_equal(
        volumetrics.rmsvolumetrics_txt2df(filename), expected_df, check_like=True
    )


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
