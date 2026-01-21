import contextlib
import pprint
import shutil
from os.path import isdir
from pathlib import Path

import numpy as np
import pytest
import xtgeo

from fmu.tools.rms.localisation import (
    create_obs_with_localisation_attributes as get_obs,
)

with contextlib.suppress(ImportError):
    import rmsapi
    import rmsapi.jobs


DEBUG_PRINT = False
REMOVE_RMS_PROJECT_AFTER_TEST = False
PP = pprint.PrettyPrinter(depth=7)

TMPD = Path("TMP")
TMPD.mkdir(parents=True, exist_ok=True)
PROJNAME = "tmp_project_create_localisation_obs.rmsxxx"
PRJ = str(TMPD / PROJNAME)
RESULTDIR = TMPD / "result_obs_csv_files"
RESULTDIR.mkdir(parents=True, exist_ok=True)
INPUTDIR = Path("tests/rms/localisation") / "input_files"
EXPORT_PATH = RESULTDIR
IMPORT_PATH = INPUTDIR


GRIDNAME = "TestGrid"
NX = 50
NY = 60
NZ = 25
XINC = 50.0
YINC = 50.0
ZINC = 1.0
GRID_DIM = (NX, NY, NZ)
INCREMENT = (XINC, YINC, ZINC)
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


def create_wells(project) -> list[str]:
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
    owner_strings: list[str],
    job_type: str,
    job_name: str,
    well_names: list[str],
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
    assert project
    if REMOVE_RMS_PROJECT_AFTER_TEST:
        print("\n******* Teardown RMS project!\n")
        if isdir(PRJ):
            print("Remove existing project!")
            shutil.rmtree(PRJ)
        if isdir(RESULTDIR):
            print("Remove temporary files")
            shutil.rmtree(RESULTDIR)


@pytest.mark.parametrize(
    "filename, result_dict_list",
    [
        (
            INPUTDIR / Path("ex1_ert_summary.obs"),
            [
                {
                    "DATE": "2019-08-01",
                    "ERROR": "100",
                    "KEY": "WOPRL__1:A3",
                    "VALUE": "266",
                    "ert_id": "A3_WOPR_VALYSAR_01_08_2019",
                    "obs_type": "WOPRL__1",
                    "wellname": "A3",
                },
                {
                    "DATE": "2019-05-05",
                    "ERROR": "10",
                    "KEY": "WBHP:A2",
                    "VALUE": "266.8",
                    "ert_id": "A2_WBHP_05_05_2019",
                    "obs_type": "WBHP",
                    "wellname": "A2",
                },
            ],
        ),
        (
            INPUTDIR / Path("ex2_ert_summary.obs"),
            [
                {
                    "DATE": "2018-06-22",
                    "ERROR": "0.1",
                    "KEY": "WWCT:A1",
                    "VALUE": "2.9680345505767036e-06",
                    "ert_id": "WWCT_A1_1",
                    "obs_type": "WWCT",
                    "wellname": "A1",
                },
                {
                    "DATE": "2020-02-08",
                    "ERROR": "50",
                    "KEY": "WGOR:A4",
                    "VALUE": "134.9546356201172",
                    "ert_id": "WGOR_A4_5",
                    "obs_type": "WGOR",
                    "wellname": "A4",
                },
            ],
        ),
    ],
)
def test_read_ert_summary_obs(filename, result_dict_list):
    obs_dict_list = get_obs.read_ert_summary_obs_file(filename)
    for indx, obs_dict in enumerate(obs_dict_list):
        PP.pprint(obs_dict)
        assert result_dict_list[indx] == obs_dict


