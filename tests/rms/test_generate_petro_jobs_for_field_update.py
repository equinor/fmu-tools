"""Run tests in RMS using rmsapi to generate jobs for petrophysics module

Creates a tmp RMS project in given version which is used as fixture
to test the script generate_petro_jobs_for_field_update.py


This requires a ROXAPI license, and to be ran in a "roxenvbash" environment; hence
the decorator "roxapilicense"

"""

import contextlib
import copy
import filecmp
import shutil
from os.path import isdir
from pathlib import Path
from typing import Dict, List

import pytest
import xtgeo  # type: ignore

with contextlib.suppress(ImportError):
    import roxar  # type: ignore
    import roxar.jobs  # type: ignore

from fmu.tools.rms.generate_petro_jobs_for_field_update import (  # type: ignore
    check_rms_project,
    create_new_petro_job_per_facies,
    define_new_variable_names_and_correlation_matrix,
    read_specification_file,
    write_petro_job_to_file,
)

# ======================================================================================
# settings to create RMS project!
REMOVE_RMS_PROJECT_AFTER_TEST = True

TMPD = Path("TMP")
TMPD.mkdir(parents=True, exist_ok=True)


PROJNAME = "tmp_project_generate_petro_jobs.rmsxxx"
PRJ = str(TMPD / PROJNAME)
RESULTDIR = TMPD / "jobs"
RESULTDIR.mkdir(parents=True, exist_ok=True)

REFERENCE_DIR = Path("tests/rms/generate_jobs_testdata")
CONFIG_FILE_ORIGINAL_SINGLE_ZONE_JOB = (
    REFERENCE_DIR / "generate_original_single_zone_job.yml"
)
CONFIG_FILE_ORIGINAL_MULTI_ZONE_JOB = (
    REFERENCE_DIR / "generate_original_multi_zone_job.yml"
)
CONFIG_FILE_SINGLE_ZONE = REFERENCE_DIR / "generate_petro_single_zone_jobs.yml"
CONFIG_FILE_MULTI_ZONE = REFERENCE_DIR / "generate_petro_multi_zone_jobs.yml"
JOB_TYPE = "Petrophysical Modeling"


REFERENCE_FILES_SINGLE_ZONE_GRID = [
    REFERENCE_DIR / "F1_single_zone_petro.txt",
    REFERENCE_DIR / "F2_single_zone_petro.txt",
    REFERENCE_DIR / "F3_single_zone_petro.txt",
]
REFERENCE_FILES_MULTI_ZONE_GRID = [
    REFERENCE_DIR / "F1_multi_zone_petro.txt",
    REFERENCE_DIR / "F2_multi_zone_petro.txt",
    REFERENCE_DIR / "F3_multi_zone_petro.txt",
]

OWNER_STRING_SINGLE_ZONE = ["Grid models", "SingleZoneBox", "Grid"]
OWNER_STRING_MULTI_ZONE = ["Grid models", "MultiZoneBox", "Grid"]


@pytest.mark.parametrize(
    "original_variable_names, facies_name, new_variable_names_input, "
    "original_lower_corr_mat, reference_var_names, reference_corr_mat",
    [
        (
            ["phit", "vsh", "klogh", "vphyl"],
            "F1",
            ["F1_klogh", "F1_phit"],
            [[], [0.2], [0.3, 0.4], [0.5, 0.6, 0.7]],
            ["F1_phit", "F1_klogh"],
            [[], [0.3]],
        ),
        (
            ["phit", "vsh", "klogh", "vphyl"],
            "F2",
            ["F2_vphyl", "F2_vsh", "F2_klogh"],
            [[], [0.2], [0.3, 0.4], [0.5, 0.6, 0.7]],
            ["F2_vsh", "F2_klogh", "F2_vphyl"],
            [[], [0.4], [0.6, 0.7]],
        ),
        (
            ["phit", "vsh", "klogh", "vphyl"],
            "F3",
            ["F3_klogh"],
            [[], [0.2], [0.3, 0.4], [0.5, 0.6, 0.7]],
            ["F3_klogh"],
            [],
        ),
    ],
)
def test_define_new_variable_names_and_correlation_matrix(
    original_variable_names: List[str],
    facies_name: str,
    new_variable_names_input: List[str],
    original_lower_corr_mat: List[List[float]],
    reference_var_names: List[str],
    reference_corr_mat: List[List[float]],
) -> None:
    new_variable_names, new_lower_corr_mat = (
        define_new_variable_names_and_correlation_matrix(
            original_variable_names,
            facies_name,
            new_variable_names_input,
            original_lower_corr_mat,
        )
    )

    print(f"Original var names:  {original_variable_names}")
    print(f"New var names:       {new_variable_names}")
    print(f"Original correlations:  {original_lower_corr_mat}")
    print(f"New correlations:       {new_lower_corr_mat}")

    # Compare lists with reference
    l1 = new_variable_names
    l2 = reference_var_names
    res = [x for x in l1 + l2 if x not in l1 or x not in l2]
    assert len(res) == 0

    # Compare corr matrix with reference
    nrows = len(new_lower_corr_mat)
    assert nrows == len(reference_corr_mat)
    for j in range(nrows):
        ncol = len(new_lower_corr_mat[j])
        assert ncol == len(reference_corr_mat[j])
        for i in range(ncol):
            assert new_lower_corr_mat[j][i] == reference_corr_mat[j][i]


