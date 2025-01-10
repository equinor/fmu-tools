"""Run tests in RMS using rmsapi to test update_petro_real.py

Creates a tmp RMS project in given version.


This requires a RMSAPI license, and to be ran in a "roxenvbash" environment

"""

import contextlib
import shutil
from os.path import isdir
from pathlib import Path
from typing import List, Tuple

import numpy as np
import pytest
import xtgeo

with contextlib.suppress(ImportError):
    import rmsapi


from fmu.tools.rms import (
    export_initial_field_parameters,
    import_updated_field_parameters,
    update_petro_parameters,
)

# ======================================================================================
# settings to create RMS project!
DEBUG_PRINT = False
REMOVE_RMS_PROJECT_AFTER_TEST = False

TMPD = Path("TMP")
TMPD.mkdir(parents=True, exist_ok=True)


PROJNAME = "tmp_project_update_petro_real.rmsxxx"
PRJ = str(TMPD / PROJNAME)
RESULTDIR = TMPD / "update_petro"
RESULTDIR.mkdir(parents=True, exist_ok=True)

EXPORT_PATH = RESULTDIR
IMPORT_PATH = RESULTDIR

FACIES_CODE_NAMES = {
    1: "F1",
    2: "F2",
    3: "F3",
    4: "F4",
}

ZONE_CODE_NAMES = {
    1: "ZoneA",
    2: "ZoneB",
}


USED_PETRO_DICT = {
    "ZoneA": {
        "F1": ["P1"],
        "F2": ["P1", "P2"],
    },
    "ZoneB": {
        "F3": ["P2"],
        "F2": ["P1", "P2"],
    },
}
# This grid is always a single zone grid
GRID_MODEL_ERTBOX = "ERTBOX"

# This grid is a single zone geogrid
GRID_MODEL_GEO_SINGLE = "SingleZoneGrid"

# This grid is a multi zone geogrid
GRID_MODEL_GEO_MULTI = "MultiZoneGrid"

FACIES_REAL_NAME = "Facies"
ZONE_PARAM_NAME = "Zones"

NX = 5
NY = 6
NZ_ERTBOX = 5
NZ = 10

SUBGRID_DICT = {
    "ZoneA": int(NZ / 2),
    "ZoneB": NZ - int(NZ / 2),
}

ZONE_FACIES_PETRO_VALUES = {
    "ZoneA": {
        "F1": {
            "P1": 10.0,
            "P2": 100.0,
        },
        "F2": {
            "P1": 20.0,
            "P2": 150.0,
        },
        "F3": {
            "P1": 14,
            "P2": 130.0,
        },
        "F4": {
            "P1": 28,
            "P2": 165.0,
        },
    },
    "ZoneB": {
        "F1": {
            "P1": 16.0,
            "P2": 110.0,
        },
        "F2": {
            "P1": 22.0,
            "P2": 160.0,
        },
        "F3": {
            "P1": 12.0,
            "P2": 120.0,
        },
        "F4": {
            "P1": 25.0,
            "P2": 175.0,
        },
    },
}


def make_facies_param_multizone(dimensions: Tuple[int, int, int]):
    values = np.zeros(dimensions, dtype=np.uint8)
    sum_layer = 0
    nfacies = len(FACIES_CODE_NAMES)
    for zone_name, nlayers in SUBGRID_DICT.items():
        start_layer = sum_layer
        end_layer = start_layer + nlayers
        petro_per_facies_dict = USED_PETRO_DICT[zone_name]
        facies_names = list(petro_per_facies_dict.keys())
        nfacies = len(facies_names)
        for layer in range(start_layer, end_layer):
            indx = layer % nfacies
            fname = facies_names[indx]
            facies_code = get_facies_code(fname)
            values[:, :, layer] = facies_code
        sum_layer += nlayers
    return values


def make_facies_param_singlezone(dimensions: Tuple[int, int, int]):
    values = np.zeros(dimensions, dtype=np.uint8)
    for k in range(dimensions[2]):
        facies_for_layer = (k % 2) + 1
        values[:, :, k] = facies_for_layer
    return values


def make_zone_param(dimensions: Tuple[int, int, int]):
    values = np.zeros(dimensions, dtype=np.uint8)
    sum_layer = 0
    for zone_name, nlayers in SUBGRID_DICT.items():
        start_layer = sum_layer
        end_layer = start_layer + nlayers
        values[:, :, start_layer:end_layer] = get_zone_code(zone_name)
        sum_layer += nlayers
    return values


