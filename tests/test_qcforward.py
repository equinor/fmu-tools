"""Testing qcforward methods"""

from __future__ import absolute_import, division, print_function  # PY2

import os
from os.path import abspath
import pytest
import xtgeo
from fmu.tools import qcforward as qcf

# EQUINOR ONLY
QEQUINOR = False
if "KOMODO_RELEASE" in os.environ:
    QEQUINOR = True
equinor = pytest.mark.skipif(not QEQUINOR, reason="Equinor internal test set")

# EXTERNAL ROXAR API ONLY
QROXAR = False
if "ROXENV" in os.environ:
    QROXAR = True
roxarapi = pytest.mark.skipif(not QROXAR, reason="Roxar API is present")


# ======================================================================================
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

# --------------------------------------------------------------------------------------
# RMS project data
TESTPATH = abspath("../xtgeo-testdata-equinor/data/rmsprojects")
PROJ = dict()
PROJ["1.3"] = os.path.join(TESTPATH, "reek.rms11.1.0")
GRID = "Geogrid"
ZONENAME = "Zone"
WELLS = ["OP*.w", "WI*.w"]
ZONELOGNAME = "Zonelog"

# ======================================================================================


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
    }

    wellcheck = qcf.QCForward()
    wellcheck.wellzonation_vs_grid(data)

    # check private members
    assert isinstance(wellcheck._grid, xtgeo.Grid)
    assert isinstance(wellcheck._gridzone, xtgeo.GridProperty)
    assert isinstance(wellcheck._wells, xtgeo.Wells)


@equinor
@roxarapi
def test_zonelog_vs_grid_asrms():
    """Testing the zonelog vs grid functionality inside RMS"""

    # data = {
    #     "verbosity": "debug",
    #     "grid": "Geogrid",
    #     "zone": "Zone",
    #     "wells": WELLS,
    #     "zonelogname": ZONELOGNAME,
    #     "zonelogrange": [1, 3],  # inclusive range at both ends
    #     "depthrange": [1580, 9999],
    #     "actions_each": {"warnthreshold": 50, "stopthreshold": 40},
    #     "actions_all": {"warnthreshold": 80, "stopthreshold": 60},
    # }

    myqc = qcf.QCForward()

    assert isinstance(myqc, qcf.QCForward)
