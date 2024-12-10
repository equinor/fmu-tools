"""Run tests in RMS using rmsapi to new blocked well logs by using
generate_bw_per_facies.

Creates a tmp RMS project in given version.

This requires a ROXAPI license, and to be ran in a "roxenvbash" environment

"""

import contextlib
import filecmp
import shutil
from os.path import isdir
from pathlib import Path
from typing import List

import numpy as np
import pytest
import xtgeo

with contextlib.suppress(ImportError):
    import rmsapi
    import rmsapi.jobs

from fmu.tools.rms.generate_bw_per_facies import create_bw_per_facies

# ======================================================================================
# settings to create RMS project!

REMOVE_RMS_PROJECT_AFTER_TEST = False
DEBUG_PRINT = True
TMPD = Path("TMP")
TMPD.mkdir(parents=True, exist_ok=True)
PROJNAME = "tmp_project_generate_bw_logs.rmsxxx"
PRJ = str(TMPD / PROJNAME)
RESULTDIR = TMPD / "bw"
RESULTDIR.mkdir(parents=True, exist_ok=True)
REFERENCE_DIR = Path("tests/rms/generate_bw_testdata")

GRIDNAME = "TestGrid"
GRID_DIM = (10, 10, 20)
INCREMENT = (250.0, 250.0, 5.0)
TOP_DEPTH = 1000
BASE_DEPTH = TOP_DEPTH + GRID_DIM[2] * INCREMENT[2]
EAST = 0.0
NORTH = 0.0
ORIGIN = (EAST, NORTH, TOP_DEPTH)

NWELLS = 3
WELL_NAME_PREFIX = "Wtest"
NPOINTS = 100
BLOCKED_WELL_SET = "BWtest"
BLOCKED_WELL_JOB = "BW_job"
ORIGINAL_PETRO_LOGS = ["PORO", "PERM"]
FACIES_LOG = "FACIES"
JOB_TYPE = "Block Wells"
FACIES_CODE_NAMES = {
    0: "F1",
    1: "F2",
    2: "F3",
}
ZONE_CODE_NAMES = {
    1: "Zone1",
    2: "Zone2",
    3: "Zone3",
}


def create_grid(project) -> None:
    grid = xtgeo.create_box_grid(GRID_DIM, origin=ORIGIN, increment=INCREMENT)
    grid.to_roxar(project, GRIDNAME)


def create_wells(project) -> List[str]:
    well_list = []
    well_names = []
    for i in range(NWELLS):
        # well head and name
        well_name = f"{WELL_NAME_PREFIX}_{i}"
        well_names.append(well_name)
        if DEBUG_PRINT:
            print(f"Create well:  {well_name}")
        well = project.wells.create(well_name)
        well.rkb = 100
        east = EAST + INCREMENT[0] + 750 * i
        north = NORTH + INCREMENT[1] + 750 * i
        topdepth = TOP_DEPTH
        basedepth = BASE_DEPTH
        npoints = NPOINTS
        loginc = (basedepth - topdepth) / npoints
        well.well_head = (east, north)

        # trajectory
        trajectories = well.wellbore.trajectories
        drilled_trajectory = trajectories.create("Drilled trajectory")
        surveypoints = drilled_trajectory.survey_point_series
        array_with_points = surveypoints.generate_survey_points(npoints)
        array_with_points[:, 0] = np.arange(topdepth, basedepth, loginc)
        array_with_points[:, 3].fill(east)
        array_with_points[:, 4].fill(north)
        array_with_points[:, 5] = np.arange(topdepth, basedepth, loginc)  # TVD
        surveypoints.set_survey_points(array_with_points)

        # log curves
        log_run = drilled_trajectory.log_runs.create("Log run 1")
        measured_depths = np.arange(
            topdepth, basedepth, loginc
        )  # MD points for log values
        log_run.set_measured_depths(measured_depths)
        nval = len(measured_depths)

        poro_log_curve = log_run.log_curves.create("PORO")
        values = np.zeros(nval, dtype=np.float32)
        for i in range(nval):
            angle = i * 10 * np.pi / nval
            values[i] = 0.05 * np.sin(angle) + 0.15
        poro_log_curve.set_values(values)

        perm_log_curve = log_run.log_curves.create("PERM")
        for i in range(nval):
            angle = i * 10 * np.pi / nval
            values[i] = 99 * np.sin(angle) + 100
        perm_log_curve.set_values(values)

        facies_log_curve = log_run.log_curves.create_discrete("FACIES")
        values = np.zeros(nval, dtype=np.int32)
        # facies_log_curve.generate_values()
        for i in range(nval):
            values[i] = (
                i % 3
            )  # (values 0,1 or 2, must be consistent with facies code names)
        facies_log_curve.set_values(values)
        code_names = FACIES_CODE_NAMES
        facies_log_curve.set_code_names(code_names)

        zone_log_curve = log_run.log_curves.create_discrete("ZONELOG")
        values = zone_log_curve.generate_values()
        for i in range(nval):
            if i < (nval / 3):
                values[i] = 1
            elif i < (2 * nval / 3):
                values[i] = 2
            else:
                values[i] = 3
        zone_log_curve.set_values(values)
        code_names = ZONE_CODE_NAMES
        zone_log_curve.set_code_names(code_names)

    well_list.append(well)

    return well_names


