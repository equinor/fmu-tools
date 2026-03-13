import contextlib
import filecmp
import shutil
from os.path import isdir
from pathlib import Path
from typing import Any

import pytest

with contextlib.suppress(ImportError):
    import rmsapi

import xtgeo

from fmu.tools.rms.get_rms_simbox_params import get_simbox_param, write_simbox

# ======================================================================================
# settings to create RMS project!

REMOVE_RMS_PROJECT_AFTER_TEST = False

TMPD = Path("TMP")
TMPD.mkdir(parents=True, exist_ok=True)


PROJNAME = "tmp_project_get_rms_simbox_params.rmsxxx"
PRJ = str(TMPD / PROJNAME)
RESULTDIR = TMPD / "rms_simbox"
RESULTDIR.mkdir(parents=True, exist_ok=True)
REFERENCE_DIR = Path("tests/rms/rms_simbox")

NX = 50
NY = 70
NZ_ZONEA = 10
NZ_ZONEB = 35
XINC = 50.0
YINC = 50.0
ZINC = 5.0
ORIGIN = (10000.0, 20000.0, 2000.0)
ROTATION = 50.0
ZONEA = "ZoneA"
ZONEB = "ZoneB"


ZONEA_NUMBER = 1
ZONEB_NUMBER = 2


GRID_MODEL_NAME = "Geogrid"
OUTPUT_FILE_PREFIX = "simbox"
OUTPUT_REF_FILE_PREFIX = "ref_simbox"


@pytest.mark.skipunlessroxar
@pytest.mark.parametrize(
    "rotation, flip, zone_index_list",
    [
        (
            0.0,
            1,
            [0, 1],
        ),
    ],
)
def test_get_rms_simbox_params(
    rotation: float, flip: int, zone_index_list: list[int]
) -> None:
    """Create a tmp RMS project for testing, populate with basic data."""
    project = create_project()

    create_grids(project, rotation, flip)
    for zone_index in zone_index_list:
        simbox_output_file_name = Path(RESULTDIR) / Path(
            OUTPUT_FILE_PREFIX
            + "_angle"
            + str(int(rotation))
            + "_zone"
            + str(zone_index)
            + ".txt"
        )
        simbox_dict = get_simbox_param(project, GRID_MODEL_NAME, zone_index)
        write_simbox(simbox_output_file_name, simbox_dict)

        # Verify that original is equal to the new params
        reference_filename = Path(REFERENCE_DIR) / Path(
            OUTPUT_REF_FILE_PREFIX
            + "_angle"
            + str(int(rotation))
            + "_zone"
            + str(zone_index)
            + ".txt"
        )
        compare_results_with_reference(simbox_output_file_name, reference_filename)

    project.close()

    if REMOVE_RMS_PROJECT_AFTER_TEST:
        print("\n******* Teardown RMS project!\n")
        if isdir(PRJ):
            print("Remove existing project!")
            shutil.rmtree(PRJ)
        if isdir(RESULTDIR):
            print("Remove temporary files")
            shutil.rmtree(RESULTDIR)


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

    project.save_as(prj1)
    return project


def create_grids(project: Any, rotation: float, flip: int = 1):
    nx = NX
    ny = NY
    nz_zoneA = NZ_ZONEA
    nz_zoneB = NZ_ZONEB
    nz = nz_zoneA + nz_zoneB
    dimension = (nx, ny, nz)
    increment = (XINC, YINC, ZINC)
    origin = ORIGIN

    subgrid_dict = {
        ZONEA: nz_zoneA,
        ZONEB: nz_zoneB,
    }
    geogrid = xtgeo.create_box_grid(
        dimension,
        origin=origin,
        increment=increment,
        rotation=rotation,
        flip=flip,
    )
    geogrid.set_subgrids(subgrid_dict)
    geogrid.to_roxar(project, GRID_MODEL_NAME)


def compare_results_with_reference(filename, reference_filename):
    # Compare with reference
    check = filecmp.cmp(filename, reference_filename)
    if check:
        print("Check OK for multi zone grid")
    assert check