def create_original_petro_job(spec_dict: Dict) -> str:
    grid_name = spec_dict["grid_name"]
    owner_string_list = ["Grid models", grid_name, "Grid"]
    job_name = spec_dict["original_job_name"]
    petro_job = roxar.jobs.Job.create(
        owner=owner_string_list, type=JOB_TYPE, name=job_name
    )
    roxar.jobs.Job.license_checkout(job_types=[JOB_TYPE])
    job_arguments = define_setting_for_original_job(spec_dict)
    petro_job.set_arguments(job_arguments)
    checked_ok, err_msg_list, warn_msg_list = petro_job.check(job_arguments)
    if not checked_ok:
        print("Errors when checking job arguments:")
        for s in err_msg_list:
            print(s)
        print("Warnings when checking job arguments:")
        for s in warn_msg_list:
            print(s)
        raise ValueError("Errors in arguments for job")
    print(f"Create original petrophysics job:  {job_name}")
    petro_job.save()
    return job_name


def define_setting_for_original_job(spec_dict: Dict) -> Dict:
    # Use specified zones, facies and variable names and selected model parameters,
    # but assign default to all other settings
    facies_real_name = spec_dict["facies_real_name"]
    grid_name = spec_dict["grid_name"]
    original_job_name = spec_dict["original_job_name"]
    original_job_settings = spec_dict["original_job_settings"]
    simulation_mode = spec_dict["mode"]
    simulation_mode = simulation_mode.upper()
    zone_dict = original_job_settings["zones"]
    zone_model_list = []
    common_petro_set = None
    common_petro_list = []
    for zone_name, facies_dict in zone_dict.items():
        facies_model_list = []
        for facies_name, petro_dict in facies_dict.items():
            var_model_list = []
            petro_list = list(petro_dict.keys())
            if common_petro_set is None:
                common_petro_set = set(petro_list)
                common_petro_list = copy.copy(petro_list)
            else:
                if len(common_petro_set.difference(set(petro_list))) > 0:
                    raise ValueError(
                        "Expecting same set of petro variables "
                        "for all facies and all zones in original petro "
                        f"job {original_job_name}"
                    )
            for petro_name, petro_model_param_list in petro_dict.items():
                model_param_mean = petro_model_param_list[0]
                model_param_stdev = petro_model_param_list[1]
                var_model_list.append(
                    {
                        "ModelingMode": "PREDICTION/SIMULATION",
                        "VariableName": petro_name,
                        "Variogram Models": [
                            {
                                "Mode": "STANDARD",
                                "RangeAzimuth": 2500.0,
                                "RangeAzimuthNormal": 1000,
                                "RangeVertical": 25.0,
                                "Type": "GENERAL_EXPONENTIAL",
                                "GeneralExponentialPower": 1.8,
                                "VariogramSillType": "CONSTANT",
                                "VariogramSill": model_param_stdev,
                            },
                        ],
                        "Transform Sequence": [
                            {
                                "EstimationMode": "FIXED",
                                "WeightLog": "- none -",
                                "Truncate": [
                                    {
                                        "Active": True,
                                        "AppliedTo": "INPUT_AND_OUTPUT",
                                        "Mode": "MIN",
                                        "Min": 0,
                                        "SequenceNumber": 0,
                                    }
                                ],
                                "Mean": [
                                    {
                                        "Active": True,
                                        "Automated": False,
                                        "Mean": model_param_mean,
                                        "SequenceNumber": 1,
                                    }
                                ],
                            },
                        ],
                    }
                )
            corr_model = [{"CorrelationMatrix": [[], [0.5]]}]
            facies_model_list.append(
                {
                    "FaciesName": facies_name,
                    "Variable Models": var_model_list,
                    "Correlation Model": corr_model,
                }
            )
        zone_model_list.append(
            {"ZoneName": zone_name, "Facies Models": facies_model_list}
        )

    return {
        "Algorithm": simulation_mode,
        "ConditionOnBlockedWells": False,
        "InputFaciesProperty": ["Grid models", grid_name, facies_real_name],
        "VariableNames": common_petro_list,
        "Zone Models": zone_model_list,
        "PrefixOutputName": "original",
    }


def rename_subgrids(xtgeo_grd: xtgeo.Grid) -> None:
    nsubgrids = len(list(xtgeo_grd.subgrids.keys()))
    subgrid_names = []
    for i in range(nsubgrids):
        name_of_subgrid = f"Zone{i + 1}"
        subgrid_names.append(name_of_subgrid)
    xtgeo_grd.rename_subgrids(subgrid_names)


