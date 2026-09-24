"""RMS integration tests for swmodel."""

from __future__ import annotations

import shutil
from os.path import isdir
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np
import pytest
import xtgeo

from fmu.tools.swmodel import run_swmodel

if TYPE_CHECKING:
    from collections.abc import Generator

try:
    import rmsapi
except ImportError:
    rmsapi = pytest.importorskip("roxar")

TMPD = Path("TMP")
TMPD.mkdir(parents=True, exist_ok=True)

PROJNAME = "tmp_project_swmodel.rmsxxx"
PRJ = str(TMPD / PROJNAME)
GRIDNAME = "Simgrid"
PORONAME = "PORO"
PERMNAME = "PERM"
REGIONNAME = "SWFUNC_REGION"
FWLNAME = "FWL"
GOCNAME = "GOC"
FWLWGNAME = "FWLWG"


def _filled_like(
    prop: xtgeo.GridProperty, value: float, name: str
) -> xtgeo.GridProperty:
    clone = prop.copy()
    clone.name = name
    clone.values = np.ma.array(
        np.full(prop.values.shape, value),
        mask=np.ma.getmaskarray(prop.values),
    )
    return clone


@pytest.fixture(name="create_project", scope="module", autouse=True)
def fixture_create_project() -> Generator[Any, None, None]:
    testdata = (
        Path(__file__).resolve().parents[1]
        / "data"
        / "ensembles"
        / "01_drogon_ahm"
        / "realization-0"
        / "iter-3"
        / "share"
        / "results"
        / "grids"
    )
    griddata = testdata / "geogrid.roff"
    porodata = testdata / "geogrid--phit.roff"
    faciesdata = testdata / "geogrid--facies.roff"

    if isdir(PRJ):
        shutil.rmtree(PRJ)

    project = rmsapi.Project.create()
    grid = xtgeo.grid_from_file(griddata)
    grid.to_roxar(project, GRIDNAME)

    poro = xtgeo.gridproperty_from_file(porodata)
    poro.to_roxar(project, GRIDNAME, PORONAME)

    facies = xtgeo.gridproperty_from_file(faciesdata)
    region_prop = xtgeo.GridProperty(
        grid,
        name=REGIONNAME,
        discrete=True,
        values=np.ma.array(
            np.ones(facies.values.shape, dtype=np.uint8),
            mask=np.ma.getmaskarray(facies.values),
        ),
        codes={1: "Channel"},
        roxar_dtype=np.uint8,
    )
    region_prop.to_roxar(project, GRIDNAME, REGIONNAME)

    _, _, zc = grid.get_xyz(asmasked=True)
    zvals = np.ma.asarray(zc.values).compressed()
    goc_value = float(np.median(zvals))
    fwl_value = float(zvals.max() + 50.0)
    fwlwg_value = float(zvals.min() - 50.0)

    perm = _filled_like(poro, 100.0, PERMNAME)
    perm.to_roxar(project, GRIDNAME, PERMNAME)
    fwl = _filled_like(poro, fwl_value, FWLNAME)
    fwl.to_roxar(project, GRIDNAME, FWLNAME)
    goc = _filled_like(poro, goc_value, GOCNAME)
    goc.to_roxar(project, GRIDNAME, GOCNAME)
    fwlwg = _filled_like(poro, fwlwg_value, FWLWGNAME)
    fwlwg.to_roxar(project, GRIDNAME, FWLWGNAME)

    project.save_as(PRJ)
    project.close()

    yield project

    if isdir(PRJ):
        shutil.rmtree(PRJ)


@pytest.mark.skipunlessroxar
def test_run_swmodel_in_roxenv() -> None:
    rox = xtgeo.RoxUtils(project=PRJ)
    config = {
        "grid": GRIDNAME,
        "gridparameter": {
            "swfunction_region": REGIONNAME,
            "poro": PORONAME,
            "perm": PERMNAME,
            "fwl": FWLNAME,
            "goc": GOCNAME,
            "fwlwg": FWLWGNAME,
        },
        "sw_functions": {
            "Channel": {
                "oil": {"a": 4.5, "b": -2.2, "swirr": 0.0},
                "gas": {"a": 3.8, "b": -1.9, "swirr": 0.0},
            }
        },
    }

    props = run_swmodel(rox.project, config, output_all=True)

    assert {"sw", "sw_h", "so", "sg"} <= set(props)

    swfunction_region = xtgeo.gridproperty_from_roxar(rox.project, GRIDNAME, REGIONNAME)
    sw = xtgeo.gridproperty_from_roxar(rox.project, GRIDNAME, "sw")
    sw_h = xtgeo.gridproperty_from_roxar(rox.project, GRIDNAME, "sw_hcenter")
    so = xtgeo.gridproperty_from_roxar(rox.project, GRIDNAME, "so")
    sg = xtgeo.gridproperty_from_roxar(rox.project, GRIDNAME, "sg")

    assert swfunction_region.codes == {1: "Channel"}
    sw_vals = np.ma.asarray(sw.values).compressed()
    so_vals = np.ma.asarray(so.values).compressed()
    sg_vals = np.ma.asarray(sg.values).compressed()

    assert sw_h is not None
    assert sw_vals.size > 0
    assert np.all(sw_vals >= 0.0)
    assert np.all(sw_vals <= 1.0)
    assert np.all(so_vals >= 0.0)
    assert np.all(so_vals <= 1.0)
    assert np.all(sg_vals >= 0.0)
    assert np.all(sg_vals <= 1.0)
    assert np.allclose(sw_vals + so_vals + sg_vals, 1.0)

    rox.project.save()
    rox.project.close()
