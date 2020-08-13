"""Testing qcforward methods"""

from __future__ import absolute_import, division, print_function  # PY2

import os
from os.path import abspath
from fmu.tools import qcforward as qcf
import pytest
import pandas as pd
import xtgeo

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
REPORT = abspath("./somefile.csv")


def test_zonelog_vs_grid_asfiles():
    """Testing the zonelog vs grid functionality using files"""

    data = {
        "verbosity": "debug",
        "path": PATH,
        "grid": GRIDFILE,
        "zone": {ZONENAME: ZONEFILE},
        "wells": WELLFILES,
        "zonelogname": ZONELOGNAME,
        "zonelogrange": [1, 3],  # inclusive range at both ends
        "depthrange": [1580, 9999],
        "actions_each": {"warnthreshold": 50, "stopthreshold": 20},
        "actions_all": {"warnthreshold": 80, "stopthreshold": 20},
        "report": {"file": REPORT, "mode": "write"},
        "dump_yaml": "somefile.yml",
    }

    wellcheck = qcf.QCForward()
    wellcheck.wellzonation_vs_grid(data)

    # check private members
    assert isinstance(wellcheck._grid, xtgeo.Grid)
    assert isinstance(wellcheck._gridzone, xtgeo.GridProperty)
    assert isinstance(wellcheck._wells, xtgeo.Wells)

    # now read the dump file:
    wellcheck.wellzonation_vs_grid("somefile.yml")

    dfr = pd.read_csv(REPORT)
    print(dfr)
    assert dfr.loc[11, "MATCH"] == pytest.approx(58.15, 0.01)
    os.unlink("somefile.yml")
    os.unlink(REPORT)


def test_zonelog_vs_grid_asfiles_shall_stop():
    """Testing the zonelog vs grid functionality using files"""

    data = {
        "verbosity": "debug",
        "path": PATH,
        "grid": GRIDFILE,
        "zone": {ZONENAME: ZONEFILE},
        "wells": WELLFILES,
        "zonelogname": ZONELOGNAME,
        "zonelogrange": [1, 3],  # inclusive range at both ends
        "depthrange": [1580, 9999],
        "actions_each": {"warnthreshold": 50, "stopthreshold": 70},
        "actions_all": {"warnthreshold": 80, "stopthreshold": 70},
    }

    wellcheck = qcf.QCForward()

    with pytest.raises(SystemExit):
        wellcheck.wellzonation_vs_grid(data)
