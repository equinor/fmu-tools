"""Testing top layer qcforward and qcforwarddata methods"""

from __future__ import absolute_import, division, print_function  # PY2

from os.path import abspath
import pytest

from fmu.tools.qcforward._qcforward import QCForward
from fmu.tools.qcforward._qcforward_data import _QCForwardData

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
PERFLOGNAME = "Perflog"
REPORT = abspath("./somefile.csv")

DATA1 = {
    "verbosity": "info",
    "path": PATH,
    "grid": GRIDFILE,
    "gridprops": [(ZONENAME, ZONEFILE)],
    "wells": WELLFILES,
    "zonelog": {"name": ZONELOGNAME, "range": [1, 3]},
    "depthrange": [1580, 9999],
    "actions_each": {"warnthreshold": 50, "stopthreshold": 20},
    "actions_all": {"warnthreshold": 80, "stopthreshold": 20},
    "report": {"file": REPORT, "mode": "write"},
    "dump_yaml": "somefile.yml",
}


def test_qcforward():
    """Testing super class QCForward"""
    qcstuff = QCForward()

    assert isinstance(qcstuff, QCForward)


def test_qcforwarddata():
    """Testing getting data with _QCForwardData class"""

    qcdata = _QCForwardData()
    qcdata.parse(DATA1)

    assert isinstance(qcdata, _QCForwardData)
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
