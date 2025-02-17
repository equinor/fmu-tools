"""Run tests in RMS using rmsapi to test geogrid_to_ertbox_field_params.py

Creates a tmp RMS project in given version.


This requires a RMSAPI license, and to be ran in a "roxenvbash" environment

"""

import contextlib
import shutil
from os.path import isdir
from pathlib import Path

import numpy as np
import pytest
import xtgeo

with contextlib.suppress(ImportError):
    import rmsapi
    from rmsapi.jobs import Job

from fmu.tools.rms import copy_rms_param
from fmu.tools.rms.copy_rms_param_to_ertbox_grid import (
    get_grid_conformity,
)

# ======================================================================================
# settings to create RMS project!


DEBUG_OFF = 0
DEBUG_ON = 1
DEBUG_VERBOSE = 2
DEBUG_VERY_VERBOSE = 3

DEBUG_LEVEL = DEBUG_ON

REMOVE_RMS_PROJECT_AFTER_TEST = True

TMPD = Path("TMP")
TMPD.mkdir(parents=True, exist_ok=True)


PROJNAME = "tmp_project_from_geo_to_ertbox.rmsxxx"
PRJ = str(TMPD / PROJNAME)
RESULTDIR = TMPD / "geo_to_ertbox"
RESULTDIR.mkdir(parents=True, exist_ok=True)
REFERENCE_DIR = Path("tests/rms/geo_to_ertbox")
GRID_MODEL_ERTBOX = "ERTBOX"
GRID_MODEL = "Geogrid"
PETROPARAMS_REFERENCE = ["P1", "P2"]
PETROPARAMS = ["P1_new", "P2_new"]
ERTBOX_PETRO_PARAMS_A = ["ZoneA_P1", "ZoneA_P2"]
ERTBOX_PETRO_PARAMS_B = ["ZoneB_P1", "ZoneB_P2"]
ZONE_PARAM_NAME = "Zone"
NX = 50
NY = 70
NZ_ZONEA = 10
NZ_ZONEB = 15
XINC = 50.0
YINC = 50.0
ZINC = 5.0
ORIGIN = (0.0, 0.0, 0.0)
ROTATION = 50.0
ZONEA = "ZoneA"
ZONEB = "ZoneB"
PROPORTIONAL_CODE = 0
TOPCONFORM_CODE = 1
BASECONFORM_CODE = 2
PROPORTIONAL = "Proportional"
TOPCONFORM = "TopConform"
BASECONFORM = "BaseConform"

ZONEA = "ZoneA"
ZONEB = "ZoneB"
ZONEC = "ZoneC"
ZONEA_NUMBER = 1
ZONEB_NUMBER = 2
ZONEC_NUMBER = 3

GRID_MODEL_NAME = "Geogrid"
GRID_BUILDING_JOB_NAME = "Grid_building_job_name"
GEO_TO_ERTBOX_DICT = {
    "project": None,
    "debug_level": DEBUG_LEVEL,
    "Mode": "from_geo_to_ertbox",
    "GeoGridParameters": {
        1: PETROPARAMS_REFERENCE,
        2: PETROPARAMS_REFERENCE,
    },
    "ErtboxParameters": {
        1: ERTBOX_PETRO_PARAMS_A,
        2: ERTBOX_PETRO_PARAMS_B,
    },
    "Conformity": {
        1: BASECONFORM,
        2: TOPCONFORM,
    },
    "GridModelName": GRID_MODEL,
    "ZoneParam": ZONE_PARAM_NAME,
    "ERTBoxGridName": GRID_MODEL_ERTBOX,
    "ExtrapolationMethod": "repeat",
    "SaveActiveParam": True,
    "AddNoiseToInactive": True,
}

ERTBOX_TO_GEO_DICT = {
    "project": None,
    "debug_level": DEBUG_LEVEL,
    "Mode": "from_ertbox_to_geo",
    "GeoGridParameters": {
        1: PETROPARAMS,
        2: PETROPARAMS,
    },
    "ErtboxParameters": {
        1: ERTBOX_PETRO_PARAMS_A,
        2: ERTBOX_PETRO_PARAMS_B,
    },
    "Conformity": {
        1: BASECONFORM,
        2: TOPCONFORM,
    },
    "GridModelName": GRID_MODEL,
    "ZoneParam": ZONE_PARAM_NAME,
    "ERTBoxGridName": GRID_MODEL_ERTBOX,
}


