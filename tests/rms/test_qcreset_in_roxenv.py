"""Run tests in RMS.

Creates a tmp RMS project in given version which is used as fixture for all other Roxar
API dependent tests.

This requires a ROXAPI license, and to be ran in a "roxenvbash" environment; hence
the decorator "roxapilicense"

"""

import contextlib
import shutil
from os.path import isdir
from pathlib import Path

import numpy as np
import pytest
import xtgeo

with contextlib.suppress(ImportError):
    import roxar


# ======================================================================================
# settings to create RMS project!

TMPD = Path("TMP")
TMPD.mkdir(parents=True, exist_ok=True)

PROJNAME = "tmp_project_qcreset.rmsxxx"
PRJ = str(TMPD / PROJNAME)

CUBENAME1 = "synth1"
SURFCAT1 = "DS_whatever"
SURFNAMES1 = ["TopReek", "MidReek", "BaseReek"]
GRIDNAME1 = "Simgrid"
PORONAME1 = "PORO"
ZONENAME1 = "Zone"

WELLS1 = ["OP1_perf.w", "OP_2.w", "OP_6.w", "XP_with_repeat.w"]


@pytest.mark.skipunlessroxar
@pytest.fixture(name="create_project", scope="module", autouse=True)
def fixture_create_project(testdata_path):
    """Create a tmp RMS project for testing, populate with basic data.

    After the yield command, the teardown phase will remove the tmp RMS project.
    """

    cubedata1 = testdata_path / "cubes/reek/syntseis_20000101_seismic_depth_stack.segy"

    surftops1 = [
        testdata_path / "surfaces/reek/1/topreek_rota.gri",
        testdata_path / "surfaces/reek/1/midreek_rota.gri",
        testdata_path / "surfaces/reek/1/lowreek_rota.gri",
    ]

    griddata1 = testdata_path / "3dgrids/reek/reek_sim_grid.roff"
    porodata1 = testdata_path / "3dgrids/reek/reek_sim_poro.roff"
    zonedata1 = testdata_path / "3dgrids/reek/reek_sim_zone.roff"

    wellsfolder1 = testdata_path / "wells/reek/1"

    prj1 = str(PRJ)

    print("\n******** Setup RMS project!\n")
    if isdir(prj1):
        print("Remove existing project! (1)")
        shutil.rmtree(prj1)

    project = roxar.Project.create()

    rox = xtgeo.RoxUtils(project)
    print("Roxar version is", rox.roxversion)
    print("RMS version is", rox.rmsversion(rox.roxversion))
    assert "1." in rox.roxversion

    for wfile in WELLS1:
        wobj = xtgeo.well_from_file(wellsfolder1 / wfile)
        if "XP_with" in wfile:
            wobj.name = "OP2_w_repeat"

        wobj.to_roxar(project, wobj.name, logrun="log", trajectory="My trajectory")

    # populate with cube data
    cube = xtgeo.cube_from_file(cubedata1)
    cube.to_roxar(project, CUBENAME1, domain="depth")

    # populate with surface data
    rox.create_horizons_category(SURFCAT1)
    for num, name in enumerate(SURFNAMES1):
        srf = xtgeo.surface_from_file(surftops1[num])
        project.horizons.create(name, roxar.HorizonType.interpreted)
        srf.to_roxar(project, name, SURFCAT1)

    # populate with grid and props
    grd = xtgeo.grid_from_file(griddata1)
    grd.to_roxar(project, GRIDNAME1)
    por = xtgeo.gridproperty_from_file(porodata1, name=PORONAME1)
    por.to_roxar(project, GRIDNAME1, PORONAME1)
    zon = xtgeo.gridproperty_from_file(zonedata1, name=ZONENAME1)
    zon.values = zon.values.astype(np.uint8)
    zon.to_roxar(project, GRIDNAME1, ZONENAME1)

    # save project (both an initla version and a work version) and exit
    project.save_as(prj1)
    project.close()

    yield project

    print("\n******* Teardown RMS project!\n")

    if isdir(prj1):
        print("Remove existing project! (1)")
        shutil.rmtree(prj1)


@pytest.mark.skipunlessroxar
def test_qcreset():
    """Test qcreset metod in roxapi."""
    # ==================================================================================
    # pylint: disable=invalid-name
    from fmu.tools.rms import qcreset  # noqa

    rox = xtgeo.RoxUtils(project=PRJ)

    SETUP1 = {
        "project": rox.project,
        "horizons": {
            "DS_whatever": ["TopReek", "MidReek"],
        },
        "grid_models": {
            "Simgrid": ["PORO"],
        },
        "value": 0.088,
    }

    SETUP2 = {
        "project": rox.project,
        "horizons": {
            "DS_whatever": ["TopReek", "MidReek"],
        },
        "grid_models": {
            "Simgrid": ["PORO"],
        },
    }

    qcreset.set_data_constant(SETUP1)

    topr = xtgeo.surface_from_roxar(rox.project, "TopReek", "DS_whatever")
    assert topr.values.mean() == pytest.approx(0.088)

    poro = xtgeo.gridproperty_from_roxar(rox.project, "Simgrid", "PORO")
    assert poro.values.mean() == pytest.approx(0.088)

    qcreset.set_data_empty(SETUP2)

    top = rox.project.horizons["TopReek"]["DS_whatever"]

    assert top.is_empty() is True
