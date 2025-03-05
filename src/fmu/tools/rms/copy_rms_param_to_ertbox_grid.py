"""This module is used in FMU workflows to copy a continuous 3D parameter
from geomodel grid to ERTBOX grid and extrapolate values that are undefined
in ERTBOX grid. This functionality is used when the user wants to
use FIELD keywords for petrophysical properties in ERT in Assisted History Matching.
This module has functions shared with APS, so check APS-Facies which functions are used
when changing the code.

"""

import math
from typing import Any, Union

import numpy as np
import numpy.ma as ma

from fmu.tools import ROXAR

if ROXAR:
    try:
        import rmsapi
        from rmsapi import Direction
        from rmsapi.jobs import Job
    except ModuleNotFoundError:
        import roxar as rmsapi
        from rmsapi import Direction
        from rmsapi.jobs import Job
else:
    pass

DEBUG_OFF = 0
DEBUG_ON = 1
DEBUG_VERBOSE = 2
DEBUG_VERY_VERBOSE = 3


def copy_rms_param(params: dict) -> None:
    """Copy 3D RMS parameters between geogrid to ERTBOX grid and optionally
    extrapolate and fill all ERTBOX grid cells.
    Specify input as dictionary with all input.
    """

    # TODO: Add an example from Drogon here in the doc string how it is used
    #       in RMS python job

    # Example of use in RMS:

    # NOTE: In the example below the geo grid has 3 zones.
    #       Ertbox grid has always 1 zone.
    #       The parameter names for geogrid is the same for each zone
    #       since it is a multizone grid and zone number + parameter name
    #       uniquely identify the field parameter.
    #       The key (integer numbers) in the two dicts refer to zone number
    #       in geogrid, so for zone number 1 the Zone1_Perm and Zone1_Poro
    #       values in the Ertbox grid corresponds to the Perm and Poro values
    #       for zone number 1 in the geogrid.
    #
    #       When copying from geo to Ertbox grid there can be grid cells in Ertbox
    #       that does not correspond to any active grid cell value in the geo grid.
    #       To fill in some values for those grid cells, an extrapolation method
    #       is used. The reason for extrapolating is to avoid having undefined
    #       values in Ertbox since all cell values are used in ERT when updating
    #       field values. It is an advantage to avoid unrealistic values in ERT
    #       ensemble vector due to the calculation of updated (analysis step in ERT)
    #       ensemble vectors to avoid making linear combinations of values for grid
    #       cells that may correspond to active grid cell in geogrid in
    #       one realization, but not for another realisation due to 3D grids varying
    #       from realisation to realisation.
    #
    #       When copying from Ertbox grid to geo grid, all grid cells in specified
    #       zones in the geo grid
    #       will correspond to a value in the Ertbox grid.
    #
    # This example copies from geogrid to ertbox grid:

    # from fmu.tools.rms import copy_rms_param

    # params ={
    #     "project": project,
    #     "debug_level": DEBUG_OFF,
    #     "Mode": "from_geo_to_ertbox",
    #     "GeoGridParameters": {
    #         1: ["Perm", "Poro"],
    #         2: ["Perm", "Poro"],
    #         3: ["Perm", "Poro"],
    #     },
    #     "ErtboxParameters": {
    #         1: ["Zone1_Perm", "Zone1_Poro"],
    #         2: ["Zone2_Perm", "Zone2_Poro"],
    #         3: ["Zone3_Perm", "Zone3_Poro"],
    #     },
    #     "Conformity": {
    #         1: "TopConform",
    #         2: "Proportional",
    #         3: "BaseConform",
    #     },

    #     "GridModelName": "Geogrid",
    #     "ZoneParam": "Zone",
    #     "ERTBoxGridName": "ERTBOX",
    #     "ExtrapolationMethod": "repeat",
    #     "SaveActiveParam": True,
    #     "AddNoiseToInactive": True,
    # }
    # copy_rms_param(params)

    # This example copies from ertbox grid to geogrid:

    # from fmu.tools.rms import copy_rms_param

    # params ={
    #     "project": project,
    #     "debug_level": DEBUG_OFF,
    #     "Mode": "from_ertbox_to_geo",
    #     "GeoGridParameters": {
    #         1: ["Perm", "Poro"],
    #         2: ["Perm", "Poro"],
    #         3: ["Perm", "Poro"],
    #     },
    #     "ErtboxParameters": {
    #         1: ["Zone1_Perm", "Zone1_Poro"],
    #         2: ["Zone2_Perm", "Zone2_Poro"],
    #         3: ["Zone3_Perm", "Zone3_Poro"],
    #     },
    #     "Conformity": {
    #         1: "TopConform",
    #         2: "Proportional",
    #         3: "BaseConform",
    #     },

    #     "GridModelName": "Geogrid",
    #     "ZoneParam": "Zone",
    #     "ERTBoxGridName": "ERTBOX",
    # }
    # copy_rms_param(params)

    project = params["project"]
    required_kw_list = ["Mode"]
    check_missing_keywords_list(params, required_kw_list)
    mode = params["Mode"]
    debug_level = DEBUG_ON
    if "debug_level" in params:
        debug_level = params["debug_level"]
    if mode == "from_geo_to_ertbox":
        # The names of the parameters in ertbox is automatically set to
        # <zone_name>_<param_name_from_geomodel> since it follows
        # the standard used in APS and therefore no need to specify
        # parameter names in ertbox.
        # Check that necessary params are specified
        required_kw_list = [
            "GridModelName",
            "ERTBoxGridName",
            "ZoneParam",
            "SaveActiveParam",
            "ExtrapolationMethod",
            "GeoGridParameters",
        ]
        # Keyword 'Conformity' is required only if the grid is not created
        # by an RMS job or there exists multiple RMS jobs to build the
        # specified grid model in keyword 'GridModelName'
        check_missing_keywords_list(params, required_kw_list)
        zone_numbers = params["GeoGridParameters"].keys()
        # Check if necessary to specify grid conformity
        if check_grid_conformity(
            params["GridModelName"], zone_numbers, debug_level=debug_level
        ):
            params["Conformity_required"] = False
        else:
            params["Conformity_required"] = True
            required_kw_list = ["Conformity"]
            check_missing_keywords_list(params, required_kw_list)

        from_geogrid_to_ertbox(project, params, seed=project.seed)
    elif mode == "from_ertbox_to_geo":
        # The name both in ertbox and in geogrid is required
        # here since no standard naming convention is required here.
        # Check that necessary params are specified
        required_kw_list = [
            "GridModelName",
            "ERTBoxGridName",
            "ZoneParam",
            "ErtboxParameters",
            "GeoGridParameters",
        ]
        check_missing_keywords_list(params, required_kw_list)
        zone_numbers = params["GeoGridParameters"].keys()
        # Check if necessary to specify grid conformity
        if check_grid_conformity(
            params["GridModelName"], zone_numbers, debug_level=debug_level
        ):
            params["Conformity_required"] = False
        else:
            params["Conformity_required"] = True
            required_kw_list = ["Conformity"]
            check_missing_keywords_list(params, required_kw_list)

        from_ertbox_to_geogrid(project, params)
    else:
        raise KeyError(
            "Unknown value for keyword 'Mode'. "
            "Legal values: 'from_geo_to_ertbox' "
            "and 'from_ertbox_to_geo"
        )


def check_missing_keywords_list(params: dict, required_kw: list) -> None:
    missing_kw = []
    for kw in required_kw:
        if kw not in params or params[kw] is None:
            missing_kw.append(kw)
    if len(missing_kw) > 0:
        raise ValueError(f"Missing specification of the keywords: {missing_kw}")


