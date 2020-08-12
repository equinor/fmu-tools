"""Testing qcforward methods"""

from __future__ import absolute_import, division, print_function  # PY2

from os.path import abspath
from fmu.tools import qcforward as qcf
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
        "actions_each": {"warnthreshold": 50, "stopthreshold": 30},
        "actions_all": {"warnthreshold": 80, "stopthreshold": 60},
        "report": ["somereport.csv", "write"],
    }

    wellcheck = qcf.QCForward()
    wellcheck.wellzonation_vs_grid(data)

    # check private members
    assert isinstance(wellcheck._grid, xtgeo.Grid)
    assert isinstance(wellcheck._gridzone, xtgeo.GridProperty)
    assert isinstance(wellcheck._wells, xtgeo.Wells)
