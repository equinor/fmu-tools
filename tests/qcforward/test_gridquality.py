"""Testing qcforward method gridquality"""

from pathlib import Path
from typing import Any

import pandas as pd
import pytest

import fmu.tools.qcforward as qcf


@pytest.fixture()
def gridfile_data(tmp_path: Path, testdata_path: Path) -> dict[str, Any]:
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
        "path": str(Path.cwd()),
        "grid": gridfile,
        "actions": ACTIONS,
        "report": {"file": str(tmp_path / "somefile_gradquality.csv"), "mode": "write"},
        "dump_yaml": str(tmp_path / "somefile.yml"),
    }


def test_gridquality_asfiles(gridfile_data: dict[str, Any]) -> None:
    """Testing grid quality using files."""
    qcf.grid_quality(gridfile_data)

    dfr = pd.read_csv(gridfile_data["report"]["file"])
    assert dfr.loc[0, "WARN%"] == pytest.approx(2.715, 0.01)


def test_gridquality_asfiles_shall_stop(gridfile_data: dict[str, Any]) -> None:
    """Testing gridquality using files which should trigger a stop.

    Here. also abbrevation "all" should here work as "allcells".
    """
    newdata = gridfile_data.copy()
    newdata["actions"] = {"faulted": [{"warn": "all > 20%", "stop": "all > 3%"}]}

    with pytest.raises(SystemExit):
        qcf.grid_quality(newdata)
