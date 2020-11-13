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
        {"warn": "if_>_1%_<_80deg", "stop": "if_>_1%_<_50deg"},
        {"warn": "if_>_50%_<_85deg", "stop": "if_>_10%_<_50deg"},
    ],
    "collapsed": [{"warn": "if_>_20%", "stop": "if_>_50%"}],
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
    """Testing the zonelog vs grid functionality using files"""

    qcf.grid_quality(DATA1)

    dfr = pd.read_csv(REPORT)
    assert dfr.loc[0, "WARN%"] == pytest.approx(2.715, 0.01)

    pathlib.Path(REPORT).unlink()
    pathlib.Path(SOMEYAML).unlink()


def test_zonelog_vs_grid_asfiles_shall_stop():
    """Testing the zonelog vs grid functionality using files"""

    newdata = DATA1.copy()
    newdata["actions"] = {"faulted": [{"warn": "if_>_20%", "stop": "if_>_3%"}]}

    with pytest.raises(SystemExit):
        qcf.grid_quality(newdata)

    pathlib.Path(REPORT).unlink()
    pathlib.Path(SOMEYAML).unlink()
