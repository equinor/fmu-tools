"""Run tests in RMS.

Creates a tmp RMS project in given version which is used as fixture for all other Roxar
API dependent tests.

This requires a ROXAPI license, and to be ran in a "roxenvbash" environment; hence
the decorator "roxapilicense"

"""
from pathlib import Path
from os.path import isdir
import shutil
import json

import numpy as np
import pytest

import xtgeo

try:
    import roxar
    import roxar.jobs

except ImportError:
    pass

from fmu.tools.rms.upscaling_qc.upscaling_qc import RMSUpscalingQC
from fmu.tools.rms.upscaling_qc._types import UpscalingQCFiles, MetaData

# ======================================================================================
# settings to create RMS project!

TMPD = Path("TMP")
TMPD.mkdir(parents=True, exist_ok=True)

TPATH = Path("../xtgeo-testdata")
PROJNAME = "tmp_project_qcupscaling.rmsxxx"

PRJ = str(TMPD / PROJNAME)

GRIDDATA1 = TPATH / "3dgrids/reek/reek_sim_grid.roff"
PORODATA1 = TPATH / "3dgrids/reek/reek_sim_poro.roff"
ZONEDATA1 = TPATH / "3dgrids/reek/reek_sim_zone.roff"
GRIDNAME1 = "Simgrid"
PORONAME1 = "PORO"
ZONENAME1 = "Zone"

WELLSFOLDER1 = TPATH / "wells/reek/1"
WELLS1 = ["OP_1.w", "OP_2.w", "OP_6.w"]

BW_JOB_SPEC = {
    "BlockedWellsName": "BW",
    "Continuous Blocked Log": [
        {
            "Name": "Poro",
        }
    ],
    "Wells": [["Wells", "OP_1"], ["Wells", "OP_2"], ["Wells", "OP_6"]],
    "Zone Blocked Log": [
        {
            "Name": "Zonelog",
            "ScaleUpType": "SUBGRID_BIAS",
            "ThicknessWeighting": "MD_WEIGHT",
            "ZoneLogArray": [1, 2],
        }
    ],
}


@pytest.mark.skipunlessroxar
@pytest.fixture(name="roxar_project")
def fixture_create_project():
    """Create a tmp RMS project for testing, populate with basic data.

    After the yield command, the teardown phase will remove the tmp RMS project.
    """
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
        wobj = xtgeo.well_from_file(WELLSFOLDER1 / wfile)
        wobj.dataframe["Zonelog"] = 1

        wobj.to_roxar(project, wobj.name, logrun="log", trajectory="Drilled trajectory")

    # populate with grid and props
    grd = xtgeo.grid_from_file(GRIDDATA1)
    grd.to_roxar(project, GRIDNAME1)
    por = xtgeo.gridproperty_from_file(PORODATA1, name=PORONAME1)
    por.to_roxar(project, GRIDNAME1, PORONAME1)
    zon = xtgeo.gridproperty_from_file(ZONEDATA1, name=ZONENAME1)
    zon.values = zon.values.astype(np.uint8)
    zon.values = 1
    zon.to_roxar(project, GRIDNAME1, ZONENAME1)

    # Create blocked wells in grid
    bw_job = roxar.jobs.Job.create(
        owner=["Grid models", "Simgrid", "Grid"], type="Block Wells", name="BW"
    )
    bw_job.set_arguments(BW_JOB_SPEC)
    bw_job.save()

    bw_job.execute(0)

    # save project (both an initla version and a work version) and exit
    project.save_as(prj1)
    project.close()

    yield prj1

    print("\n******* Teardown RMS project!\n")

    if isdir(prj1):
        print("Remove existing project! (1)")
        shutil.rmtree(prj1)


@pytest.mark.skipunlessroxar
def test_upscaling_qc(tmpdir, roxar_project):
    """Test qcreset metod in roxapi."""
    # ==================================================================================

    rox = xtgeo.RoxUtils(roxar_project, readonly=True)
    project = rox.project

    well_data = {
        "selectors": {
            "ZONE": {
                "name": "Zonelog",
            }
        },
        "properties": {"PORO": {"name": "Poro"}},
    }
    bw_data = {
        "selectors": {
            "ZONE": {
                "name": "Zonelog",
            }
        },
        "properties": {"PORO": {"name": "Poro"}},
        "wells": {"grid": "Simgrid", "bwname": "BW"},
    }
    grid_data = {
        "selectors": {"ZONE": {"name": "Zone"}},
        "properties": ["PORO"],
        "grid": "Simgrid",
    }
    ups = RMSUpscalingQC(
        project=project, well_data=well_data, bw_data=bw_data, grid_data=grid_data
    )
    well_df = ups._get_well_data()
    bw_df = ups._get_bw_data()
    grid_df = ups._get_grid_data()
    for data in [well_df, bw_df, grid_df]:
        assert set(data.columns) == set(["ZONE", "PORO"])
    assert well_df["PORO"].mean() == pytest.approx(0.1725, abs=0.0001)
    assert bw_df["PORO"].mean() == pytest.approx(0.1765, abs=0.0001)
    assert grid_df["PORO"].mean() == pytest.approx(0.1677, abs=0.0001)
    ups.to_disk(path=str(tmpdir / "upscalingqc"))
    files = Path(tmpdir / "upscalingqc").glob("**/*")
    assert set([fn.name for fn in files]) == set(
        [item.value for item in UpscalingQCFiles]
    )
    ups.get_statistics()
    with open(Path(tmpdir / "upscalingqc" / UpscalingQCFiles.METADATA), "r") as fp:
        assert MetaData(**json.load(fp)) == ups._metadata