def create_bw_job(
    owner_strings: List[str],
    job_type: str,
    job_name: str,
    well_names: List[str],
    debug_print: bool = False,
):
    bw_job = rmsapi.jobs.Job.create(owner=owner_strings, type=job_type, name=job_name)

    params = {
        "BlockedWellsName": BLOCKED_WELL_SET,
        "Continuous Blocked Log": [
            {
                "Name": "PORO",
                "Interpolate": True,
                "CellLayerAveraging": True,
            },
            {
                "Name": "PERM",
                "Interpolate": True,
                "CellLayerAveraging": True,
            },
        ],
        "Discrete Blocked Log": [
            {
                "Name": "FACIES",
                "CellLayerAveraging": True,
            },
        ],
        "Wells": [["Wells", well_name] for well_name in well_names],
        "Zone Blocked Log": [
            {
                "Name": "ZONELOG",
                "CellLayerAveraging": True,
                "ZoneLogArray": [1, 2, 3, 4],
            }
        ],
    }
    check, err_list, warn_list = bw_job.check(params)
    if not check:
        print("Error when creating blocked well job:")
        for i in range(len(err_list)):
            print(f"  {err_list[i]}")
        print("Warnings when creating blocked well job:")
        for i in range(len(warn_list)):
            print(f"  {warn_list[i]}")

    if debug_print:
        print(
            f"Create block well job:  {job_name} to make blocked well set: "
            f"{BLOCKED_WELL_SET}"
        )
        print(f"Use the wells: {well_names}")

    bw_job.set_arguments(params)
    bw_job.save()

    return bw_job


def create_project():
    """Create a tmp RMS project for testing, populate with basic data."""

    prj1 = str(PRJ)

    print("\n******** Setup RMS project!\n")
    if isdir(prj1):
        print("Remove existing project! (1)")
        shutil.rmtree(prj1)

    project = rmsapi.Project.create()

    rox = xtgeo.RoxUtils(project)
    print("rmsapi version is", rox.roxversion)
    print("RMS version is", rox.rmsversion(rox.roxversion))
    assert "1." in rox.roxversion

    create_grid(project)

    well_names = create_wells(project)
    owner_strings = ["Grid models", GRIDNAME, "Grid"]
    bw_job = create_bw_job(owner_strings, "Block Wells", BLOCKED_WELL_JOB, well_names)
    bw_job.execute()
    project.save_as(prj1)
    return project


@pytest.mark.skipunlessroxar
def test_generate_bw() -> None:
    """Test generate_new blocked well logs"""

    project = create_project()
    create_bw_per_facies(
        project,
        GRIDNAME,
        BLOCKED_WELL_SET,
        ORIGINAL_PETRO_LOGS,
        FACIES_LOG,
        FACIES_CODE_NAMES,
        debug_print=DEBUG_PRINT,
    )
    wellnames = write_bw_to_files(project)

    # Compare text files with blocked well data with reference data
    for wellname in wellnames:
        filename = wellname + ".txt"
        check = filecmp.cmp(TMPD / Path(filename), REFERENCE_DIR / Path(filename))
        if check:
            print(f"Check OK for blocked well: {wellname}")
        assert check

    if REMOVE_RMS_PROJECT_AFTER_TEST:
        print("\n******* Teardown RMS project!\n")
        if isdir(PRJ):
            print("Remove existing project!")
            shutil.rmtree(PRJ)
        if isdir(RESULTDIR):
            print("Remove temporary files")
            shutil.rmtree(RESULTDIR)


def write_bw_to_files(project) -> List[str]:
    xtgeo_bw = xtgeo.blockedwells_from_roxar(
        project, GRIDNAME, BLOCKED_WELL_SET, lognames="all"
    )
    wells = xtgeo_bw.wells
    wellnames = []
    for well in wells:
        well_file_name = TMPD / Path(well.name + ".txt")
        wellnames.append(well.name)
        if DEBUG_PRINT:
            print(f"Write file:  {well_file_name}")
            print(f"Well logs:  {well.lognames}")
        well.to_file(well_file_name, fformat="rmswell")
    return wellnames