def make_petro_param(dimensions: Tuple[int, int, int], value: float):
    values = np.zeros(dimensions, dtype=np.float32)
    values[:, :, :] = value
    return values


def make_reference_petro_param(
    dimensions: Tuple[int, int, int], petro_name: str, facies_values, zone_values
):
    (nx, ny, nz) = dimensions
    values = np.zeros(dimensions, dtype=np.float32)
    # Assign only values for the grid cells containing wanted facies and zone code
    # All other grid cells are kept to 0. They will not be updated anyway and it
    # simplifies the test if they are 0.
    for k in range(nz):
        for j in range(ny):
            for i in range(nx):
                facies_code = facies_values[i, j, k]
                facies_name = FACIES_CODE_NAMES[facies_code]
                zone_code = zone_values[i, j, k]
                zone_name = ZONE_CODE_NAMES[zone_code]
                if zone_name in USED_PETRO_DICT:
                    petro_per_facies_dict = USED_PETRO_DICT[zone_name]
                    if facies_name in petro_per_facies_dict:
                        petro_list = petro_per_facies_dict[facies_name]
                        if petro_name in petro_list:
                            values[i, j, k] = ZONE_FACIES_PETRO_VALUES[zone_name][
                                facies_name
                            ][petro_name]
    return values


def get_zone_code(zone_name: str) -> None:
    for zone_code, name in ZONE_CODE_NAMES.items():
        if name == zone_name:
            return zone_code
    raise ValueError(f"Can not find zone {zone_name} in 'ZONE_CODE_NAMES'")


def get_facies_code(facies_name: str) -> None:
    for facies_code, name in FACIES_CODE_NAMES.items():
        if name == facies_name:
            return facies_code
    raise ValueError(f"Can not find facies {facies_name} in 'FACIES_CODE_NAMES'")


def make_petro_param_per_zone(
    dimensions: Tuple[int, int, int],
    input_values,
    zone_name: str,
    zone_values,
    constant_value: float,
):
    # Will modify input_values and return updated values
    (nx, ny, nz) = dimensions
    if input_values is None:
        values = np.zeros(dimensions, dtype=np.float32)
    else:
        values = input_values
    zone_code = get_zone_code(zone_name)
    selected = zone_values == zone_code
    values[selected] = constant_value
    return values


def get_petro_variable_names() -> List[str]:
    petro_names = []
    for _, petro_per_facies_dict in USED_PETRO_DICT.items():
        for _, petro_list in petro_per_facies_dict.items():
            for petro_name in petro_list:
                if petro_name not in petro_names:
                    petro_names.append(petro_name)
    return petro_names