def from_geogrid_to_ertbox(project: Any, params: dict, seed: int = 12345) -> None:
    """Function to copy a set of field parameters from geogrid to ertbox grid.
    A parameter in geogrid is copied to ertbox with name
    zone_name + '_' + petrovariablename.
    The input is a dictionary with specification of grid names, parameter names,
    grid layout (conformity).

    """
    # Assign user specified parameters
    grid_model_name = params["GridModelName"]
    zone_param_name = params["ZoneParam"]
    ertbox_grid_model_name = params["ERTBoxGridName"]
    method = params.get("ExtrapolationMethod", "extend_layer_mean")
    param_names_geogrid_dict = params["GeoGridParameters"]
    debug_level = int(params["debug_level"])

    conformity_dict = assign_conformity(params, debug_level=debug_level)

    # Optional parameter
    save_active_param = params.get("SaveActiveParam", False)
    # Optional parameter, Default is to add noise to inactive grid cell values
    add_noise_to_inactive = params.get("AddNoiseToInactive", True)

    # Check type and existence of geogrid parameters
    (continuous_type_param_dict, discrete_type_param_list) = check_geogrid_parameters(
        project, grid_model_name, param_names_geogrid_dict
    )

    geogrid_model, geogrid3D = get_grid_model(project, grid_model_name)
    if zone_param_name not in geogrid_model.properties:
        raise ValueError(
            f"The parameter {zone_param_name} does not exist in {grid_model_name} ."
        )
    zone_param = geogrid_model.properties[zone_param_name]
    zone_code_names = zone_param.code_names

    _, ertboxgrid3D = get_grid_model(project, ertbox_grid_model_name)

    # Check grid index origin
    geogrid_handedness = geogrid3D.grid_indexer.ijk_handedness
    ertboxgrid_handedness = ertboxgrid3D.grid_indexer.ijk_handedness

    if geogrid_handedness != ertboxgrid_handedness:
        raise ValueError(
            f"Grid model for geomodel '{grid_model_name}' and "
            f"grid model for ERTBOX grid '{ertbox_grid_model_name}'  "
            "have different grid index origin.\n"
            "Use 'Eclipse grid standard' (upper left corner) as "
            "common grid index origin (right-handed grid) in FMU projects using ERT."
        )
    if ertboxgrid_handedness != rmsapi.Direction.right:
        print("WARNING: ERTBOX grid should have 'Eclipse grid index origin'.")
        print("         Use the grid index origin job in RMS to set this.")

    zone_dict = {}
    zone_names_used = []
    if debug_level >= DEBUG_ON:
        print(
            f"- Copy RMS 3D parameters from {grid_model_name} "
            f"to {ertbox_grid_model_name} for zones:"
        )
    if debug_level >= DEBUG_ON:
        print("- Continuous parameters:")
    for zone_number, zone_name in zone_code_names.items():
        if (zone_number in param_names_geogrid_dict) and (
            zone_number in conformity_dict
        ):
            zone_dict[zone_name] = (
                zone_number,
                0,
                conformity_dict[zone_number],
                continuous_type_param_dict[zone_number],
            )
            zone_names_used.append(zone_name)
            if debug_level >= DEBUG_ON:
                print(f"  {zone_name}:  {continuous_type_param_dict[zone_number]} ")

    if debug_level >= DEBUG_ON and len(discrete_type_param_list) > 0:
        print("- Discrete parameters:")
        for p in discrete_type_param_list:
            print(f" {p} ")

    copy_from_geo_to_ertbox_grid(
        project,
        grid_model_name,
        ertbox_grid_model_name,
        zone_dict,
        method,
        discrete_param_names=discrete_type_param_list,
        debug_level=debug_level,
        save_active_param=save_active_param,
        add_noise_to_inactive=add_noise_to_inactive,
        normalize_trend=False,
        not_aps_workflow=True,
        seed=seed,
    )

    if debug_level >= DEBUG_ON:
        print(
            f"- Finished copy rms parameters from {grid_model_name} "
            f"to {ertbox_grid_model_name} "
        )


def from_ertbox_to_geogrid(project: Any, params: dict) -> None:
    """Function to copy a set of field parameters from ertbox grid into geogrid.
    A parameter in ertbox with name  zone_name + '_' + petrovariablename
    is copied into the variable with name petrovariablename in the geogrid
    and only into the zone with the correct name.
    The input is a dictionary with specification of grid names, parameter names,
    grid layout (conformity).

    """

    real_number = project.current_realisation
    # Assign user specified parameters
    grid_model_name = params["GridModelName"]
    ertbox_grid_model_name = params["ERTBoxGridName"]
    param_names_geogrid_dict = params["GeoGridParameters"]
    param_names_ertbox_dict = params["ErtboxParameters"]
    debug_level = int(params["debug_level"])

    conformity_dict = assign_conformity(params, debug_level=debug_level)

    # Create
    geogrid_model, grid3D = get_grid_model(project, grid_model_name)
    ertbox_grid_model, ertbox3D = get_grid_model(project, ertbox_grid_model_name)

    # Check grid index origin
    geogrid_handedness = grid3D.grid_indexer.ijk_handedness
    ertboxgrid_handedness = ertbox3D.grid_indexer.ijk_handedness
    if geogrid_handedness != ertboxgrid_handedness:
        raise ValueError(
            f"Grid model for geomodel '{grid_model_name}' and "
            f"grid model for ERTBOX grid '{ertbox_grid_model_name}'  "
            "have different grid index origin.\n"
            "Use 'Eclipse grid standard' (upper left corner) as "
            "common grid index origin (right-handed grid) in FMU projects using ERT."
        )
    if ertboxgrid_handedness != rmsapi.Direction.right:
        print("WARNING: ERTBOX grid should have 'Eclipse grid index origin'.")
        print("         Use the grid index origin job in RMS to set this.")

    number_of_layers_per_zone_in_geo_grid, _, _ = get_zone_layer_numbering(grid3D)
    nx, ny, nz_ertbox = ertbox3D.simbox_indexer.dimensions
    for zone_number in param_names_geogrid_dict:
        zone_index = zone_number - 1
        conformity = conformity_dict[zone_number]
        param_names_geogrid_list = param_names_geogrid_dict[zone_number]
        param_names_ertbox_list = param_names_ertbox_dict[zone_number]
        if debug_level >= DEBUG_VERBOSE:
            print(f"-- Zone number:  {zone_number}")
            print(f"-- Conformity: {conformity}  ")
            print(f"-- Copy from:  {param_names_ertbox_list}")
            print(f"-- Copy to:    {param_names_geogrid_list}")
        nz_for_zone = number_of_layers_per_zone_in_geo_grid[zone_index]
        parameter_names_geo_grid = []
        parameter_values_geo_grid = []

        for index, param_name in enumerate(param_names_ertbox_list):
            try:
                rms_property = ertbox_grid_model.properties[param_name]
            except KeyError as e:
                raise ValueError(
                    f"The parameter: {param_name} does not exist or is "
                    f"empty for grid model: {ertbox_grid_model_name}"
                ) from e
            values = rms_property.get_values(realisation=real_number)
            field_values = values.reshape(nx, ny, nz_ertbox)

            # Extract values from ertbox and assign to updated
            # field_values for RMS simbox
            field_values = extract_values_from_ertbox_grid_to_geogrid_simbox(
                field_values, conformity, nz_for_zone
            )

            # Field names and corresponding values to update the geo grid with
            param_name_geo = param_names_geogrid_list[index]
            parameter_names_geo_grid.append(param_name_geo)
            parameter_values_geo_grid.append(field_values)

        # Update geogrid. Has often multiple zones
        if debug_level >= DEBUG_VERY_VERBOSE:
            for name in parameter_names_geo_grid:
                print(
                    f"--- Update parameter {name} for zone number "
                    f"{zone_number} in {geogrid_model}"
                )

        set_continuous_3d_parameter_values_in_zone_region(
            geogrid_model,
            parameter_names_geo_grid,
            parameter_values_geo_grid,
            zone_number,
            realisation_number=project.current_realisation,
            is_shared=geogrid_model.shared,
            switch_handedness=True,
        )
    if debug_level >= DEBUG_ON:
        print(
            f"- Finished copy rms parameters from {ertbox_grid_model_name}  "
            f"to {grid_model_name}."
        )


def get_zone_layer_numbering(grid: Any) -> tuple[list[int], list[int], list[int]]:
    indexer = grid.simbox_indexer
    number_layers_per_zone = []
    start_layers_per_zone = []
    end_layers_per_zone = []
    for key in indexer.zonation:
        layer_ranges = indexer.zonation[key]
        number_layers = 0
        assert len(layer_ranges) == 1  # Required for simbox indexer
        layer_range = layer_ranges[0]
        start = layer_range[0]
        end = layer_range[-1]
        number_layers += end + 1 - start
        number_layers_per_zone.append(number_layers)
        start_layers_per_zone.append(start)
        end_layers_per_zone.append(end)
    return number_layers_per_zone, start_layers_per_zone, end_layers_per_zone


def get_grid_model(project: Any, grid_model_name: str) -> tuple[Any, Any]:
    """
    For given grid model name, return grid_model and grid objects.
    """
    if grid_model_name not in project.grid_models:
        raise ValueError(f"Grid model {grid_model_name} does not exist.")
    grid_model = project.grid_models[grid_model_name]
    real_number = project.current_realisation
    if grid_model.is_empty(realisation=real_number):
        raise ValueError(f"Grid model {grid_model_name} is empty. ")
    grid = grid_model.get_grid(realisation=real_number)
    return grid_model, grid