class GridJob:
    def __init__(
        self,
        zone_numbers: list[int],
        zone_names: list[str],
        conform_mode_list: list[int],
        use_bottom_surface_list: list[bool],
        use_top_surface_list: list[bool],
    ) -> None:
        self.conformal_mode_list = conform_mode_list
        self.zone_names = zone_names
        self.zone_numbers = zone_numbers
        self.use_bottom_surface_list = use_bottom_surface_list
        self.use_top_surface_list = use_top_surface_list

    def get_arguments(self) -> dict:
        return {
            "ConformalMode": self.conformal_mode_list,
            "ZoneNames": self.zone_names,
            "UseBottomSurface": self.use_bottom_surface_list,
            "UseTopSurface": self.use_top_surface_list,
        }


@pytest.mark.skipunlessroxar
@pytest.mark.parametrize(
    "rms_grid_building_jobs, rms_zone_numbers, rms_zone_names, rms_conform_mode_list,"
    "rms_use_top_surface_list, rms_use_bottom_surface_list,"
    "specified_grid_layout_list,specified_zone_numbers, modify, debug_level",
    [
        (
            # This should represent the conformity setting in the grid model
            ["Grid_building_job"],
            [ZONEA_NUMBER, ZONEB_NUMBER, ZONEC_NUMBER],
            [ZONEA, ZONEB, ZONEC],
            [BASECONFORM_CODE, TOPCONFORM_CODE, PROPORTIONAL_CODE],
            [False, False, False],
            [False, False, False],
            # This should represent the specification in the config file
            # for function copy_rms_parameters
            [BASECONFORM, TOPCONFORM, PROPORTIONAL],
            [ZONEA_NUMBER, ZONEB_NUMBER, ZONEC_NUMBER],
            True,
            DEBUG_VERY_VERBOSE,
        ),
        (
            ["Grid_building_job"],
            [ZONEA_NUMBER, ZONEB_NUMBER],
            [ZONEA, ZONEB],
            [TOPCONFORM_CODE, TOPCONFORM_CODE],
            [True, False, False],
            [False, False, False],
            [TOPCONFORM, TOPCONFORM],
            [ZONEA_NUMBER, ZONEB_NUMBER],
            True,
            DEBUG_VERY_VERBOSE,
        ),
        (
            [],
            [ZONEA_NUMBER, ZONEB_NUMBER, ZONEC_NUMBER],
            [ZONEA, ZONEB, ZONEC],
            [BASECONFORM_CODE, TOPCONFORM_CODE, PROPORTIONAL_CODE],
            [False, False, False],
            [False, False, False],
            [BASECONFORM, TOPCONFORM, PROPORTIONAL],
            [ZONEA_NUMBER, ZONEB_NUMBER, ZONEC_NUMBER],
            True,
            DEBUG_VERY_VERBOSE,
        ),
        (
            ["Grid_building_job1", "Grid_building_job2"],
            [ZONEA_NUMBER, ZONEB_NUMBER, ZONEC_NUMBER],
            [ZONEA, ZONEB, ZONEC],
            [BASECONFORM_CODE, TOPCONFORM_CODE, PROPORTIONAL_CODE],
            [False, False, False],
            [False, False, False],
            [BASECONFORM, TOPCONFORM, PROPORTIONAL],
            [ZONEA_NUMBER, ZONEB_NUMBER, ZONEC_NUMBER],
            True,
            DEBUG_VERY_VERBOSE,
        ),
    ],
)
def test_check_grid_layout(
    mocker,
    rms_grid_building_jobs: list[str],
    rms_zone_numbers: list[int],
    rms_zone_names: list[str],
    rms_conform_mode_list: list[int],
    rms_use_top_surface_list: list[bool],
    rms_use_bottom_surface_list: list[bool],
    specified_grid_layout_list: list[str],
    specified_zone_numbers: list[int],
    modify: bool,
    debug_level: int,
) -> None:
    # Create a mock version of rmsapi functions in rmsapi.jobs.Job object
    mocker.patch.object(Job, "get_job_names", return_value=rms_grid_building_jobs)
    mocker.patch.object(
        Job,
        "get_job",
        return_value=GridJob(
            rms_zone_numbers,
            rms_zone_names,
            rms_conform_mode_list,
            rms_use_bottom_surface_list,
            rms_use_top_surface_list,
        ),
    )

    # For each zone check grid layout with RMS grid building job
    # (here the mock of the rmsapi functions)

    conformity_dict = get_grid_conformity(GRID_MODEL_NAME, debug_level=debug_level)
    if conformity_dict:
        for indx, zone_number in enumerate(specified_zone_numbers):
            grid_layout = specified_grid_layout_list[indx]
            conformity = conformity_dict[zone_number]
            assert conformity == grid_layout