@pytest.mark.skipunlessroxar
@pytest.fixture(scope="module", autouse=True, name="project")
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

    dimensions = (NX, NY, NZ_ERTBOX)
    xtgeo_ertbox_grid = xtgeo.create_box_grid(dimensions, increment=(50.0, 50.0, 1.0))
    xtgeo_ertbox_grid.to_roxar(project, GRID_MODEL_ERTBOX)

    dimensions = (NX, NY, NZ)
    xtgeo_grid_single = xtgeo.create_box_grid(dimensions, increment=(50.0, 50.0, 1.0))
    xtgeo_grid_single.to_roxar(project, GRID_MODEL_GEO_SINGLE)

    xtgeo_grid_multizone = xtgeo.create_box_grid(
        dimensions, increment=(50.0, 50.0, 1.0)
    )
    xtgeo_grid_multizone.set_subgrids(SUBGRID_DICT)
    xtgeo_grid_multizone.to_roxar(project, GRID_MODEL_GEO_MULTI)

    values = make_facies_param_multizone((NX, NY, NZ))
    xtgeo_facies_param_multi = xtgeo.GridProperty(
        ncol=NX,
        nrow=NY,
        nlay=NZ,
        name=FACIES_REAL_NAME,
        discrete=True,
        grid=xtgeo_grid_multizone,
        codes=FACIES_CODE_NAMES,
        roxar_dtype=np.uint8,
        values=values,
    )
    xtgeo_facies_param_multi.to_roxar(project, GRID_MODEL_GEO_MULTI, FACIES_REAL_NAME)

    values = make_facies_param_singlezone((NX, NY, NZ))
    xtgeo_facies_param_single = xtgeo.GridProperty(
        ncol=NX,
        nrow=NY,
        nlay=NZ,
        name=FACIES_REAL_NAME,
        discrete=True,
        grid=xtgeo_grid_single,
        codes=FACIES_CODE_NAMES,
        roxar_dtype=np.uint8,
        values=values,
    )
    xtgeo_facies_param_single.to_roxar(project, GRID_MODEL_GEO_SINGLE, FACIES_REAL_NAME)

    values = make_zone_param((NX, NY, NZ))
    xtgeo_zone_param_multi = xtgeo.GridProperty(
        ncol=NX,
        nrow=NY,
        nlay=NZ,
        name=ZONE_PARAM_NAME,
        discrete=True,
        grid=xtgeo_grid_multizone,
        codes=ZONE_CODE_NAMES,
        roxar_dtype=np.uint8,
        values=values,
    )
    xtgeo_zone_param_multi.to_roxar(project, GRID_MODEL_GEO_MULTI, ZONE_PARAM_NAME)

    values = np.ones((NX, NY, NZ), dtype=np.uint8)
    xtgeo_zone_param_single = xtgeo.GridProperty(
        ncol=NX,
        nrow=NY,
        nlay=NZ,
        name=ZONE_PARAM_NAME,
        discrete=True,
        grid=xtgeo_grid_single,
        codes=ZONE_CODE_NAMES,
        roxar_dtype=np.uint8,
        values=values,
    )
    xtgeo_zone_param_single.to_roxar(project, GRID_MODEL_GEO_SINGLE, ZONE_PARAM_NAME)

    # make petro param per zone and facies for ertbox grid
    for zone_name, petro_per_facies_dict in USED_PETRO_DICT.items():
        for facies_name, petro_list in petro_per_facies_dict.items():
            for petro_name in petro_list:
                new_petro_name = zone_name + "_" + facies_name + "_" + petro_name
                # Use  constant value for all grid cells
                values = make_petro_param(
                    (NX, NY, NZ_ERTBOX),
                    ZONE_FACIES_PETRO_VALUES[zone_name][facies_name][petro_name],
                )
                xtgeo_petro_param = xtgeo.GridProperty(
                    ncol=NX,
                    nrow=NY,
                    nlay=NZ_ERTBOX,
                    name=new_petro_name,
                    grid=xtgeo_ertbox_grid,
                    roxar_dtype=np.float32,
                    values=values,
                )
                xtgeo_petro_param.to_roxar(project, GRID_MODEL_ERTBOX, new_petro_name)

    # make inital and reference params for petro variables for geo grids
    petro_names = get_petro_variable_names()
    for petro_name in petro_names:
        petro_name_ref = petro_name + "_ref"
        facies_values_multi = xtgeo_facies_param_multi.values
        zone_values_multi = xtgeo_zone_param_multi.values

        facies_values_single = xtgeo_facies_param_single.values
        zone_values_single = xtgeo_zone_param_single.values

        # The reference petro params will depend on zone,
        # facies and be constant for given zone and facies
        values = make_reference_petro_param(
            (NX, NY, NZ), petro_name, facies_values_multi, zone_values_multi
        )
        xtgeo_petro_param = xtgeo.GridProperty(
            ncol=NX,
            nrow=NY,
            nlay=NZ,
            name=petro_name_ref,
            grid=xtgeo_grid_multizone,
            roxar_dtype=np.float32,
            values=values,
        )
        xtgeo_petro_param.to_roxar(project, GRID_MODEL_GEO_MULTI, petro_name_ref)

        values = make_reference_petro_param(
            (NX, NY, NZ), petro_name, facies_values_single, zone_values_single
        )
        xtgeo_petro_param = xtgeo.GridProperty(
            ncol=NX,
            nrow=NY,
            nlay=NZ,
            name=petro_name_ref,
            grid=xtgeo_grid_single,
            roxar_dtype=np.float32,
            values=values,
        )
        xtgeo_petro_param.to_roxar(project, GRID_MODEL_GEO_SINGLE, petro_name_ref)

        # Set initial value of petro params to 0
        # They will be updated and checked with reference after that.
        values = np.zeros((NX, NY, NZ), dtype=np.float32)
        xtgeo_petro_param_initial = xtgeo.GridProperty(
            ncol=NX,
            nrow=NY,
            nlay=NZ,
            name=petro_name_ref,
            grid=xtgeo_grid_single,
            roxar_dtype=np.float32,
            values=values,
        )
        xtgeo_petro_param_initial.to_roxar(project, GRID_MODEL_GEO_MULTI, petro_name)
        xtgeo_petro_param_initial.to_roxar(project, GRID_MODEL_GEO_SINGLE, petro_name)

    # make petro param per facies for multizone grid.
    # They are use as input when updating the petro params
    values = None
    zone_values_multi = xtgeo_zone_param_multi.values
    values_petro_param_dict = {}
    for zone_name, petro_per_facies_dict in USED_PETRO_DICT.items():
        for facies_name, petro_list in petro_per_facies_dict.items():
            if facies_name not in values_petro_param_dict:
                values_petro_param_dict[facies_name] = {}
            for petro_name in petro_list:
                if petro_name not in values_petro_param_dict[facies_name]:
                    # Initialize all values to 0
                    values = np.zeros((NX, NY, NZ), dtype=np.float32)
                    values_petro_param_dict[facies_name][petro_name] = values
                else:
                    values = values_petro_param_dict[facies_name][petro_name]

                # Update values for current zone, facies and petro_param
                # with a constant value
                values_petro_param_dict[facies_name][petro_name] = (
                    make_petro_param_per_zone(
                        (NX, NY, NZ),
                        values,
                        zone_name,
                        zone_values_multi,
                        ZONE_FACIES_PETRO_VALUES[zone_name][facies_name][petro_name],
                    )
                )

    new_petro_param_list = []
    for zone_name, petro_per_facies_dict in USED_PETRO_DICT.items():
        for facies_name, petro_list in petro_per_facies_dict.items():
            for petro_name in petro_list:
                new_petro_name = facies_name + "_" + petro_name
                if new_petro_name not in new_petro_param_list:
                    new_petro_param_list.append(new_petro_name)
                    values = values_petro_param_dict[facies_name][petro_name]
                    xtgeo_petro_param = xtgeo.GridProperty(
                        ncol=NX,
                        nrow=NY,
                        nlay=NZ,
                        name=new_petro_name,
                        grid=xtgeo_grid_multizone,
                        roxar_dtype=np.float32,
                        values=values,
                    )
                    xtgeo_petro_param.to_roxar(
                        project, GRID_MODEL_GEO_MULTI, new_petro_name
                    )

    # make petro param per facies for single zone grid.
    # They are use as input when updating the petro params
    values = None
    zone_values_single = xtgeo_zone_param_single.values
    zone_name = ZONE_CODE_NAMES[1]
    petro_per_facies_dict = USED_PETRO_DICT[zone_name]
    for facies_name, petro_list in petro_per_facies_dict.items():
        for petro_name in petro_list:
            new_petro_name = facies_name + "_" + petro_name
            # Constant value for all grid cells in each zone.
            # The input 'values' will initially be created here
            # and updated for each zone
            values = make_petro_param_per_zone(
                (NX, NY, NZ),
                values,
                zone_name,
                zone_values_single,
                ZONE_FACIES_PETRO_VALUES[zone_name][facies_name][petro_name],
            )
            xtgeo_petro_param = xtgeo.GridProperty(
                ncol=NX,
                nrow=NY,
                nlay=NZ,
                name=new_petro_name,
                grid=xtgeo_grid_single,
                roxar_dtype=np.float32,
                values=values,
            )
            xtgeo_petro_param.to_roxar(project, GRID_MODEL_GEO_SINGLE, new_petro_name)

    project.save_as(prj1)
    project.close()

    yield project

    if REMOVE_RMS_PROJECT_AFTER_TEST:
        print("\n******* Teardown RMS project!\n")
        if isdir(PRJ):
            print("Remove existing project!")
            shutil.rmtree(PRJ)
        if isdir(RESULTDIR):
            print("Remove temporary files")
            shutil.rmtree(RESULTDIR)


