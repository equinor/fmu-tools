"""Testing qcforward method blockedwells vs gridprops"""

from copy import deepcopy
from os.path import abspath

import pandas as pd
import pytest

from fmu.tools import qcforward as qcf

# filedata
PATH = abspath(".")  # normally not needed; here due to pytest fixture tmpdir
COMPARE = {"Facies": "FACIES", "PHIT": "PHIT"}


@pytest.fixture(name="datainput")
def fixture_datainput(tmp_path, testdata_path):
    gridfile = str(testdata_path / "3dgrids/drogon/3/valysar.roff")
    bwellfiles = [str(testdata_path / "wells/drogon/3/valysar*.bw")]
    return {
        "nametag": "MYDATA1",
        "verbosity": "info",
        "path": PATH,
        "grid": gridfile,
        "report": tmp_path / "bw_vs_gprop.csv",
        "compare": COMPARE,
        "gridprops": [["FACIES", gridfile], ["PHIT", gridfile]],
        "bwells": bwellfiles,
        "tolerance": 0.01,
        "actions": [
            {"warn": "anywell < 80%", "stop": "anywell < 75%"},
            {"warn": "allwells < 90%", "stop": "allwells < 85%"},
        ],
    }


def test_bw_vs_gridprops_asfiles(datainput):
    """Testing the zonelog vs grid functionality using files"""

    job = qcf.BlockedWellsVsGridProperties()
    job.run(datainput)

    rep = pd.read_csv(datainput["report"])
    rep.sort_values(by=["WELL", "COMPARE(BW:MODEL)"], inplace=True, ignore_index=True)
    # pylint: disable=no-member, unsubscriptable-object
    assert rep.iloc[3].at["MATCH%"] == 85.0
    assert rep.iloc[3].at["STATUS"] == "OK"

    wel = "WELL"
    cmp = "COMPARE(BW:MODEL)"

    ser = rep.loc[(rep[wel] == "55_33-A-6") & (rep[cmp] == "PHIT:PHIT"), "MATCH%"]
    ser.reset_index(drop=True, inplace=True)
    assert ser[0] == 100.0


def test_bw_vs_gridprops_asfiles_shall_stop(tmp_path, datainput):
    """Testing the zonelog vs grid functionality using files, shall stop."""

    job = qcf.BlockedWellsVsGridProperties()
    data = deepcopy(datainput)
    data["actions"] = [
        {"warn": "anywell < 80%", "stop": "anywell < 86%"},
        {"warn": "allwells < 98%", "stop": "allwells < 96%"},
    ]
    data["report"] = tmp_path / "failedreport.csv"

    with pytest.raises(SystemExit) as err:
        job.run(data)
    assert "STOP criteria is found" in str(err)
    rep = pd.read_csv(data["report"])
    # pylint: disable=no-member, unsubscriptable-object
    rep.sort_values(by=["WELL", "COMPARE(BW:MODEL)"], inplace=True, ignore_index=True)
    assert rep.iloc[3].at["MATCH%"] == 85.0
    assert rep.iloc[3].at["STATUS"] == "STOP"


def test_bw_vs_gridprops_asfiles_change_tolerance(tmp_path, datainput):
    """Testing the zonelog vs grid functionality using files, iterate tolerance."""

    job = qcf.BlockedWellsVsGridProperties()
    data = deepcopy(datainput)
    data["actions"] = [
        {"warn": "anywell < 88%", "stop": "anywell < 86%"},
        {"warn": "allwells < 98%", "stop": "allwells < 98%"},
    ]
    data["report"] = tmp_path / "failedreport2.csv"
    data["tolerance"] = {"abs": 0.001}

    with pytest.raises(SystemExit) as err:
        job.run(data)
    assert "STOP criteria is found" in str(err)
    rep = pd.read_csv(data["report"])
    # pylint: disable=no-member, unsubscriptable-object
    rep.sort_values(by=["WELL", "COMPARE(BW:MODEL)"], inplace=True, ignore_index=True)
    assert rep.iloc[3].at["MATCH%"] == 85.0
    assert rep.iloc[3].at["STATUS"] == "STOP"