# Here the temporary RMS project is created. It contains a grid,
# a facies parameter and an original petrophysical job
def create_project():
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

    # Read specification for original petrophysical job
    # using facies realization as input for single zone grid
    spec_original_dict = read_specification_file(
        CONFIG_FILE_ORIGINAL_SINGLE_ZONE_JOB, check=False
    )
    rms_grid_name = spec_original_dict["grid_name"]
    rms_facies_real_name = spec_original_dict["facies_real_name"]
    grid_file_name = spec_original_dict["grid_file_name"]
    facies_file_name = spec_original_dict["facies_file_name"]

    # populate with grid and props
    grid_data = REFERENCE_DIR / grid_file_name
    grd = xtgeo.grid_from_file(grid_data, fformat="roff")
    grd.to_roxar(project, rms_grid_name)
    facies_data = REFERENCE_DIR / facies_file_name
    facies = xtgeo.gridproperty_from_file(
        facies_data, name=rms_facies_real_name, fformat="roff"
    )
    facies.to_roxar(project, rms_grid_name, rms_facies_real_name)

    job_name = create_original_petro_job(spec_original_dict)
    petro_job = roxar.jobs.Job.get_job(OWNER_STRING_SINGLE_ZONE, JOB_TYPE, job_name)
    print(f"Run {job_name}")
    petro_job.execute()

    # Read specification for original petrophysical job
    # using facies realization as input for multi zone grid
    spec_original_dict = read_specification_file(
        CONFIG_FILE_ORIGINAL_MULTI_ZONE_JOB, check=False
    )
    rms_grid_name = spec_original_dict["grid_name"]
    rms_facies_real_name = spec_original_dict["facies_real_name"]
    grid_file_name = spec_original_dict["grid_file_name"]
    facies_file_name = spec_original_dict["facies_file_name"]

    # populate with grid and props
    grid_data = REFERENCE_DIR / grid_file_name
    grd = xtgeo.grid_from_file(grid_data, fformat="roff")
    rename_subgrids(grd)
    grd.to_roxar(project, rms_grid_name)
    facies_data = REFERENCE_DIR / facies_file_name
    facies = xtgeo.gridproperty_from_file(
        facies_data, name=rms_facies_real_name, fformat="roff"
    )
    facies.to_roxar(project, rms_grid_name, rms_facies_real_name)

    job_name = create_original_petro_job(spec_original_dict)
    petro_job = roxar.jobs.Job.get_job(OWNER_STRING_MULTI_ZONE, JOB_TYPE, job_name)
    print(f"Run {job_name}")
    petro_job.execute()

    project.save_as(prj1)
    return project


# Now run the script to generate one petro job per facies
# using the same settings (same model parameters)
# as the original petro job for the
# petrophysical properties.
@pytest.mark.skipunlessroxar
def test_generate_jobs() -> None:
    """Test generate_petro_jobs_for_field_update"""

    project = create_project()
    check_rms_project(project)

    # Now run script to generate one petro job per facies for single zone grid
    spec_case = read_specification_file(CONFIG_FILE_SINGLE_ZONE)
    job_name_list = create_new_petro_job_per_facies(spec_case)
    for n, job_name in enumerate(job_name_list):
        filename = RESULTDIR / Path(job_name + "_single.txt")
        reference_filename = REFERENCE_FILES_SINGLE_ZONE_GRID[n]
        write_petro_job_to_file(OWNER_STRING_SINGLE_ZONE, JOB_TYPE, job_name, filename)
        # Compare text files with job parameters with reference for single zone jobs
        check = filecmp.cmp(filename, reference_filename)
        if check:
            print("Check OK for single zone grid")
        assert check

    for n, job_name in enumerate(job_name_list):
        petro_job = roxar.jobs.Job.get_job(OWNER_STRING_SINGLE_ZONE, JOB_TYPE, job_name)
        print(f"Run {job_name}")
        petro_job.execute()

    # Now run script to generate one petro job per facies for single zone grid
    spec_case = read_specification_file(CONFIG_FILE_MULTI_ZONE)
    job_name_list = create_new_petro_job_per_facies(spec_case)
    for n, job_name in enumerate(job_name_list):
        filename = RESULTDIR / Path(job_name + "_multi.txt")
        reference_filename = REFERENCE_FILES_MULTI_ZONE_GRID[n]
        write_petro_job_to_file(OWNER_STRING_MULTI_ZONE, JOB_TYPE, job_name, filename)
        # Compare text files with job parameters with reference for single zone jobs
        check = filecmp.cmp(filename, reference_filename)
        if check:
            print("Check OK for multi zone grid")
        assert check

    for n, job_name in enumerate(job_name_list):
        petro_job = roxar.jobs.Job.get_job(OWNER_STRING_MULTI_ZONE, JOB_TYPE, job_name)
        print(f"Run {job_name}")
        petro_job.execute()

    project.save()
    project.close()
    if REMOVE_RMS_PROJECT_AFTER_TEST:
        print("\n******* Teardown RMS project!\n")
        if isdir(PRJ):
            print("Remove existing project!")
            shutil.rmtree(PRJ)
        if isdir(RESULTDIR):
            print("Remove temporary files")
            shutil.rmtree(RESULTDIR)
