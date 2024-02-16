"""Testing qcdata loading of XTGeo data"""

from os.path import abspath

import pytest
import xtgeo
from fmu.tools.qcdata import QCData

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
PERFLOGNAME = "Perflog"
REPORT = abspath("./somefile.csv")

DATA1 = {
    "verbosity": "info",
    "path": PATH,
    "grid": GRIDFILE,
    "gridprops": [[ZONENAME, ZONEFILE]],
    "wells": WELLFILES,
}


def test_qcdata():
    """Testing getting data with _QCForwardData class"""

    qcdata = QCData()
    qcdata.parse(data=DATA1)

    assert isinstance(qcdata, QCData)
    assert isinstance(qcdata.grid, xtgeo.Grid)
    assert isinstance(qcdata.gridprops, xtgeo.GridProperties)
    assert isinstance(qcdata.wells, xtgeo.Wells)

    assert qcdata._project is None
    assert qcdata.grid.ncol == 40

    zone = qcdata.gridprops.get_prop_by_name(ZONENAME)
    assert isinstance(zone, xtgeo.GridProperty)
    assert zone.name == ZONENAME
    assert zone.values.mean() == pytest.approx(1.92773, abs=0.01)
    assert zone.ncol == 40

    op1 = qcdata.wells.get_well("OP_1")

    assert ZONELOGNAME in op1.dataframe.columns