@pytest.mark.parametrize(
    "spec,"
    "ref_result_summary_file, ref_result_local_file,"
    "ref_use_wellhead_pos, ref_grid_model_name, ref_blocked_well_set_name,"
    "ref_trajector_name, ref_well_renaming_file, ref_ert_obs_file,"
    "ref_ert_config_field_param_file, ref_rms_corr_file,"
    "ref_default_ranges, ref_min_range_hwell, ref_mult_hwell_length,"
    "ref_zone_dict, ref_field_settings, ref_expand_spec",
    [
        (
            {
                "localisation": {
                    "result_summary_obs_file": "summary_obs.csv",
                    "result_localisation_obs_file": "localisation_obs_attributes.csv",
                    "expand_wildcards": True,
                    "rms_settings": {
                        "use_well_head_position": True,
                        "grid_model": "Geogrid_Valysar",
                        "blocked_well_set": "BW",
                        "trajectory": "Drilled trajectory",
                    },
                    "input_files": {
                        "well_renaming_table": "rms_eclipse.renaming_table",
                        "ert_summary_obs_file": "ert_observations.obs",
                        "rms_field_correlation_file": "correlation_ranges.txt",
                        "ert_config_field_param_file": "ahm_field_aps.ert",
                    },
                    "zone_codes": {
                        "Valysar": 1,
                        "Therys": 2,
                        "Volon": 3,
                    },
                    "default_field_settings": {
                        "ranges": [2000.0, 1000.0, 45.0],
                        "min_range_hwell": 150.0,
                        "mult_hwell_length": 1.5,
                    },
                    "field_settings": [
                        {
                            "zone_name": ["Valysar", "Therys"],
                            "obs_type": ["all"],
                            "well_names": ["all"],
                            "ranges": [1500.0, 1250.0, 45.0],
                        },
                        {
                            "zone_name": ["Volon"],
                            "obs_type": ["all"],
                            "well_names": ["all"],
                            "ranges": [1000.0, 1000.0, 35.0],
                        },
                    ],
                }
            },
            "summary_obs.csv",
            "localisation_obs_attributes.csv",
            True,
            "Geogrid_Valysar",
            "BW",
            "Drilled trajectory",
            "rms_eclipse.renaming_table",
            "ert_observations.obs",
            "ahm_field_aps.ert",
            "correlation_ranges.txt",
            [2000.0, 1000.0, 45.0],
            150.0,
            1.5,
            {
                "Valysar": 1,
                "Therys": 2,
                "Volon": 3,
            },
            [
                {
                    "zone_name": ["Valysar", "Therys"],
                    "obs_type": ["all"],
                    "well_names": ["all"],
                    "ranges": [1500.0, 1250.0, 45.0],
                },
                {
                    "zone_name": ["Volon"],
                    "obs_type": ["all"],
                    "well_names": ["all"],
                    "ranges": [1000.0, 1000.0, 35.0],
                },
            ],
            True,
        ),
        (
            {
                "localisation": {
                    "result_summary_obs_file": "summary_obs.csv",
                    "result_localisation_obs_file": "localisation_obs_attributes.csv",
                    "expand_wildcards": False,
                    "rms_settings": {
                        "use_well_head_position": True,
                        "grid_model": "Geogrid_Valysar",
                        "blocked_well_set": "BW",
                        "trajectory": "Drilled trajectory",
                    },
                    "input_files": {
                        "well_renaming_table": "rms_eclipse.renaming_table",
                        "ert_summary_obs_file": "ert_observations.obs",
                        "rms_field_correlation_file": "correlation_ranges.txt",
                        "ert_config_field_param_file": "ahm_field_aps.ert",
                    },
                    "zone_codes": {
                        "Valysar": 1,
                        "Therys": 2,
                        "Volon": 3,
                    },
                    "default_field_settings": {
                        "ranges": [2000.0, 1000.0, 45.0],
                        "min_range_hwell": 150.0,
                        "mult_hwell_length": 1.5,
                    },
                    "field_settings": [
                        {
                            "zone_name": ["Valysar", "Therys"],
                            "obs_type": ["all"],
                            "well_names": ["all"],
                            "ranges": [1500.0, 1250.0, 45.0],
                        },
                        {
                            "zone_name": ["Volon"],
                            "obs_type": ["all"],
                            "well_names": ["all"],
                            "ranges": [1000.0, 1000.0, 35.0],
                        },
                    ],
                }
            },
            "summary_obs.csv",
            "localisation_obs_attributes.csv",
            True,
            "Geogrid_Valysar",
            "BW",
            "Drilled trajectory",
            "rms_eclipse.renaming_table",
            "ert_observations.obs",
            "ahm_field_aps.ert",
            "correlation_ranges.txt",
            [2000.0, 1000.0, 45.0],
            150.0,
            1.5,
            {
                "Valysar": 1,
                "Therys": 2,
                "Volon": 3,
            },
            [
                {
                    "zone_name": ["Valysar", "Therys"],
                    "obs_type": ["all"],
                    "well_names": ["all"],
                    "ranges": [1500.0, 1250.0, 45.0],
                },
                {
                    "zone_name": ["Volon"],
                    "obs_type": ["all"],
                    "well_names": ["all"],
                    "ranges": [1000.0, 1000.0, 35.0],
                },
            ],
            False,
        ),
    ],
)
def test_get_specification(
    spec: dict,
    ref_result_summary_file: str,
    ref_result_local_file: str,
    ref_use_wellhead_pos: bool,
    ref_grid_model_name: str,
    ref_blocked_well_set_name: str,
    ref_trajector_name: str,
    ref_well_renaming_file: str,
    ref_ert_obs_file: str,
    ref_ert_config_field_param_file: str,
    ref_rms_corr_file: str,
    ref_default_ranges: list[float],
    ref_min_range_hwell: float,
    ref_mult_hwell_length: float,
    ref_zone_dict: dict,
    ref_field_settings: dict,
    ref_expand_spec: bool,
) -> None:
    (
        result_summary_obs_file,
        result_localisation_obs_file,
        use_well_head_position,
        grid_model_name,
        blocked_well_set_name,
        trajectory_name,
        well_renaming_file,
        ert_obs_file,
        ert_config_field_param_file,
        rms_field_correlation_file,
        default_ranges,
        min_range_hwell,
        mult_hwell_length,
        zone_dict,
        field_settings,
        expand_spec,
    ) = get_obs.get_specification(spec)

    assert result_summary_obs_file == ref_result_summary_file
    assert result_localisation_obs_file == ref_result_local_file
    assert use_well_head_position == ref_use_wellhead_pos
    if not use_well_head_position:
        assert grid_model_name == ref_grid_model_name
        assert blocked_well_set_name == ref_blocked_well_set_name
    else:
        assert trajectory_name == ref_trajector_name
    assert well_renaming_file == ref_well_renaming_file
    assert ert_obs_file == ref_ert_obs_file
    assert ert_config_field_param_file == ref_ert_config_field_param_file
    assert rms_field_correlation_file == ref_rms_corr_file
    assert default_ranges == ref_default_ranges
    assert min_range_hwell == ref_min_range_hwell
    assert mult_hwell_length == ref_mult_hwell_length
    assert zone_dict == ref_zone_dict
    assert field_settings == ref_field_settings
    assert expand_spec == ref_expand_spec


