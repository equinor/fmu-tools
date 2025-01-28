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
import pandas as pd
import pytest
import xtgeo

with contextlib.suppress(ImportError):
    import roxar


# ======================================================================================
# settings to create RMS project!

TMPD = Path("TMP")
TMPD.mkdir(parents=True, exist_ok=True)

PROJNAME = "tmp_project.rmsxxx"
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

    cubedata = testdata_path / "cubes/reek/syntseis_20000101_seismic_depth_stack.segy"
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
    cube = xtgeo.cube_from_file(cubedata)
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
def test_qcforward_wzonation_vs_grid_stops(tmp_path):
    """Test wzonation vs grid inside RMS, and here it will STOP."""
    # ==================================================================================
    # qcforward well vs grid (mimic python inside RMS input!)
    # pylint: disable=invalid-name
    from fmu.tools import qcforward

    PRJ1 = PRJ
    WELLS = ["OP.*"]

    ZONELOGNAME = "Zonelog"
    TRAJ = "My trajectory"
    LOGRUN = "log"
    GRIDNAME = "Simgrid"
    ZONEGRIDNAME = "Zone"
    DRANGE = [1300, 3200]
    ZLOGRANGE = [1, 3]
    ZLOGSHIFT = 0
    REPORTPATH = tmp_path / "well_vs_grid.csv"

    ACT = [
        {"warn": "any < 90", "stop": "any < 70"},
        {"warn": "all < 95", "stop": "all < 80"},
    ]

    qcjob = qcforward.WellZonationVsGrid()

    def check():
        usedata = {
            "wells": {"names": WELLS, "logrun": LOGRUN, "trajectory": TRAJ},
            "zonelog": {"name": ZONELOGNAME, "range": ZLOGRANGE, "shift": ZLOGSHIFT},
            "grid": GRIDNAME,
            "depthrange": DRANGE,
            "gridprops": [ZONEGRIDNAME],
            "actions": ACT,
            "report": REPORTPATH,
            "nametag": "ZONELOG",
        }

        qcjob.run(usedata, project=PRJ1)

    with pytest.raises(SystemExit):
        check()


@pytest.mark.skipunlessroxar
def test_qcforward_wzonation_vs_grid_runs_ok(tmp_path):
    """Test wzonation vs grid inside RMS, and here it will run OK."""
    # ==================================================================================
    # qcforward well vs grid (mimic python inside RMS input!)
    # pylint: disable=invalid-name
    from fmu.tools import qcforward

    PRJ1 = PRJ
    WELLS = ["OP.*"]

    ZONELOGNAME = "Zonelog"
    TRAJ = "My trajectory"
    LOGRUN = "log"
    GRIDNAME = "Simgrid"
    ZONEGRIDNAME = "Zone"
    DRANGE = [1300, 3200]
    ZLOGRANGE = [1, 3]
    ZLOGSHIFT = 0
    REPORTPATH = tmp_path / "well_vs_grid.csv"

    ACT = [
        {"warn": "any < 80", "stop": "any < 50"},
        {"warn": "all < 85", "stop": "all < 40"},
    ]

    qcjob = qcforward.WellZonationVsGrid()

    def check():
        usedata = {
            "wells": {"names": WELLS, "logrun": LOGRUN, "trajectory": TRAJ},
            "zonelog": {"name": ZONELOGNAME, "range": ZLOGRANGE, "shift": ZLOGSHIFT},
            "grid": GRIDNAME,
            "depthrange": DRANGE,
            "gridprops": [ZONEGRIDNAME],
            "actions": ACT,
            "report": REPORTPATH,
            "nametag": "ZONELOG",
        }

        qcjob.run(usedata, project=PRJ1)

    check()

    result = pd.read_csv(REPORTPATH).set_index("WELL")
    assert result.loc["OP_1_PERF", "MATCH%"] == pytest.approx(70.588235)
    assert result.loc["all", "MATCH%"] == pytest.approx(67.207573)


@pytest.mark.skipunlessroxar
def test_qcforward_gridquality_ok(tmp_path):
    """Test qcforward gridquality parameters that runs ok."""
    # ==================================================================================
    # qcforward grid quality (mimic python inside RMS input!)
    # pylint: disable=invalid-name
    from fmu.tools import qcforward

    PRJ1 = PRJ
    GRIDNAME = "Simgrid"
    REPORT = tmp_path / "gridquality.csv"

    ACT = {
        "minangle_topbase": [
            {"warn": "allcells > 1% when < 80", "stop": "allcells > 1% when < 50"},
            {"warn": "allcells > 50% when < 85", "stop": "all > 10% when < 50"},
            {"warn": "allcells > 50% when < 85"},
        ],
        "collapsed": [{"warn": "all > 20%", "stop": "all > 50%"}],
        "faulted": [{"warn": "all > 20%", "stop": "all > 50%"}],
    }

    qcjob = qcforward.GridQuality()

    def check():
        usedata = {
            "grid": GRIDNAME,
            "actions": ACT,
            "report": {"file": REPORT, "mode": "write"},
            "nametag": "ZONELOG",
        }

        qcjob.run(usedata, project=PRJ1)

    check()

    result = pd.read_csv(REPORT).set_index("GRIDQUALITY")
    assert result.loc["minangle_topbase[1]", "WARN%"] == pytest.approx(10.447, abs=0.01)
    assert result.loc["minangle_topbase[0]", "WARN%"] == pytest.approx(2.715, abs=0.01)


@pytest.mark.skipunlessroxar
def test_qcforward_gridquality_fail(tmp_path):
    """Test qcforward gridquality parameters that shall fail on faulted."""
    # ==================================================================================
    # qcforward grid quality (mimic python inside RMS input!)
    # pylint: disable=invalid-name
    from fmu.tools import qcforward

    PRJ1 = PRJ
    GRIDNAME = "Simgrid"
    REPORT = tmp_path / "gridquality.csv"

    ACT = {
        "minangle_topbase": [
            {"warn": "allcells > 1% when < 80", "stop": "allcells > 1% when < 50"},
            {"warn": "allcells > 50% when < 85", "stop": "all > 10% when < 50"},
            {"warn": "allcells > 50% when < 85"},
        ],
        "collapsed": [{"warn": "all > 20%", "stop": "all > 50%"}],
        "faulted": [{"warn": "all > 20%", "stop": "all > 10%"}],
    }

    qcjob = qcforward.GridQuality()

    def check():
        usedata = {
            "grid": GRIDNAME,
            "actions": ACT,
            "report": {"file": REPORT, "mode": "write"},
            "nametag": "ZONELOG",
        }

        qcjob.run(usedata, project=PRJ1)

    with pytest.raises(SystemExit):
        check()

    result = pd.read_csv(REPORT).set_index("GRIDQUALITY")
    assert result.loc["faulted[0]", "WARN%"] == pytest.approx(16.368, abs=0.01)
