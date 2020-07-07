"""Testing qcforward methods"""

from __future__ import absolute_import, division, print_function  # PY2

from fmu.tools import qcforward as qcf
import pytest
import xtgeo

GRIDFILE = "tests/data/xtgeo-testdata/3dgrids/reek/reek_sim_grid.roff"
ZONENAME = "Zone"
ZONEFILE = "tests/data/xtgeo-testdata/3dgrids/reek/reek_sim_zone.roff"
WELLFILES = [
    "tests/data/xtgeo-testdata/wells/reek/1/OP*.w",
    "tests/data/xtgeo-testdata/wells/reek/1/WI*.w",
]

ZONELOGNAME = "Zonelog"
MDLOGNAME = "MDepth"


@pytest.fixture(scope="module")
def test_zonelog_vs_grid_asfiles():
    """Testing the zonelog vs grid functionality using files"""

    data = {
        "grid": GRIDFILE,
        "zone": {ZONENAME: ZONEFILE},
        "wells": WELLFILES,
        "zonelogname": {ZONENAME: ZONELOGNAME},
        "mdlogname": MDLOGNAME,
    }

    wellcheck = qcf.QCForward()
    wellcheck.wellzonation_vs_grid(data)

    # check private members
    assert isinstance(wellcheck._grid, xtgeo.Grid)
    assert isinstance(wellcheck._gridzone, xtgeo.GridProperty)


def test_zonelog_vs_grid_asrms():
    """Testing the zonelog vs grid functionality inside RMS"""

    myqc = qcf.QCForward()

    assert isinstance(myqc, qcf.QCForward)
