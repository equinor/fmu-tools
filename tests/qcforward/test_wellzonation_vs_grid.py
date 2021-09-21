"""Testing qcforward method wellzonation vs grid"""

import pathlib
from os.path import abspath

import fmu.tools.qcforward as qcf
import pandas as pd
import pytest

# filedata
PATH = abspath(".")  # normally not needed; here due to pytest fixture tmpdir
GRIDFILE = "../xtgeo-testdata/3dgrids/reek/reek_sim_grid.roff"
ZONENAME = "Zone"
ZONEFILE = "../xtgeo-testdata/3dgrids/reek/reek_sim_zone.roff"
WELLFILES = [
    "../xtgeo-testdata/wells/reek/1/OP*.w",
    "../xtgeo-testdata/wells/reek/1/WI*.w",
]

ZONELOGNAME = "Zonelog"
PERFLOGNAME = "PERF"
REPORT = abspath("/tmp/somefile.csv")
SOMEYAML = abspath("/tmp/somefile.yml")

DATA1 = {
    "nametag": "MYDATA1",
    "verbosity": "debug",
    "path": PATH,
    "grid": GRIDFILE,
    "gridprops": [[ZONENAME, ZONEFILE]],
    "wells": WELLFILES,
    "zonelog": {"name": ZONELOGNAME, "range": [1, 3]},
    "depthrange": [1580, 9999],
    "actions": [
        {"warn": "anywell < 50%", "stop": "anywell < 20%"},
        {"warn": "allwells < 80%", "stop": "allwells < 20%"},
    ],
    "report": {"file": REPORT, "mode": "write"},
    "dump_yaml": SOMEYAML,
}


def test_zonelog_vs_grid_asfiles():
    """Testing the zonelog vs grid functionality using files"""

    qcf.wellzonation_vs_grid(DATA1)

    # now read the dump file:
    qcf.wellzonation_vs_grid(SOMEYAML)

    dfr = pd.read_csv(REPORT, index_col="WELL")
    assert dfr.loc["all", "MATCH%"] == pytest.approx(63.967, 0.01)

    pathlib.Path(REPORT).unlink()
    pathlib.Path(SOMEYAML).unlink()


def test_zonelog_vs_grid_asfiles_shall_stop():
    """Testing the zonelog vs grid functionality using files"""

    newdata = DATA1.copy()
    newdata["actions"] = [{"warn": "any < 90%", "stop": "any < 80%"}]

    with pytest.raises(SystemExit):
        qcf.wellzonation_vs_grid(newdata)

    pathlib.Path(REPORT).unlink()
    pathlib.Path(SOMEYAML).unlink()


def test_zonelog_vs_grid_asfiles_reuse_instance():
    """Testing reusing the instance"""

    newdata = DATA1.copy()
    newdata["actions"] = [{"warn": "anywell < 33%", "stop": "anywell < 22%"}]

    job = qcf.WellZonationVsGrid()
    job.run(DATA1)
    job.run(newdata, reuse=True)

    pathlib.Path(REPORT).unlink()
    pathlib.Path(SOMEYAML).unlink()


def test_perflog_vs_grid_asfiles():
    """
    Testing the perforation log as zonelog filter vs grid functionality using files.

    When a perflog is present, it means in this example
    that all intervals within a PERFLOG range will have a zonelog vs grid check,
    i.e. the PERFLOG acts a contrain/filter. In intervals with missing PERFLOG,
    or if PERFLOG is outside range, then zonelog vs grid checks is ignored.


    """

    mydata = DATA1.copy()
    mydata["perflog"] = {"name": PERFLOGNAME, "range": [1, 5]}

    wellcheck = qcf.WellZonationVsGrid()
    wellcheck.run(mydata)

    dfr = pd.read_csv(REPORT, index_col="WELL")

    print(dfr)

    assert dfr.loc["OP_1_PERF", "MATCH%"] == pytest.approx(80.701, 0.01)

    pathlib.Path(REPORT).unlink()
    pathlib.Path(SOMEYAML).unlink()
