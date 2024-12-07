"""Run tests in RMS using rmsapi to new blocked well logs by using
generate_bw_per_facies.

Creates a tmp RMS project in given version.

This requires a ROXAPI license, and to be ran in a "roxenvbash" environment

"""

import contextlib
import shutil
from os.path import isdir
from pathlib import Path

import numpy as np
import pytest
import xtgeo

import roxarimport roxar.jobs

with contextlib.suppress(ImportError):
    import roxar

from fmu.tools.rms.generate_bw_per_facies import create_bw_per_facies

# ======================================================================================
# settings to create RMS project!

REMOVE_RMS_PROJECT_AFTER_TEST = True
DEBUG_PRINT = True
TMPD = Path("TMP")
TMPD.mkdir(parents=True, exist_ok=True)
PROJNAME = "tmp_project_generate_bw_logs.rmsxxx"
PRJ = str(TMPD / PROJNAME)
RESULTDIR = TMPD / "bw"
RESULTDIR.mkdir(parents=True, exist_ok=True)
REFERENCE_DIR = Path("tests/rms/generate_bw_testdata")
REFERENCE_FILE = REFERENCE_DIR / "BW.txt"

GRIDDATA = REFERENCE_DIR / "grid.roff"
GRIDNAME = "GridModel"
NWELLS = 3
BLOCKED_WELL_SET = "BW"
BLOCKED_WELL_JOB = "BW_job"
ORIGINAL_PETRO_LOGS = ["PORO", "PERM"]
FACIES_LOG = "FACIES"
FACIES_CODE_NAMES = {
    0: "F1",
    1: "F2",
    2: "F3",
}

def create_wells(project, nwells):
    well_list = []
    well_names = []
    for i in range(nwells):
        # well head and name
        well_name = f"W{i}"
        well_names.append(well_name)
        well = project.wells.create(well_name)
        well.rkb = 100
        east = 1000 + 200*i
        north = 2000 + 100*i
        well.well_head = (east, north)

        # trajectory
        trajectories = well.wellbore.trajectories
        drilled_trajectory = trajectories.create("Drilled trajectory")
        surveypoints = drilled_trajectory.survey_point_series
        array_with_points = surveypoints.generate_survey_points(15)
        array_with_points[:,0] = np.arange(1000, 1200, 10)  #From MD depth 1000 to MD depth 1200
        array_with_points[:,3].fill(east)   # vertical well (constant x,y position for all points)
        array_with_points[:,4].fill(north)  
        array_with_points[:,5] = np.arange(1500, 1700, 10)  #TVD
        surveypoints.set_survey_points(array_with_points)

        # log curves
        log_run = drilled_trajectory.log_runs.create("Log run 1")
        measured_depths = np.arange(1499.0,1701,1.0) # MD points for log values
        log_run.set_measured_depths(measured_depths)
        nval = len(measured_depths)

        poro_log_curve = log_run.log_curves.create("PORO")
        values = np.zeros(nval, dtype=np.float32)
        for i in range(nval):
            angle = i*10*np.pi/nval
            values[i] = 0.05 * np.sin(angle) + 0.15
        poro_log_curve.set_values(values)

        perm_log_curve = log_run.log_curves.create("PERM")
        for i in range(nval):
            angle = i*10*np.pi/nval
            values[i] = 99 * np.sin(angle) + 100
        perm_log_curve.set_values(values)

        facies_log_curve = log_run.log_curves.create_discrete("FACIES")
        values = facies_log_curve.generate_values()
        for i in range(nval):
            angle = i*10*np.pi/nval
            values[i] = i % 3  # (values 0,1 or 2, must be consistent with facies code names)
        facies_log_curve.set_values(values)
        code_names = FACIES_CODE_NAMES
        facies_log_curve.set_code_names(code_names)
        well_list.append(well)
    
    return well_names

def create_bw_job(owner_strings,job_type, job_name, well_names):
    bw_job = roxar.jobs.Job.create(owner=owner_strings, type=job_type, name=job_name)

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
        "Wells": [["Wells", well.name] for well in well_names],
        "Zone Blocked Log": [
            {
                "Name": "ZONELOG",
                "CellLayerAveraging": True,
                "ZoneLogArray": [1],
            }
        ],
    }
    check, err_list, warn_list = bw_job.check(params)
    if not check:
        print(f"Error when creating blocked well job:")
        for i in range(len(err_list)):
            print(f"  {err_list[i]}")
        print(f"Warnings when creating blocked well job:")
        for i in range(len(warn_list)):
            print(f"  {warn_list[i]}")

    bw_job.set_arguments(params)
    bw_job.save()

    return bw_job


def create_project():
    """Create a tmp RMS project for testing, populate with basic data.

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


    # populate with grid and props
    grd = xtgeo.grid_from_file(GRIDDATA, fformat="roff")
    grd.to_roxar(project, GRIDNAME)

    well_names = create_wells(project, NWELLS)
    owner_strings = ["Grid Models", GRIDNAME, "Grid"]
    bw_job = create_bw_job(owner_strings,"Block Wells", BLOCKED_WELL_JOB, well_names)
    bw_job.execute()
    project.save_as(prj1)
    return project




@pytest.mark.skipunlessroxar
def test_generate_bw():
    """Test generate_new blocked well logs"""

    project = create_project()
    create_bw_per_facies(
        PRJ,
        GRIDNAME,
        BLOCKED_WELL_SET,
        ORIGINAL_PETRO_LOGS,
        FACIES_LOG,
        FACIES_CODE_NAMES,
        debug_print=DEBUG_PRINT,

    # Export bw set før og etter og sammenlign med referanse