def create_grids(project):
    nx = NX
    ny = NY
    nz_zoneA = NZ_ZONEA
    nz_zoneB = NZ_ZONEB
    nz = nz_zoneA + nz_zoneB
    dimension = (nx, ny, nz)
    dimension_ertbox = (nx, ny, max(nz_zoneA, nz_zoneB))
    increment = (XINC, YINC, ZINC)
    origin = ORIGIN
    rotation = ROTATION

    subgrid_dict = {
        ZONEA: nz_zoneA,
        ZONEB: nz_zoneB,
    }
    geogrid = xtgeo.create_box_grid(
        dimension,
        origin=origin,
        increment=increment,
        rotation=rotation,
        flip=-1,
    )
    actnum = geogrid.get_actnum()
    # Zone A and Zone B
    actnum.values[:10, :20, :] = 0

    # Zone A Base conform eroded from above
    actnum.values[10:30, 30:70, :6] = 0
    actnum.values[15:35, 5:25, :4] = 0

    # Zone B Top Conform eroded from below
    actnum.values[25:35, 10:25, 11:] = 0
    actnum.values[5:30, 5:25, 20:] = 0
    geogrid.set_actnum(actnum)
    geogrid.set_subgrids(subgrid_dict)
    geogrid.to_roxar(project, GRID_MODEL)

    ertboxgrid = xtgeo.create_box_grid(
        dimension_ertbox,
        origin=origin,
        increment=increment,
        rotation=rotation,
        flip=-1,
    )
    ertboxgrid.to_roxar(project, GRID_MODEL_ERTBOX)


def compare_results_with_reference(project):
    # Compare with reference
    for i in range(len(PETROPARAMS_REFERENCE)):
        petro_name_reference = PETROPARAMS_REFERENCE[i]
        petro_name = PETROPARAMS[i]
        values1 = project.grid_models[GRID_MODEL].properties[petro_name].get_values()
        values2 = (
            project.grid_models[GRID_MODEL]
            .properties[petro_name_reference]
            .get_values()
        )
        assert np.allclose(values1, values2)


def import_petro_params(project):
    for i in range(len(PETROPARAMS_REFERENCE)):
        petro_name_reference = PETROPARAMS_REFERENCE[i]
        filename = Path(REFERENCE_DIR) / Path(petro_name_reference + ".roff")
        petro_reference = xtgeo.gridproperty_from_file(filename, fformat="roff")
        petro_reference.to_roxar(project, GRID_MODEL, petro_name_reference)

    filename = Path(REFERENCE_DIR) / Path(ZONE_PARAM_NAME + ".roff")
    zone_param = xtgeo.gridproperty_from_file(filename, fformat="roff")
    zone_param.to_roxar(project, GRID_MODEL, ZONE_PARAM_NAME)


@pytest.mark.skipunlessroxar
def test_copy_between_geo_and_ertbox_grids():
    """Create a tmp RMS project for testing, populate with basic data."""
    prj1 = str(PRJ)

    print("\n******** Setup RMS project!\n")
    if isdir(prj1):
        print("Remove existing project! (1)")
        shutil.rmtree(prj1)

    project = rmsapi.Project.create()
    project.seed = 12345
    rox = xtgeo.RoxUtils(project)
    print("rmsapi version is", rox.roxversion)
    print("RMS version is", rox.rmsversion(rox.roxversion))
    assert "1." in rox.roxversion
    # Create both geogrid and ertbox grid
    create_grids(project)

    # Load zone and petro params from file into geogrid
    import_petro_params(project)

    # Copy to ertbox
    GEO_TO_ERTBOX_DICT["project"] = project
    copy_rms_param(GEO_TO_ERTBOX_DICT)

    # Copy back from ertbox
    ERTBOX_TO_GEO_DICT["project"] = project
    copy_rms_param(ERTBOX_TO_GEO_DICT)

    # Verify that original is equal to the new params
    compare_results_with_reference(project)

    project.save_as(prj1)
    project.close()

    if REMOVE_RMS_PROJECT_AFTER_TEST:
        print("\n******* Teardown RMS project!\n")
        if isdir(PRJ):
            print("Remove existing project!")
            shutil.rmtree(PRJ)
        if isdir(RESULTDIR):
            print("Remove temporary files")
            shutil.rmtree(RESULTDIR)
