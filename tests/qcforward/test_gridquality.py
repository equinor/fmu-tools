"""Testing qcforward method gridquality"""

import pathlib

import pandas as pd
import pytest

import fmu.tools.qcforward as qcf

PATH = pathlib.Path(".").resolve().as_posix()
REPORT = "/tmp/somefile_gridquality.csv"
SOMEYAML = "/tmp/somefile.yml"


@pytest.fixture()
def gridfile_data(testdata_path):
    gridfile = str(testdata_path / "3dgrids/reek/reek_sim_grid.roff")

    ACTIONS = {
        "minangle_topbase": [
            {"warn": "allcells > 1% when < 80", "stop": "allcells > 1% when < 50"},
            {"warn": "allcells > 50% when < 85", "stop": "allcells > 10% when < 50"},
        ],
        "collapsed": [{"warn": "allcells > 20%", "stop": "allcells > 50%"}],
    }

    return {
        "nametag": "MYDATA1",
        "verbosity": "info",
        "path": PATH,
        "grid": gridfile,
        "actions": ACTIONS,
        "report": {"file": REPORT, "mode": "write"},
        "dump_yaml": SOMEYAML,
    }


def test_gridquality_asfiles(gridfile_data):
    """Testing grid quality using files."""
    qcf.grid_quality(gridfile_data)

    dfr = pd.read_csv(REPORT)
    assert dfr.loc[0, "WARN%"] == pytest.approx(2.715, 0.01)

    pathlib.Path(REPORT).unlink()
    pathlib.Path(SOMEYAML).unlink()


def test_gridquality_asfiles_shall_stop(gridfile_data):
    """Testing gridquality using files which should trigger a stop.

    Here. also abbrevation "all" should here work as "allcells".
    """
    newdata = gridfile_data.copy()
    newdata["actions"] = {"faulted": [{"warn": "all > 20%", "stop": "all > 3%"}]}

    with pytest.raises(SystemExit):
        qcf.grid_quality(newdata)

    pathlib.Path(REPORT).unlink()
    pathlib.Path(SOMEYAML).unlink()