@pytest.mark.skipunlessroxar
@pytest.mark.parametrize(
    "used_petro_dict,zone_name_for_single_zone_grid",
    [
        (
            {
                "default": USED_PETRO_DICT["ZoneA"],
            },
            "ZoneA",
        ),
        (
            {
                "default": USED_PETRO_DICT["ZoneB"],
            },
            "ZoneB",
        ),
    ],
)
def test_import_export_updated_field_parameters(
    used_petro_dict: dict,
    zone_name_for_single_zone_grid: str,
) -> None:
    rox = xtgeo.RoxUtils(project=PRJ)

    export_initial_field_parameters(
        rox.project,
        used_petro_dict,
        grid_model_name=GRID_MODEL_ERTBOX,
        zone_name_for_single_zone_grid=zone_name_for_single_zone_grid,
        export_path=EXPORT_PATH,
        debug_print=DEBUG_PRINT,
    )

    # Compare input with reference data
    for zone_name, petro_per_facies_dict in used_petro_dict.items():
        if zone_name == zone_name_for_single_zone_grid:
            for facies_name, petro_list in petro_per_facies_dict.items():
                for petro_name in petro_list:
                    name = zone_name + "_" + facies_name + "_" + petro_name
                    name_from_export = name + "_" + "export"
                    filename = RESULTDIR / Path(name + ".roff")
                    xtgeo_property = xtgeo.gridproperty_from_file(
                        filename, fformat="roff"
                    )
                    xtgeo_property.to_roxar(
                        rox.project, GRID_MODEL_ERTBOX, name_from_export
                    )
                    value1 = (
                        rox.project.grid_models[GRID_MODEL_ERTBOX]
                        .properties[name_from_export]
                        .get_values()
                    )
                    value2 = (
                        rox.project.grid_models[GRID_MODEL_ERTBOX]
                        .properties[name]
                        .get_values()
                    )
                    assert np.allclose(value1, value2)

    import_updated_field_parameters(
        rox.project,
        used_petro_dict,
        grid_model_name=GRID_MODEL_ERTBOX,
        zone_name_for_single_zone_grid=zone_name_for_single_zone_grid,
        import_path=IMPORT_PATH,
        debug_print=DEBUG_PRINT,
    )

    # Compare input with reference data
    for zone_name, petro_per_facies_dict in used_petro_dict.items():
        if zone_name == zone_name_for_single_zone_grid:
            for facies_name, petro_list in petro_per_facies_dict.items():
                for petro_name in petro_list:
                    name = zone_name + "_" + facies_name + "_" + petro_name
                    name_from_export = name + "_" + "export"
                    filename = RESULTDIR / Path(name + ".roff")
                    xtgeo_property = xtgeo.gridproperty_from_file(
                        filename, fformat="roff"
                    )
                    xtgeo_property.to_roxar(
                        rox.project, GRID_MODEL_ERTBOX, name_from_export
                    )
                    values1 = (
                        rox.project.grid_models[GRID_MODEL_ERTBOX]
                        .properties[name_from_export]
                        .get_values()
                    )
                    values2 = (
                        rox.project.grid_models[GRID_MODEL_ERTBOX]
                        .properties[name]
                        .get_values()
                    )
                    assert np.allclose(values1, values2)
    rox.project.save()
    rox.project.close()