def check_and_get_grid_dimensions(
    geogrid: Any, ertboxgrid: Any, geo_grid_model_name: str, ertbox_grid_model_name: str
) -> tuple[int, int, int, int]:
    """
    For a given geogrid and ertbox grid return grid dimensions.
    """
    geogrid_dims = geogrid.simbox_indexer.dimensions
    ertbox_dims = ertboxgrid.simbox_indexer.dimensions
    nx = geogrid_dims[0]
    ny = geogrid_dims[1]
    nz = geogrid_dims[2]
    if ertbox_dims[0] != nx or ertbox_dims[1] != ny:
        raise ValueError(
            f"Grid dimensions nx and ny for geogrid {geo_grid_model_name} "
            f"and ertbox grid {ertbox_grid_model_name} must be equal."
        )
    nz_ertbox = ertbox_dims[2]
    return nx, ny, nz, nz_ertbox


def get_grid_indices(
    geogrid, nx: int, ny: int, start_layer: int, end_layer: int
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    start = (0, 0, start_layer)
    end = (nx, ny, end_layer + 1)
    indexer = geogrid.simbox_indexer
    try:
        ijk_handedness = indexer.ijk_handedness
    except AttributeError:
        ijk_handedness = indexer.handedness

    zone_cell_numbers = geogrid.simbox_indexer.get_cell_numbers_in_range(start, end)
    defined_cell_indices = geogrid.simbox_indexer.get_indices(zone_cell_numbers)
    if ijk_handedness == Direction.right:
        i_indices = defined_cell_indices[:, 0]
        j_indices = -defined_cell_indices[:, 1] + ny - 1
    else:
        i_indices = defined_cell_indices[:, 0]
        j_indices = defined_cell_indices[:, 1]
    k_indices = defined_cell_indices[:, 2]
    return i_indices, j_indices, k_indices, zone_cell_numbers


def active_params_in_zone(
    geo_i_indices: np.ndarray,
    geo_j_indices: np.ndarray,
    geo_k_indices: np.ndarray,
    geo_nx: int,
    geo_ny: int,
    geo_nz: int,
    nz_ertbox: int,
    conformity: str,
    number_layers: int,
    start_layer: int,
    end_layer: int,
) -> np.ndarray:
    # Define active parameter for geogrid
    active_3d = np.zeros((geo_nx, geo_ny, geo_nz), dtype=np.int32)
    active_3d[geo_i_indices, geo_j_indices, geo_k_indices] = 1

    # Initially mask all values for ertbox parameter
    ertbox_active_3d = np.zeros((geo_nx, geo_ny, nz_ertbox), dtype=np.uint8)
    ertbox_active_3d = extract_active_values_from_geogrid_simbox_to_ertbox_grid(
        ertbox_active_3d, active_3d, number_layers, start_layer, end_layer, conformity
    )

    return np.reshape(ertbox_active_3d, geo_nx * geo_ny * nz_ertbox)


def ertbox_active_param_to_rms(
    prefix: str,
    real_number: int,
    zone_name: str,
    ertbox_grid_model: Any,
    ertbox_active,
    debug_level: int = DEBUG_OFF,
) -> Any:
    # Create and save a parameter for grid cells in ERTBOX
    # corresponding to active cells from geomodel for current geomodel zone
    active_param_name = prefix + zone_name + "_active"
    if active_param_name not in ertbox_grid_model.properties:
        ertbox_active_param = ertbox_grid_model.properties.create(
            active_param_name,
            property_type=rmsapi.GridPropertyType.discrete,
            data_type=np.uint8,
        )
    else:
        ertbox_active_param = ertbox_grid_model.properties[active_param_name]

    if debug_level >= DEBUG_VERBOSE:
        print(f"-- Update parameter: {active_param_name}")
    ertbox_active_param.set_values(ertbox_active, real_number)
    return ertbox_active_param


def define_active_parameters_in_ertbox(
    project: Any,
    geo_grid_model_name: str,
    ertbox_grid_model_name: str,
    zone_dict: dict,
    debug_level: int = DEBUG_OFF,
    not_aps_workflow=True,
) -> None:
    """
    zone_dict[zone_name] = (zone_number, region_number, conformity, param_name_list)
    """
    real_number = project.current_realisation
    _, geogrid = get_grid_model(project, geo_grid_model_name)
    ertbox_grid_model, ertboxgrid = get_grid_model(project, ertbox_grid_model_name)

    # Both ERTBOX grid and geogrid should have same nx, ny dimensions
    # nz is here the geogrid number of layers for all zones
    # nz_ertbox is number of layers in total in ERTBOX grid
    nx, ny, nz, nz_ertbox = check_and_get_grid_dimensions(
        geogrid, ertboxgrid, geo_grid_model_name, ertbox_grid_model_name
    )

    number_layers_per_zone, start_layers_per_zone, end_layers_per_zone = (
        get_zone_layer_numbering(geogrid)
    )

    # Get zone_name and parameter names from model specification
    for zone_name, zone_item in zone_dict.items():
        zone_number, _, conformity, _ = zone_item
        zone_index = zone_number - 1
        number_layers = number_layers_per_zone[zone_index]
        start_layer = start_layers_per_zone[zone_index]
        end_layer = end_layers_per_zone[zone_index]
        if number_layers > nz_ertbox:
            raise ValueError(
                f"Number of layers of {ertbox_grid_model_name} ({nz_ertbox}) "
                "is less than number of layers in "
                f"{geo_grid_model_name} ({number_layers})"
                f"for zone {zone_name}."
            )
        if debug_level >= DEBUG_VERY_VERBOSE:
            print(f"--- zone name: {zone_name}")
            print(f"--- number_layers: {number_layers}")
            print(f"--- start_layer: {start_layer}  end_layer: {end_layer}")

        i_indices, j_indices, k_indices, _ = get_grid_indices(
            geogrid, nx, ny, start_layer, end_layer
        )

        prefix = "aps_"
        if not_aps_workflow:
            prefix = ""

        # The active cells as array
        ertbox_active = active_params_in_zone(
            i_indices,
            j_indices,
            k_indices,
            nx,
            ny,
            nz,
            nz_ertbox,
            conformity,
            number_layers,
            start_layer,
            end_layer,
        )
        # Active stored in RMS parameter
        ertbox_active_param_to_rms(
            prefix,
            real_number,
            zone_name,
            ertbox_grid_model,
            ertbox_active,
            debug_level=debug_level,
        )


def get_param_values(
    geogrid_model: Any,
    param_name: str,
    real_number: int,
) -> np.ndarray:
    if param_name not in geogrid_model.properties:
        raise ValueError(
            f"The 3D parameter {param_name} does not exist "
            f"in grid model {geogrid_model.name}"
        )

    param = geogrid_model.properties[param_name]
    if param.is_empty(realisation=real_number):
        raise ValueError(
            f"Grid parameter {param_name} for {geogrid_model.name} is empty.\n"
        )
    return param.get_values(realisation=real_number)


def copy_parameters_for_zone(
    zone_name: str,
    geogrid_model: Any,
    ertbox_model_name: str,
    param_name: str,
    i_indices: np.ndarray,
    j_indices: np.ndarray,
    k_indices: np.ndarray,
    zone_cell_numbers: np.ndarray,
    conformity: str,
    nx: int,
    ny: int,
    nz: int,
    nz_ertbox: int,
    number_layers,
    start_layer: int,
    end_layer: int,
    real_number: int,
    param_type: str = "float",
    debug_level: int = DEBUG_OFF,
) -> np.ma.MaskedArray[Any, Any]:
    """
    Description:
    For specified zone name a parameter from the geomodel is copied
    to the ertbox grid. The i,j,k indices coming from the geogrid
    defines the (i,j,k) indices with actively used values.
    The zone_cell_numbers define active cell numbers in geomodel.
    The mapping from geogrid to ertbox grid is defined by the
    specified geogrid conformity and the layer interval.
    """
    param_values_active = get_param_values(geogrid_model, param_name, real_number)

    if debug_level >= DEBUG_VERBOSE:
        print(f"-- Zone: {zone_name} Parameter:{param_name} ")

    # Mask all values for geogrid parameter except the active values within the zone
    if param_type == "float":
        param_values_3d_all = ma.masked_all((nx, ny, nz), dtype=np.float32)
    elif param_type == "int":
        param_values_3d_all = ma.masked_all((nx, ny, nz), dtype=np.uint16)
    else:
        raise ValueError("Parameter type must be 'float' or 'int' ")
    param_values_3d_all[i_indices, j_indices, k_indices] = param_values_active[
        zone_cell_numbers
    ]

    # Initially mask all values for ertbox parameter
    if param_type == "float":
        ertbox_values_3d_masked = ma.masked_all((nx, ny, nz_ertbox), dtype=np.float32)
    else:
        ertbox_values_3d_masked = ma.masked_all((nx, ny, nz_ertbox), dtype=np.uint16)

    if debug_level >= DEBUG_VERY_VERBOSE:
        print(
            f"--- Parameter {param_name}  for zone: {zone_name} "
            f"is copied to {ertbox_model_name}."
        )

    # The RMS simbox layers (num_layers) are copied into ertbox grid
    # at top if grid layout is top conform or proportional and
    # at the bottom if grid layout is base conform.
    # Must be consistent with export_fields_to_disk.py
    return extract_values_from_geogrid_simbox_to_ertbox_grid(
        ertbox_values_3d_masked,
        param_values_3d_all,
        number_layers,
        start_layer,
        end_layer,
        conformity,
    )


def update_ertbox_properties_int(
    prefix: str,
    zone_name: str,
    param_name: str,
    ertbox_grid_model: Any,
    ertbox_values,
    real_number: int,
    debug_level: int = DEBUG_OFF,
) -> None:
    # Create /Update ertbox properties in RMS
    full_param_name = prefix + zone_name + "_" + param_name
    if full_param_name in ertbox_grid_model.properties:
        ertbox_param = ertbox_grid_model.properties[full_param_name]
    else:
        ertbox_param = ertbox_grid_model.properties.create(
            full_param_name,
            property_type=rmsapi.GridPropertyType.discrete,
            data_type=np.uint16,
        )
    ertbox_param.set_values(ertbox_values, real_number)

    if debug_level >= DEBUG_VERBOSE:
        print(f"-- Update parameter: {full_param_name}")


def update_ertbox_properties_float(
    prefix: str,
    zone_name: str,
    param_name: str,
    ertbox_grid_model: Any,
    ertbox_values: np.ndarray,
    real_number: int,
    normalize_trend: bool = False,
    debug_level: int = DEBUG_OFF,
) -> None:
    # Create /Update ertbox properties in RMS
    full_param_name = prefix + zone_name + "_" + param_name
    if full_param_name in ertbox_grid_model.properties:
        ertbox_param = ertbox_grid_model.properties[full_param_name]
    else:
        ertbox_param = ertbox_grid_model.properties.create(
            full_param_name,
            property_type=rmsapi.GridPropertyType.continuous,
            data_type=np.float32,
        )
    ertbox_param.set_values(ertbox_values, real_number)

    if debug_level >= DEBUG_VERBOSE:
        if normalize_trend:
            print(f"-- Update parameter (normalized): {full_param_name}")
        else:
            print(f"-- Update parameter: {full_param_name}")


def assign_undefined_constant(
    ertbox_values_3d_masked: np.ma.MaskedArray[Any, Any],
    value: float,
    debug_level: int = DEBUG_OFF,
) -> np.ma.MaskedArray:
    if debug_level >= DEBUG_VERY_VERBOSE:
        print(f"--- All inactive values set to:{value}")
    return ertbox_values_3d_masked.filled(value)


def fill_remaining_masked_values_within_colum(
    column_values_masked: np.ndarray, nz_ertbox: int
) -> np.ndarray:
    if not ma.is_masked(column_values_masked):
        return column_values_masked
    index_array = np.arange(nz_ertbox)
    work_array = column_values_masked.copy()
    list_of_unmasked_intervals = ma.notmasked_contiguous(column_values_masked)
    current_slice = list_of_unmasked_intervals[0]
    current_index_interval = index_array[current_slice]
    last_index = current_index_interval[-1]
    v1 = work_array[last_index]
    for number in range(1, len(list_of_unmasked_intervals)):
        prev_last_index = last_index
        current_slice = list_of_unmasked_intervals[number]
        indices = index_array[current_slice]
        first_index = indices[0]
        last_index = indices[-1]
        n = first_index - prev_last_index + 1
        v0 = work_array[prev_last_index]
        v1 = work_array[first_index]
        # Linear interpolate and assign to masked values
        n = first_index - prev_last_index
        indx = 1
        for k in range(prev_last_index + 1, first_index):
            column_values_masked[k] = v0 + (v1 - v0) * indx / n
            indx += 1

    return column_values_masked


def assign_undefined_vertical(
    method: str,
    nx: int,
    ny: int,
    nz_ertbox: int,
    ertbox_values_3d_masked: np.ma.MaskedArray[Any, Any],
    fill_value: float,
) -> np.ma.MaskedArray[Any, Any]:
    k_indices = np.arange(nz_ertbox)
    for i in range(nx):
        for j in range(ny):
            column_values_masked = ertbox_values_3d_masked[i, j, :]
            defined_k_indices = k_indices[~column_values_masked.mask]

            if len(defined_k_indices) > 0:
                top_k = defined_k_indices[0]
                bottom_k = defined_k_indices[-1]
                top_value = column_values_masked[top_k]
                bottom_value = column_values_masked[bottom_k]
                undefined_k_indices_top = np.arange(top_k)
                undefined_k_indices_bottom = np.arange(bottom_k + 1, nz_ertbox)
                if method in ["extend", "extend_layer_mean"]:
                    column_values_masked[undefined_k_indices_top] = top_value
                    column_values_masked[undefined_k_indices_bottom] = bottom_value
                    column_values_masked = fill_remaining_masked_values_within_colum(
                        column_values_masked, nz_ertbox
                    )
                    ertbox_values_3d_masked[i, j, :] = column_values_masked

                elif method in ["repeat", "repeat_layer_mean"]:
                    if len(undefined_k_indices_top) > 0:
                        m = len(undefined_k_indices_top)
                        n = len(defined_k_indices)
                        values_for_undefined = column_values_masked[
                            undefined_k_indices_top
                        ]
                        values_for_undefined[:] = bottom_value
                        if m > n:
                            values_for_undefined[:n] = column_values_masked[
                                defined_k_indices
                            ]
                        elif m < n:
                            tmp = column_values_masked[defined_k_indices]
                            values_for_undefined = tmp[:m]
                        else:
                            values_for_undefined = column_values_masked[
                                defined_k_indices
                            ]

                        reverse_values_for_undefined = np.flip(
                            values_for_undefined, axis=0
                        )
                        column_values_masked[undefined_k_indices_top] = (
                            reverse_values_for_undefined
                        )
                    if len(undefined_k_indices_bottom) > 0:
                        m = len(undefined_k_indices_bottom)
                        n = len(defined_k_indices)
                        values_for_undefined = column_values_masked[
                            undefined_k_indices_bottom
                        ].copy()
                        values_for_undefined[:] = top_value
                        if m > n:
                            values_for_undefined[(m - n) :] = column_values_masked[
                                defined_k_indices
                            ]
                        elif m < n:
                            tmp = column_values_masked[defined_k_indices]
                            values_for_undefined = tmp[(n - m) :]
                        else:
                            values_for_undefined = column_values_masked[
                                defined_k_indices
                            ]

                        reverse_values_for_undefined = np.flip(
                            values_for_undefined, axis=0
                        )
                        column_values_masked[undefined_k_indices_bottom] = (
                            reverse_values_for_undefined
                        )

                    column_values_masked = fill_remaining_masked_values_within_colum(
                        column_values_masked, nz_ertbox
                    )
                    ertbox_values_3d_masked[i, j, :] = column_values_masked

    return ertbox_values_3d_masked.filled(fill_value)


def assign_undefined_lateral(
    nz_ertbox: int,
    ertbox_values_3d_masked: np.ma.MaskedArray[Any, Any],
) -> np.ma.MaskedArray[Any, Any]:
    for k in range(nz_ertbox):
        layer_values = ertbox_values_3d_masked[:, :, k]
        if layer_values.count() > 0:
            mean = ma.mean(ertbox_values_3d_masked[:, :, k])
            filled_layer_values = layer_values.filled(mean)
            ertbox_values_3d_masked[:, :, k] = filled_layer_values
    return ertbox_values_3d_masked


def extrapolate_values_for_zone(
    ertbox_values_3d_masked: np.ma.MaskedArray[Any, Any],
    extrapolation_method: str,
    nx: int,
    ny: int,
    nz_ertbox: int,
    debug_level: int = DEBUG_OFF,
    seed: int = 12345,
    add_noise_to_inactive: bool = False,
) -> np.ndarray:
    """
    Description:
    Here all inactive cells in ertbox are filled with values using
    some chosen extrapolation method. Returns a flatten 1D array
    """

    if debug_level >= DEBUG_VERBOSE:
        if extrapolation_method is not None:
            print(
                "-- Extrapolate parameter using option for undefined grid cells in "
                f"ERTBOX: {extrapolation_method}"
            )
        if add_noise_to_inactive:
            print(
                "-- Add random noise to undefined grid cells in ERTBOX on top "
                "of the extrapolated values"
            )

    if add_noise_to_inactive:
        # The undefined grid cells before any of them are filled
        undefined_grid_cells = np.copy(ertbox_values_3d_masked.mask)

    vertical_methods = ("extend", "repeat")

    vertical_horizontal_methods = ["extend_layer_mean", "repeat_layer_mean"]

    if extrapolation_method in vertical_horizontal_methods:
        ertbox_values_3d_masked = assign_undefined_lateral(
            nz_ertbox, ertbox_values_3d_masked
        )

    if extrapolation_method == "zero":
        ertbox_values_3d = assign_undefined_constant(
            ertbox_values_3d_masked, 0.0, debug_level
        )

    elif extrapolation_method == "mean":
        mean = ma.mean(ertbox_values_3d_masked)
        ertbox_values_3d = assign_undefined_constant(
            ertbox_values_3d_masked, mean, debug_level
        )

    elif (extrapolation_method in vertical_methods) or (
        extrapolation_method in vertical_horizontal_methods
    ):
        mean = ma.mean(ertbox_values_3d_masked)
        ertbox_values_3d = assign_undefined_vertical(
            extrapolation_method, nx, ny, nz_ertbox, ertbox_values_3d_masked, mean
        )

    else:
        raise ValueError(
            f"Extrapolation method:{extrapolation_method} is not implemented."
        )

    # Add random noise with low std dev to all values for undefined
    # grid cells that have been filled in the above extrapolation
    # This is to avoid creating ensemble of realizations where undefined grid cells
    # that are filled with extrapolated values get 0 standard deviation since
    # 0 standard deviation per today trigger errors in ERT with adaptive localisation.
    if add_noise_to_inactive:
        ertbox_values_3d = add_noise_to_undefined_grid_cell_values(
            ertbox_values_3d, undefined_grid_cells, seed
        )

    return np.reshape(ertbox_values_3d, nx * ny * nz_ertbox)


def add_noise_to_undefined_grid_cell_values(
    ertbox_values_3d: np.ma.MaskedArray[Any, Any],
    undefined_grid_cells: np.ndarray,
    seed: int,
    max_relative_noise: float = 0.05,
) -> np.ma.MaskedArray[Any, Any]:
    mean = np.mean(ertbox_values_3d)
    low = 0.0
    high = math.fabs(mean) * max_relative_noise
    # To avoid making negative values for positive random numbers
    # (e.g. from lognormal distribution), add a small positive noise
    rng = np.random.default_rng(seed)
    noise = rng.uniform(low, high, size=ertbox_values_3d.shape)
    ertbox_values_3d[undefined_grid_cells] = (
        ertbox_values_3d[undefined_grid_cells] + noise[undefined_grid_cells]
    )
    return ertbox_values_3d


def copy_from_geo_to_ertbox_grid(
    project: Any,
    geo_grid_model_name: str,
    ertbox_grid_model_name: str,
    zone_dict: dict,
    extrapolation_method: str,
    discrete_param_names: list = [],
    debug_level: int = DEBUG_OFF,
    save_active_param: bool = False,
    add_noise_to_inactive: bool = False,
    normalize_trend: bool = False,
    not_aps_workflow: bool = False,
    seed: int = 12345,
) -> None:
    """Copy grid parameters from geomodel grid to ertbox grid
    and both continuous and discrete parameters can be copied.
    Continuous parameters can be extrapolated in ertbox grid model.

    Input:
        geogrid name,
        ertbox grid name,
        parameters to be copied per zone (zone_dict) defined by
        zone_dict[zone_name] = (zone_number, region_number, conformity, param_name_list)
        extrapolation method for continuous 3D parameters,

    Optional input:
        list of discrete parameter names to be copied,
        debug_level (0 for off, 1 or larger for on),
        save_active_param (False/True) if this should be calculated,
        add_noise_to_inactive (False/True)  if random noise with small variance
        is to be added to grid cell values in ERTBOX grid that are extrapolated,
        normalize_trend (False/True) is only relevant when used in APS,
        not_aps_workflow (False/True) turn on prefix 'aps' if False else no prefix
        for 3D parameters in ERTBOX grid,
        seed is input to random generator to draw the noise values
        if add_noise_to_inactive is True.

    Extrapolation alternative method:

        zero -  where all undefined cells get 0 as value

        mean - where all undefined cells get mean value of defined cell values

        extend_layer_mean - where all undefined values in a layer is replaced by the
                            layer average. For undefined grid cells above or below the
                            layers having some defined values, the upper most defined
                            cell value is copied to all undefined cell values above
                            this cell for each cell column and bottom most defined
                            cell value is copied to all undefined cell values below
                            this cell for each cell column.

        repeat_layer_mean - where all undefined values in a layer is replaced by the
                            layer average. For undefined cells above the uppermost
                            active cell are assigned the values of the active cells
                            in the same column but in reverse order to avoid
                            discontinuity at the border between the initially active
                            and undefined cell values. If the number of active cells
                            in a column is less than the undefined cells above the
                            uppermost active cell, they will be assigned a constant
                            value in the same way as option EXTEND_LAYER_MEAN.
                            The same procedure is used to fill in inactive cell
                            values below lowermost active cell.

        repeat -            where all undefined values in a column is defined by
                            repeating values upwards and downwards from the defined
                            value at the border between defined and undefined grid
                            cells. The repeat is taken in reverse order
                            (like making a mirror copy of the defined values upwards
                            and downwards from the defined to the undefined grid cells.)

        extend -            where all undefined values in a column is defined by
                            repeating values upwards and downwards from the defined
                            value at the border between defined and undefined grid
                            cells. The uppermost defined value is copied to all
                            undefined grid cells above and the lowermost defined
                            value is copied to all undefined grid cells below.

    """
    real_number = project.current_realisation
    geogrid_model, geogrid = get_grid_model(project, geo_grid_model_name)
    ertbox_grid_model, ertboxgrid = get_grid_model(project, ertbox_grid_model_name)

    # Both ERTBOX grid and geogrid should have same nx, ny dimensions
    # nz is here the geogrid number of layers for all zones
    # nz_ertbox is number of layers in total in ERTBOX grid
    nx, ny, nz, nz_ertbox = check_and_get_grid_dimensions(
        geogrid, ertboxgrid, geo_grid_model_name, ertbox_grid_model_name
    )

    number_layers_per_zone, start_layers_per_zone, end_layers_per_zone = (
        get_zone_layer_numbering(geogrid)
    )

    # Get parameter names from model specification
    for zone_name, zone_item in zone_dict.items():
        zone_number, _, conformity, param_name_list = zone_item
        zone_index = zone_number - 1
        number_layers = number_layers_per_zone[zone_index]
        start_layer = start_layers_per_zone[zone_index]
        end_layer = end_layers_per_zone[zone_index]
        if number_layers > nz_ertbox:
            raise ValueError(
                f"Number of layers of {ertbox_grid_model_name} ({nz_ertbox}) "
                f"is less than number of layers in "
                f"{geo_grid_model_name} ({number_layers})"
                f"for zone {zone_name}."
            )
        if debug_level >= DEBUG_VERY_VERBOSE:
            print(f"--- zone name: {zone_name}")
            print(f"--- number_layers: {number_layers}")
            print(f"--- start_layer: {start_layer}  end_layer: {end_layer}")

        i_indices, j_indices, k_indices, zone_cell_numbers = get_grid_indices(
            geogrid, nx, ny, start_layer, end_layer
        )

        prefix = "aps_"
        if not_aps_workflow:
            prefix = ""

        # The active cells as array
        ertbox_active = active_params_in_zone(
            i_indices,
            j_indices,
            k_indices,
            nx,
            ny,
            nz,
            nz_ertbox,
            conformity,
            number_layers,
            start_layer,
            end_layer,
        )
        # Active stored in RMS parameter
        if save_active_param:
            ertbox_active_param_to_rms(
                prefix,
                real_number,
                zone_name,
                ertbox_grid_model,
                ertbox_active,
                debug_level,
            )

        for param_name in discrete_param_names:
            ertbox_values_3d_masked = copy_parameters_for_zone(
                zone_name,
                geogrid_model,
                ertbox_grid_model_name,
                param_name,
                i_indices,
                j_indices,
                k_indices,
                zone_cell_numbers,
                conformity,
                nx,
                ny,
                nz,
                nz_ertbox,
                number_layers,
                start_layer,
                end_layer,
                real_number,
                param_type="int",
                debug_level=debug_level,
            )
            # Inactive cells filled with -1
            ertbox_values_3d = ertbox_values_3d_masked.filled(0)
            ertbox_values = np.reshape(ertbox_values_3d, nx * ny * nz_ertbox)
            update_ertbox_properties_int(
                prefix,
                zone_name,
                param_name,
                ertbox_grid_model,
                ertbox_values,
                real_number,
                debug_level=debug_level,
            )

        for param_name in param_name_list:
            # Copy parameter for give zone from geogrid to ertbox grid
            ertbox_values_3d_masked = copy_parameters_for_zone(
                zone_name,
                geogrid_model,
                ertbox_grid_model_name,
                param_name,
                i_indices,
                j_indices,
                k_indices,
                zone_cell_numbers,
                conformity,
                nx,
                ny,
                nz,
                nz_ertbox,
                number_layers,
                start_layer,
                end_layer,
                real_number,
                param_type="float",
                debug_level=debug_level,
            )

            # Fill values for all inactive cells in ertbox
            ertbox_values = extrapolate_values_for_zone(
                ertbox_values_3d_masked,
                extrapolation_method,
                nx,
                ny,
                nz_ertbox,
                debug_level,
                seed=seed,
                add_noise_to_inactive=add_noise_to_inactive,
            )

            # Normalize values to be between 0 and 1 within this zone
            if normalize_trend:
                if debug_level >= DEBUG_VERBOSE:
                    print(f"-- Normalize parameter: {param_name} ")
                selected_values = ertbox_values[ertbox_active == 1]
                minval = selected_values.min()
                maxval = selected_values.max()
                minmax_diff = maxval - minval
                if minmax_diff > 0.000001:
                    # All values including the inactive cells are rescaled
                    # All active cell values will be between 0 and 1
                    ertbox_values = (ertbox_values - minval) / (minmax_diff)

                    # All values for inactive cells should also be >= 0
                    ertbox_values[ertbox_values < 0.0] = 0.0
                else:
                    # Constant trend equal to 0 is set if trend is constant
                    ertbox_values[:] = 0.0

            # Create /Update ertbox properties in RMS
            update_ertbox_properties_float(
                prefix,
                zone_name,
                param_name,
                ertbox_grid_model,
                ertbox_values,
                real_number,
                normalize_trend=normalize_trend,
                debug_level=debug_level,
            )


def check_geogrid_parameters(
    project: Any, grid_model_name: str, param_names_geogrid_dict: dict
) -> tuple[dict, list]:
    if grid_model_name in project.grid_models:
        grid_model = project.grid_models[grid_model_name]
    else:
        raise ValueError(f"Grid model: {grid_model_name} does not exists.")
    if grid_model.is_empty(project.current_realisation):
        raise ValueError(f"Grid model: {grid_model.name} is empty.")
    properties = grid_model.properties
    continuous_type_param_dict = {}
    discrete_type_param_list = []
    for zone_number, property_names in param_names_geogrid_dict.items():
        continuous_type_param_list = []
        for pname in property_names:
            if pname not in properties:
                raise ValueError(
                    f"Grid parameter: {pname} "
                    f"does not exists for grid model: {grid_model.name}  "
                )

            prop = properties[pname]
            if prop.is_empty(project.current_realisation):
                raise ValueError(
                    f"Grid property: {pname} is empty for grid model: {grid_model.name}"
                )
            if prop.type == rmsapi.GridPropertyType.continuous:
                continuous_type_param_list.append(pname)
            elif prop.type == rmsapi.GridPropertyType.discrete:
                if pname not in discrete_type_param_list:
                    discrete_type_param_list.append(pname)
            else:
                raise ValueError(
                    f"Grid parameter: {pname} for grid model: {grid_model.name} "
                    f"has type: {prop.type} which is not implemented in this script."
                )

        continuous_type_param_dict[zone_number] = continuous_type_param_list
    return continuous_type_param_dict, discrete_type_param_list


def get_layer_range(
    indexer: Any, zone_number: int, fmu_mode: bool = False
) -> tuple[int, int]:
    _, _, nz = indexer.dimensions
    if fmu_mode:
        if len(indexer.zonation) == 1:
            layer_ranges = indexer.zonation[0]
        else:
            raise ValueError(
                "While in FMU / ERT mode, the grid must have EXACTLY 1 zone"
            )
    else:
        layer_ranges = indexer.zonation[
            zone_number - 1
        ]  # Zonation is 0-indexed, while zone numbers are 1-indexed
    start_layer = nz
    end_layer = 0
    for layer_range in layer_ranges:
        if start_layer > layer_range.start:
            start_layer = layer_range.start
        if end_layer < layer_range.stop:
            end_layer = layer_range.stop
    return end_layer, start_layer


def define_active_cell_indices(
    indexer: Any,
    cell_numbers: np.ndarray,
    ijk_handedness: Any,
    use_left_handed_grid_indexing: bool,
    grid_model_name: str,
    debug_level: int = DEBUG_OFF,
    switch_handedness_for_parameters: bool = False,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    _, ny, _ = indexer.dimensions
    defined_cell_indices = indexer.get_indices(cell_numbers)
    switch_handedness = switch_handedness_for_parameters
    if (ijk_handedness == Direction.right) and use_left_handed_grid_indexing:
        switch_handedness = True
    if switch_handedness:
        if debug_level >= DEBUG_VERBOSE:
            print(
                f"-- Grid handedness for {grid_model_name} : "
                f"{ijk_handedness}.  Switch handedness."
            )
        i_indices = defined_cell_indices[:, 0]
        j_indices = -defined_cell_indices[:, 1] + ny - 1
    else:
        i_indices = defined_cell_indices[:, 0]
        j_indices = defined_cell_indices[:, 1]
    k_indices = defined_cell_indices[:, 2]
    return i_indices, j_indices, k_indices


def set_continuous_3d_parameter_values_in_zone_region(
    grid_model: Any,
    parameter_names: list[str],
    input_values_for_zones: list[np.ndarray],
    zone_number: int,
    region_number: int = 0,
    region_parameter_name: str = "",
    realisation_number: int = 0,
    is_shared: bool = True,
    debug_level: int = DEBUG_OFF,
    fmu_mode: bool = False,
    use_left_handed_grid_indexing: bool = False,
    switch_handedness: bool = False,
) -> bool:
    """Set 3D parameter with values for specified grid model for
       specified zone (and region)

    Input:

           grid_model:
                Grid model object

           parameter_names:
                List of names of 3D parameter to update.

           input_values_for_zones:
                A list of numpy 3D arrays.
                They corresponds to the parameter names in parameter_names.
                The size of the numpy input arrays are (nx,ny,nLayers) where
                nx, ny must match the gridModels 3D grid size for the simulation
                box grid and nLayers must match the number of layers for the
                zone in simulationx box. Note that since nx, ny are the simulation
                box grid size, they can be larger than the number of cells reported
                for the grid in reverse faulted grids. The grid values must be of type
                numpy.float32. Only the grid cells belonging to the specified zone
                are updated, and error is raised if the number of grid cells for
                the zone doesn't match the size of the input array.

           zone_number:
                The zone number (counted from 1 in the input)

           regionNumber:
                The region number for the grid cells to be updated.

           region_parameter_name:
                The name of the 3D grid parameter containing a discrete
                3D parameter with region numbers

           realisation_number:
                Realisation number counted from 0 for the parameter to get.

           is_shared:
                Is set to true or false if the parameter is to be set
                to shared or non-shared.

           debug_level: 0 is off, 1 or larger is on for additional output to screen

    """

    # Check if specified grid model exists and is not empty
    if grid_model.is_empty(realisation_number):
        print(
            f"Specified grid model: {grid_model.name} "
            f"is empty for realisation {realisation_number + 1}"
        )
        return False

    # Check if the parameter is defined and create new if not existing
    grid = grid_model.get_grid(realisation_number)

    # Find grid layers for the zone
    indexer = grid.simbox_indexer
    try:
        ijk_handedness = indexer.ijk_handedness
    except AttributeError:
        ijk_handedness = indexer.handedness

    nx, ny, nz = indexer.dimensions
    end_layer, start_layer = get_layer_range(indexer, zone_number, fmu_mode)
    start = (0, 0, start_layer)
    end = (nx, ny, end_layer)
    zone_cell_numbers = indexer.get_cell_numbers_in_range(start, end)

    num_layers = end_layer - start_layer
    # All input data vectors are from the same zone and has the same size
    nx_in, ny_in, nz_in = input_values_for_zones[0].shape
    if nx != nx_in or ny != ny_in or num_layers > nz_in:
        raise IOError(
            "Input array with values has different dimensions than the grid model:\n"
            f"Grid model nx: {nx}  Input array nx: {nx_in}\n"
            f"Grid model ny: {ny}  Input array ny: {ny_in}\n"
            f"Grid model nLayers for zone {zone_number} is: "
            f"{num_layers}    Input array nz: {nz_in}"
        )
    use_regions = False
    if region_parameter_name is None or len(region_parameter_name) == 0 or fmu_mode:
        i_indices, j_indices, k_indices = define_active_cell_indices(
            indexer,
            zone_cell_numbers,
            ijk_handedness,
            use_left_handed_grid_indexing,
            grid_model.name,
            debug_level=DEBUG_OFF,
            switch_handedness_for_parameters=switch_handedness,
        )

    else:
        # Get region parameter values
        if region_parameter_name in grid_model.properties:
            p = grid_model.properties[region_parameter_name]
            if not p.is_empty(realisation_number):
                region_param_values = p.get_values(realisation_number)
        else:
            raise ValueError(
                f"Parameter {region_parameter_name} "
                f"does not exist or is empty in grid model {grid_model.name}."
            )
        region_param_values_in_zone = region_param_values[zone_cell_numbers]
        zone_region_cell_numbers = zone_cell_numbers[
            region_param_values_in_zone == region_number
        ]
        i_indices, j_indices, k_indices = define_active_cell_indices(
            indexer,
            zone_region_cell_numbers,
            ijk_handedness,
            use_left_handed_grid_indexing,
            grid_model.name,
            debug_level=DEBUG_OFF,
            switch_handedness_for_parameters=switch_handedness,
        )
        use_regions = True

    # Loop over all parameter names
    for param_index in range(len(parameter_names)):
        parameter_name = parameter_names[param_index]
        input_values_for_zone = input_values_for_zones[param_index]
        if parameter_name in grid_model.properties:
            property_param = grid_model.properties[parameter_name]
        else:
            # Create new parameter
            property_param = grid_model.properties.create(
                parameter_name, rmsapi.GridPropertyType.continuous, np.float32
            )
            property_param.set_shared(is_shared, realisation_number)
            if debug_level >= DEBUG_VERY_VERBOSE:
                print(f"--- Create specified RMS parameter: {parameter_name}")
                if is_shared:
                    print("--- Set parameter to shared.")
                else:
                    print("--- Set parameter to non-shared.")

        assert property_param is not None
        if property_param.is_empty(realisation_number):
            # Initialize to 0 if empty
            v = grid.generate_values(np.float32)
            property_param.set_values(v, realisation_number)

        # Get current values
        current_values = property_param.get_values(realisation_number)

        # Assign values from input array into the 3D grid array
        # Note that input array is of dimension (nx,ny,nLayers)
        # where nLayers is the number of layers of the input grid
        # These layers must correspond to layer from start_layer
        # until but not including end_layer in the full 3D grid.

        # Create a 3D array for all cells in the grid including inactive cells
        # Since the cell numbers, and the indices all are based on the same range,
        # it is possible to use numpy vectorization to copy
        new_values = np.zeros((nx, ny, nz), dtype=float, order="F")
        for k in range(start_layer, end_layer):
            new_values[:, :, k] = input_values_for_zone[:, :, k - start_layer]

        if use_regions:
            current_values[zone_region_cell_numbers] = new_values[
                i_indices, j_indices, k_indices
            ]
        else:
            current_values[zone_cell_numbers] = new_values[
                i_indices, j_indices, k_indices
            ]

        property_param.set_values(current_values, realisation_number)

    return True


def get_conformity(
    grid_model_name: str,
    zone_numbers: list[int],
) -> dict[int, str]:
    """Function to get conformity from the grid.
    Restrictions:
    - All horizons used are specified to be honored and not sampled.
    - The zones must be defined with Horizon as reference for both
      top and base and no Surface is used to define grid layout.
    - If the two above mentioned criteria is satisfied, it is possible
      to use the 'ConformalMode' list from rmsapi to get conformity status.

    If restrictions above are not satisfied, the conformity will be 'Undefined'
    """

    rms_grid_job_name = check_and_get_grid_job_name(grid_model_name)
    assert rms_grid_job_name

    conformity_dict: dict[int, str] = {}
    for zone_number in zone_numbers:
        conform_zone_dict = get_conformity_per_zone(
            grid_model_name, zone_number, rms_grid_job_name
        )
        conformity_dict[zone_number] = conform_zone_dict["conformity"]
    return conformity_dict


def get_conformity_per_zone(
    grid_model_name: str,
    zone_number: int,
    rms_grid_job_name: str,
) -> dict[str, str]:
    assert grid_model_name
    assert rms_grid_job_name
    assert zone_number > 0
    arguments = get_grid_building_job_arguments(grid_model_name, rms_grid_job_name)
    conformal_mode_list = arguments["ConformalMode"]
    zone_names = arguments["ZoneNames"]
    use_base_surface = arguments["UseBottomSurface"]
    use_top_surface = arguments["UseTopSurface"]

    # zone_number starts at 1
    conform_mode = conformal_mode_list[zone_number - 1]
    use_top_surf = use_top_surface[zone_number - 1]
    use_base_surf = use_base_surface[zone_number - 1]

    assert conform_mode in [0, 1, 2]
    if conform_mode == 0:
        conform = "Proportional"
    elif conform_mode == 1:
        conform = "TopConform"
    else:
        conform = "BaseConform"

    if use_top_surf or use_base_surf:
        conform = "Undefined"

    return {
        "zone_name": zone_names[zone_number - 1],
        "conformity": conform,
    }


def get_grid_building_job_arguments(
    grid_model_name: str, rms_grid_job_name: str
) -> Any:
    owner_strings = ["Grid models", grid_model_name, "Grid"]
    type_string = "Create Grid"
    grid_job = Job.get_job(owner_strings, type_string, rms_grid_job_name)
    return grid_job.get_arguments()


def get_job_names(grid_model_name: str) -> list[str]:
    owner_strings = ["Grid models", grid_model_name, "Grid"]
    type_string = "Create Grid"
    return Job.get_job_names(owner_strings, type_string)


def log_warning(message_lines, debug_level=DEBUG_ON):
    """Helper function to print warning messages if debug_level is above threshold."""
    if debug_level >= DEBUG_ON:
        print("WARNING:")
        for line in message_lines:
            print(f"         {line}")


def check_and_get_grid_job_name(
    grid_model_name: str, debug_level: int = DEBUG_OFF
) -> Union[None, str]:
    """Check if there are one unique grid building job for the grid model.
    If one unique grid buidling job, check that no zone bounaries are defined by
    the option 'Sample' and that all are defined by the method 'Honor'.
    Return job name or None
    """
    job_names = get_job_names(grid_model_name)
    if job_names is None or len(job_names) == 0:
        log_warning(
            [
                f"No automatic grid conformity check for '{grid_model_name}'",
                "This grid is not created by an RMS grid building job.",
            ],
            debug_level,
        )
        return None

    if len(job_names) > 1:
        log_warning(
            [
                f"No automatic grid conformity check for '{grid_model_name}'",
                "There exist multiple grid building jobs for this grid.",
                "Cannot know which one to use to check grid conformity.",
                "The jobs are:",
                f"{job_names}",
            ],
            debug_level,
        )
        return None

    rms_grid_job_name = job_names[0]

    arguments = get_grid_building_job_arguments(grid_model_name, rms_grid_job_name)
    sample_zone_boundaries = arguments["SampledHorizons"]

    err = False
    for indx, is_sampled in enumerate(sample_zone_boundaries):
        if is_sampled:
            # This indicates that some zone borders are calculated using 'Sample'
            # and not 'Honor'. In this case the conformal_mode_list no longer
            # match the modelling zones since sone zones are merged when
            # defining grid layout.
            err = True
            log_warning(
                [
                    f"The grid definition in the job '{rms_grid_job_name}' "
                    f"for the grid model '{grid_model_name}' is not implemented.",
                    f"Zone boundary {indx + 1} is defined by the option 'Sample'.",
                    "Only zone boundaries defined by option 'Honor' is implemented.",
                ],
                debug_level,
            )

    return None if err else rms_grid_job_name


def check_grid_layout(
    grid_model_name: str,
    zone_number: int,
    grid_layout: Union[None, str] = None,
    aps_job_name: Union[None, str] = None,
    return_grid_layout: bool = False,
    debug_level: int = DEBUG_OFF,
) -> Union[None, str]:
    """Function checking grid conformity of the grid if possible.
    - If not possible return None.
    - If possible and 'return_grid_layout' is True,
      then return the grid layout from the grid model.
    - If possible and 'return_grid_layout' is False,
      then compare the input specified 'grid_layout' with the one from the grid model
      and raise error if they are not equal and return the grid_layout that is equal to
      the input of ok.
    """

    rms_grid_job_name = check_and_get_grid_job_name(
        grid_model_name, debug_level=debug_level
    )
    if rms_grid_job_name is None:
        return None

    zone_conformity_dict = get_conformity_per_zone(
        grid_model_name, zone_number, rms_grid_job_name
    )

    zone_name = zone_conformity_dict["zone_name"]
    conformity = zone_conformity_dict["conformity"]

    # If grid_layout is known and match the grid conformity,
    # or is unknown return grid_layout
    if conformity == "Undefined":
        # Conformity is undefined. This means have to accept the specified
        # grid_layout since the implemented conformity does not support
        # the conformity found in the grid
        if debug_level >= DEBUG_ON:
            print(f"- Grid conformity found for zone '{zone_name}' is not implemented.")
            if grid_layout:
                print(
                    "- Will accept to use the user specified conformity: "
                    f"{grid_layout}."
                )
            else:
                print("- Will accept to use the user specified conformity.")
        return grid_layout

    if return_grid_layout:
        # Return the grid layout from the grid model since it is defined and ignore
        # any mismatch with the specified input grid_layout
        if debug_level >= DEBUG_VERY_VERBOSE:
            print(
                "--- Use grid conformity from the grid model for zone "
                f"{zone_number}: {conformity}"
            )
        return conformity

    # Check and report error if no match between specified grid-layout
    # and grid-layout in the grid model for the case the conformity is not 'Undefined'
    if conformity != grid_layout:
        if aps_job_name is not None:
            aps_job_string = f"'in APS job '{aps_job_name}'"
        else:
            aps_job_string = ""
        raise ValueError(
            "\n"
            f"Specified zone conformity for zone '{zone_name}' with zone number "
            f"{zone_number} is '{grid_layout}'.\n"
            f"Grid model '{grid_model_name}' has different zone conformity: "
            f"{conformity}.\n"
            f"Change conformity setting {aps_job_string} to match the correct "
            "one used in the grid model."
        )
    if debug_level >= DEBUG_VERY_VERBOSE:
        print(
            "--- Specified grid conformity "
            f"is consistent with the grid for zone '{zone_name}'"
        )
    return None


def check_grid_conformity(
    grid_model_name: str, zone_numbers: list[int], debug_level: int = DEBUG_OFF
) -> bool:
    ok = True
    for zone_number in zone_numbers:
        conformity = check_grid_layout(
            grid_model_name,
            zone_number,
            return_grid_layout=True,
            debug_level=debug_level,
        )
        if conformity is None:
            ok = False
    return ok


def assign_conformity(
    params: dict,
    debug_level: int = DEBUG_OFF,
) -> dict[int, str]:
    """This function assumes that grid conformity is already checked
    and if grid conformity is not defined, the grid conformity must
    be defined by the user and keyword 'Conformity' defined.
    """
    grid_model_name = params["GridModelName"]
    geogrid_parameter_dict = params["GeoGridParameters"]
    zone_numbers = list(geogrid_parameter_dict.keys())
    if params["Conformity_required"]:
        # Now expecting conformity to be specified by the user
        conformity_dict: dict[int, str] = params["Conformity"]
        assert conformity_dict
        if debug_level >= DEBUG_VERBOSE:
            print("-- Use grid conformity specified by user.")
    else:
        # Get conformity from the RMS grid building job for the grid model
        if debug_level >= DEBUG_VERBOSE:
            if "Conformity" in params:
                print(
                    "-- Specified conformity is not used but read from "
                    "the RMS grid building job for grid model "
                    f"'{grid_model_name}' instead."
                )
            else:
                print(
                    "-- Get conformity from RMS grid building job for grid model "
                    f"{grid_model_name}."
                )

        conformity_dict = get_conformity(grid_model_name, zone_numbers)
        assert conformity_dict
    return conformity_dict


def extract_values_from_geogrid_simbox_to_ertbox_grid(
    ertbox_values_3d_masked: np.ma.MaskedArray[Any, Any],
    geogrid_values_3d_all: np.ndarray,
    nz_zone_geogrid: int,
    start_layer_geogrid: int,
    end_layer_geogrid: int,
    conformity: str,
) -> np.ma.MaskedArray[Any, Any]:
    # The RMS simbox layers (num_layers) are copied into ertbox grid
    # at top if grid layout is top conform or proportional and
    # at the bottom if grid layout is base conform.
    nz = nz_zone_geogrid
    if conformity in ["BaseConform"]:
        # Only copy the geogrid layers for the zone into the lowermost ertbox layers
        ertbox_values_3d_masked[:, :, -nz:] = geogrid_values_3d_all[
            :, :, start_layer_geogrid : (end_layer_geogrid + 1)
        ]

    elif conformity in ["TopConform", "Proportional"]:
        # Only copy the geogrid layers for the zone into the uppermost ertbox layers
        ertbox_values_3d_masked[:, :, 0:nz] = geogrid_values_3d_all[
            :, :, start_layer_geogrid : (end_layer_geogrid + 1)
        ]

    else:
        raise NotImplementedError(f"Grid conformity {conformity} is not implemented.")

    return ertbox_values_3d_masked


def extract_values_from_ertbox_grid_to_geogrid_simbox(
    field_values_3d: np.ndarray,
    grid_layout_as_string: str,
    number_of_layers_in_geo_grid_zone: int,
) -> np.ndarray:
    """Updates or replaces the input field_values for fmu ertbox grid to contain
    only the values that are used in the geomodel simbox.
    Use grid conformity definition to select layers from top of fmu ertbox grid
    or from bottom of ertbox grid.

    """
    nz = number_of_layers_in_geo_grid_zone
    conformity = grid_layout_as_string
    if conformity is None:
        raise ValueError("Undefined conformity")
    if conformity in ["Proportional", "TopConform"]:
        # Only get the top n cells of field_values
        field_values_3d = field_values_3d[:, :, :nz]
    elif conformity in ["BaseConform"]:
        # Get the bottom n cells of field_values
        field_values_3d = field_values_3d[:, :, -nz:]
    else:
        # One such case is 'mixed conform'
        raise ValueError(f"Grid conformity: {conformity} is not implemented")
    return field_values_3d


def extract_active_values_from_geogrid_simbox_to_ertbox_grid(
    ertbox_active_3d: np.ndarray,
    geogrid_active_3d: np.ndarray,
    nz_zone_geogrid: int,
    start_layer_geogrid: int,
    end_layer_geogrid: int,
    conformity: str,
) -> np.ndarray:
    # The RMS simbox layers (num_layers) integer parameter is copied into ertbox grid
    # at top if grid layout is top conform or proportional and
    # at the bottom if grid layout is base conform
    nz = nz_zone_geogrid
    if conformity in ["BaseConform"]:
        # Only copy the geogrid layers for the zone into the lowermost ertbox layers
        ertbox_active_3d[:, :, -nz:] = geogrid_active_3d[
            :, :, start_layer_geogrid : (end_layer_geogrid + 1)
        ]

    elif conformity in ["TopConform", "Proportional"]:
        # Only copy the geogrid layers for the zone into the uppermost ertbox layers
        ertbox_active_3d[:, :, 0:nz] = geogrid_active_3d[
            :, :, start_layer_geogrid : (end_layer_geogrid + 1)
        ]

    else:
        raise ValueError(f"Grid conformity {conformity} is not implemented.")

    return ertbox_active_3d
