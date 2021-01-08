"""Testing qcforward method gridquality"""

import pathlib
import pytest
import pandas as pd

import fmu.tools.qcforward as qcf

# filedata
PATH = pathlib.Path(".").resolve().as_posix()
GRIDFILE = "../xtgeo-testdata/3dgrids/reek/reek_sim_grid.roff"
REPORT = "/tmp/somefile_gridquality.csv"
SOMEYAML = "/tmp/somefile.yml"

ACTIONS = {
    "minangle_topbase": [
        {"warn": "allcells > 1% when < 80", "stop": "allcells > 1% when < 50"},
        {"warn": "allcells > 50% when < 85", "stop": "allcells > 10% when < 50"},
    ],
    "collapsed": [{"warn": "allcells > 20%", "stop": "allcells > 50%"}],
}


DATA1 = {
    "nametag": "MYDATA1",
    "verbosity": "info",
    "path": PATH,
    "grid": GRIDFILE,
    "actions": ACTIONS,
    "report": {"file": REPORT, "mode": "write"},
    "dump_yaml": SOMEYAML,
}


def test_gridquality_asfiles():
    """Testing grid quality using files."""
    qcf.grid_quality(DATA1)

    dfr = pd.read_csv(REPORT)
    assert dfr.loc[0, "WARN%"] == pytest.approx(2.715, 0.01)

    pathlib.Path(REPORT).unlink()
    pathlib.Path(SOMEYAML).unlink()


def test_gridquality_asfiles_shall_stop():
    """Testing gridquality using files which should trigger a stop.

    Here. also abbrevation "all" should here work as "allcells".
    """
    newdata = DATA1.copy()
    newdata["actions"] = {"faulted": [{"warn": "all > 20%", "stop": "all > 3%"}]}

    with pytest.raises(SystemExit):
        qcf.grid_quality(newdata)

    pathlib.Path(REPORT).unlink()
    pathlib.Path(SOMEYAML).unlink()