@pytest.mark.skipunlessroxar
def test_update_field_parameters_single_zone_grid() -> None:
    rox = xtgeo.RoxUtils(project=PRJ)
    update_petro_parameters(
        rox.project,
        facies_code_names=FACIES_CODE_NAMES,
        grid_name=GRID_MODEL_GEO_SINGLE,
        facies_real_name=FACIES_REAL_NAME,
        used_petro_dict=USED_PETRO_DICT,
        zone_name_for_single_zone_grid=ZONE_CODE_NAMES[1],
        debug_print=DEBUG_PRINT,
    )

    # Compare with reference
    petro_names = get_petro_variable_names()
    for petro_name in petro_names:
        petro_name_reference = petro_name + "_ref"
        values1 = (
            rox.project.grid_models[GRID_MODEL_GEO_SINGLE]
            .properties[petro_name]
            .get_values()
        )
        values2 = (
            rox.project.grid_models[GRID_MODEL_GEO_SINGLE]
            .properties[petro_name_reference]
            .get_values()
        )
        assert np.allclose(values1, values2)

    rox.project.save()
    rox.project.close()


@pytest.mark.skipunlessroxar
def test_update_field_parameters_multi_zone_grid() -> None:
    rox = xtgeo.RoxUtils(project=PRJ)
    update_petro_parameters(
        rox.project,
        facies_code_names=FACIES_CODE_NAMES,
        grid_name=GRID_MODEL_GEO_MULTI,
        facies_real_name=FACIES_REAL_NAME,
        used_petro_dict=USED_PETRO_DICT,
        zone_code_names=ZONE_CODE_NAMES,
        zone_param_name=ZONE_PARAM_NAME,
        debug_print=DEBUG_PRINT,
    )

    # Compare with reference
    petro_names = get_petro_variable_names()
    for petro_name in petro_names:
        petro_name_reference = petro_name + "_ref"
        values1 = (
            rox.project.grid_models[GRID_MODEL_GEO_MULTI]
            .properties[petro_name]
            .get_values()
        )
        values2 = (
            rox.project.grid_models[GRID_MODEL_GEO_MULTI]
            .properties[petro_name_reference]
            .get_values()
        )
        assert np.allclose(values1, values2)
    rox.project.save()
    rox.project.close()