@pytest.mark.parametrize(
    "filename, ref_table",
    [
        (
            "tests/rms/localisation/input_files/rms_rename_wells.txt",
            {
                "A1": "55_33-A-1",
                "A2": "55_33-A-2",
                "A3": "55_33-A-3",
            },
        ),
    ],
)
def test_read_renaming_table(filename: str, ref_table: dict) -> None:
    renaming_dict = get_obs.read_renaming_table(filename)
    assert renaming_dict == ref_table


@pytest.mark.parametrize(
    "filename, ref_field_names",
    [
        (
            "tests/rms/localisation/input_files/ahm_field_aps.ert",
            [
                "aps_Valysar_GRF1",
                "aps_Valysar_GRF2",
                "aps_Valysar_GRF3",
                "aps_Therys_GRF1",
                "aps_Therys_GRF2",
                "aps_Therys_GRF3",
            ],
        ),
    ],
)
def test_read_field_param_names(filename: str, ref_field_names: list[str]) -> None:
    field_names = get_obs.read_field_param_names(filename)
    assert field_names == ref_field_names


@pytest.mark.parametrize(
    "input_field_names, zone_dict, ref_used_zone_names",
    [
        (
            [
                "aps_Valysar_GRF1",
                "aps_Valysar_GRF2",
                "aps_Valysar_GRF3",
                "aps_Therys_GRF1",
                "aps_Therys_GRF2",
                "aps_Therys_GRF3",
            ],
            {
                "Valysar": 1,
                "Therys": 2,
                "Volon": 3,
            },
            [
                "Valysar",
                "Therys",
            ],
        ),
        (
            [
                "aps_Valysar_GRF1",
                "aps_Valysar_GRF2",
                "aps_Valysar_GRF3",
                "aps_Therys_GRF1",
                "aps_Therys_GRF2",
                "aps_Therys_GRF3",
                "aps_Volon_GRF1",
            ],
            {
                "Valysar": 1,
                "Therys": 2,
                "Volon": 3,
            },
            [
                "Valysar",
                "Therys",
                "Volon",
            ],
        ),
    ],
)
def test_get_defined_zone_names(
    input_field_names: list[str], zone_dict: dict, ref_used_zone_names: list[str]
) -> None:
    used_zone_names = get_obs.get_defined_zone_names(input_field_names, zone_dict)
    assert used_zone_names == ref_used_zone_names
