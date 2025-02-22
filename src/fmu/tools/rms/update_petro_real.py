"""
Merge petrophysical realizations created individually per facies
into one realization using facies realization as filter
"""

from pathlib import Path
from typing import Dict, List

import xtgeo

from fmu.tools.rms.generate_petro_jobs_for_field_update import (
    get_original_job_settings,
    read_specification_file,
)


def update_petro_real(
    project,
    facies_code_names: Dict[int, str],
    config_file: str = "",
    grid_name: str = "",
    facies_real_name: str = "",
    used_petro_dict: Dict = {},
    zone_name_for_single_zone_grid: str = "",
    zone_code_names: Dict[int, str] = {},
    zone_param_name: str = "",
    debug_print: bool = False,
    ignore_missing_parameters: bool = False,
) -> None:
    """Combine multiple petrophysical realizations (one per facies) into one parameter
    using facies realization as filter.

    Description:
        This function will read petrophysical realization for multiple facies
        (where all grid cells have the same facies) and use the facies
        realization to combine them into one realization conditioned to facies.

    Input:
        Choose either to use a config file of the same type as for the function
        generate_petro_real in fmu.tools.rms or choose to specify the
        dictionary defining which petro variables to use as field parameters for
        each zone and facies. In the last case also specify grid model
        and facies realization name.

        If multi zone grid is used, also specify dictionary defining
        zone name and zone code and zone parameter name.

    Output:
        Updated version of petrophysical realizations
        for the specified petrophysical variables.

    """
    if config_file:
        spec_dict = read_specification_file(config_file)
        used_petro_dict = spec_dict["used_petro_var"]
        grid_name = spec_dict["grid_name"]
        original_job_name = spec_dict["original_job_name"]

        # Get facies param name from the job settings
        owner_string_list = ["Grid models", grid_name, "Grid"]
        job_type = "Petrophysical Modeling"
        petro_job_param = get_original_job_settings(
            owner_string_list, job_type, original_job_name
        )
        # Get facies realization name from the original petrophysics job
        facies_real_name = petro_job_param["InputFaciesProperty"][2]
    else:
        # Check that necessary parameters are specified
        if not grid_name:
            raise ValueError(
                "Need to specify grid name when config file is not specified."
            )
        if not used_petro_dict:
            raise ValueError(
                "Need to specify the dict used_petro_dict when "
                "config file is not specified."
            )
        if not facies_real_name:
            raise ValueError(
                "Need to specify the facies realization name when "
                "config file is not specified."
            )
    grid = xtgeo.grid_from_roxar(project, grid_name)
    subgrids = grid.subgrids

    if subgrids:
        # Multi zone grid is found
        if not zone_code_names:
            raise ValueError(
                "Need to specify the 'zone_code_names' when using multi zone grids."
            )
        if not zone_param_name:
            raise ValueError(
                "Need to specify the 'zone_param_name' when using multi zone grids."
            )
        if zone_name_for_single_zone_grid:
            raise ValueError(
                f"For multi zone grids {grid_name} the variable "
                "'zone_name_for_single_zone_grid' should not be used"
            )
    else:
        if not zone_name_for_single_zone_grid:
            raise ValueError(
                "Need to specify 'zone_name_for_single_zone_grid' "
                f"since input {grid_name} is a single zone grid."
            )

    combine_petro_real_from_multiple_facies(
        project,
        grid_name,
        facies_real_name,
        used_petro_dict,
        facies_code_names,
        zone_name_for_single_zone_grid=zone_name_for_single_zone_grid,
        zone_param_name=zone_param_name,
        zone_code_names=zone_code_names,
        debug_print=debug_print,
        ignore_missing_parameters=ignore_missing_parameters,
    )


def import_updated_field_parameters(
    project,
    used_petro_dict: Dict,
    grid_model_name: str = "ERTBOX",
    zone_name_for_single_zone_grid: str = "",
    import_path: str = "../..",
    debug_print: bool = False,
) -> None:
    """Import ROFF files with field parameters updated by ERT.

    Description:
        This function will import ROFF format files generated by ERT when using
        the FIELD keyword in ERT to update petrophysical field parameters.
        The naming convention is files with the name of the form:
        zonename_faciesname_petrovarname with suffix ".roff"
        The files are assumed to be located at the top directory level
        where updated fields are written by ERT.

    Input:
        A dictionary specifying which petrophysical variables to use as field parameters
        for each facies for each zone.
        The grid model name to import the field parameters into (ERTBOX grid).
        For singe zone grids, also a name of the zone for the single zone
        must be specified.

    The result will be new petrophysical parameters in ERTBOX grid.

    """

    for zone_name, petro_per_facies_dict in used_petro_dict.items():
        if len(used_petro_dict) == 1:
            # Single zone grid, use specified zone name
            zone_name = zone_name_for_single_zone_grid
        if debug_print:
            print(f"Zone name:  {zone_name}")
        for fname, petro_list in petro_per_facies_dict.items():
            if debug_print:
                print(f"Facies name:  {fname}")
            for petro_name in petro_list:
                if debug_print:
                    print(f"Petro variable:  {petro_name}")
                property_name = zone_name + "_" + fname + "_" + petro_name
                file_name = Path(import_path) / Path(property_name + ".roff")
                print(f"Import file: {file_name} into {grid_model_name}")
                xtgeo_prop = xtgeo.gridproperty_from_file(
                    file_name, fformat="roff", name=property_name
                )
                xtgeo_prop.to_roxar(project, grid_model_name, property_name)


def export_initial_field_parameters(
    project,
    used_petro_dict: Dict,
    grid_model_name: str = "ERTBOX",
    zone_name_for_single_zone_grid: str = "",
    export_path: str = "../../rms/output/aps",
    debug_print: bool = False,
) -> None:
    """Export ROFF files with field parameters simulated by RMS to files to be
       read by ERT and used as field parameters.

    Description:
        This function will export ROFF format files generated by RMS in workflows
        where field parameters are updated by ERT.
        The parameter names will be in the format: zonename_faciesname_petroname
        and the file names will have extension ".roff".
        The files are assumed to be located in the directory:  rms/output/aps
        together with field parameters used by the facies modelling method APS.


    Input:
        A dictionary specifying which petrophysical variables to use as field parameters
        for each facies for each zone.
        The grid model name to export the field parameters from (ERTBOX grid).
        For singe zone grids, also a name of the zone for the single zone must
        be specified.

    The result will be files with petrophysical parameters per zone per facies with
    size equal to the ERTBOX grid.

    """

    for zone_name, petro_per_facies_dict in used_petro_dict.items():
        if len(used_petro_dict) == 1:
            # Single zone grid, use specified zone name
            zone_name = zone_name_for_single_zone_grid
        if debug_print:
            print(f"Zone name:  {zone_name}")
        for fname, petro_list in petro_per_facies_dict.items():
            if debug_print:
                print(f"Facies name:  {fname}")
            for petro_name in petro_list:
                if debug_print:
                    print(f"Petro variable:  {petro_name}")
                property_name = zone_name + "_" + fname + "_" + petro_name
                file_name = Path(export_path) / Path(property_name + ".roff")
                print(f"Export file: {file_name} into {grid_model_name}")
                xtgeo_prop = xtgeo.gridproperty_from_roxar(
                    project, grid_model_name, property_name
                )
                xtgeo_prop.to_file(file_name, fformat="roff", name=property_name)


def combine_petro_real_from_multiple_facies(
    project,
    grid_name: str,
    facies_real_name: str,
    used_petro_dict: Dict[str, Dict[str, List[str]]],
    facies_code_names: Dict[int, str],
    zone_name_for_single_zone_grid: str = "",
    zone_param_name: str = "",
    zone_code_names: Dict[int, str] = {},
    debug_print: bool = False,
    ignore_missing_parameters: bool = False,
) -> None:
    single_zone_grid = False
    if len(zone_name_for_single_zone_grid) > 0:
        single_zone_grid = True

    # Find all defined 3D grid parameters using rmsapi
    properties = project.grid_models[grid_name].properties
    property_names = [prop.name for prop in properties]
    #    print(f"Gridname:  {grid_name}  Properties: {property_names}")

    # Find all petro var names to use in any zone
    petro_var_list = get_petro_var(used_petro_dict)

    # Get facies realization
    prop_facies = xtgeo.gridproperty_from_roxar(
        project, grid_name, facies_real_name, faciescodes=True
    )
    prop_facies_values = prop_facies.values

    # Get zone realization for multi zone grid
    if not single_zone_grid:
        prop_zone = xtgeo.gridproperty_from_roxar(project, grid_name, zone_param_name)
        prop_zone_values = prop_zone.values

    err_msg = []
    for zone_name, petro_per_facies_dict in used_petro_dict.items():
        if single_zone_grid:
            # This is a single zone grid
            if len(used_petro_dict) > 1 and zone_name_for_single_zone_grid != zone_name:
                # Skip all but the one with correct zone name
                continue
            # Use the specified zone name
            zone_name = zone_name_for_single_zone_grid
        else:
            if zone_code_names:
                zone_code = code_per_name(zone_code_names, zone_name)
        for pname in petro_var_list:
            prop_petro_original = xtgeo.gridproperty_from_roxar(
                project, grid_name, pname
            )
            prop_petro_original_values = prop_petro_original.values
            is_updated = False
            for fname in petro_per_facies_dict:
                petro_list_for_this_facies = petro_per_facies_dict[fname]
                if pname in petro_list_for_this_facies:
                    petro_name_per_facies = f"{fname}_{pname}"

                    # Get petro realization for this facies and this petro variable
                    if petro_name_per_facies not in property_names:
                        err_msg.append(
                            "Skip non-existing petro realization: "
                            f"{petro_name_per_facies}"
                        )
                        continue
                    if (
                        project.grid_models[grid_name]
                        .properties[petro_name_per_facies]
                        .is_empty()
                    ):
                        err_msg.append(
                            f"Skip empty petro realization: {petro_name_per_facies}"
                        )
                        continue

                    prop_petro = xtgeo.gridproperty_from_roxar(
                        project, grid_name, petro_name_per_facies
                    )
                    prop_petro_values = prop_petro.values

                    facies_code = code_per_name(facies_code_names, fname)

                    if not single_zone_grid:
                        # Multi zone grid
                        if debug_print:
                            print(
                                f"Update values for {pname} "
                                f"in existing parameter for facies {fname} "
                                f"for zone {zone_name}"
                            )
                        cells_selected = (prop_facies_values == facies_code) & (
                            prop_zone_values == zone_code
                        )
                    else:
                        if debug_print:
                            print(
                                f"Update values for {pname} "
                                f"in existing parameter for facies {fname}"
                            )
                        cells_selected = prop_facies_values == facies_code
                    is_updated = True
                    prop_petro_original_values[cells_selected] = prop_petro_values[
                        cells_selected
                    ]
            prop_petro_original.values = prop_petro_original_values
            if is_updated:
                if not single_zone_grid:
                    # Multi zone grid
                    print(
                        f"Write updated petro param {pname} "
                        f"for zone {zone_name} to grid model {grid_name}"
                    )
                else:
                    print(
                        f"Write updated petro param {pname} for grid model {grid_name}"
                    )
            prop_petro_original.to_roxar(project, grid_name, pname)
    if not ignore_missing_parameters and len(err_msg) > 0:
        print(
            f"Missing or empty petrophysical 3D parameters for grid model: {grid_name}:"
        )
        for msg in err_msg:
            print(f"  {msg}")
        raise ValueError("Missing or empty petrophysical parameters.")
    print(f"Finished updating properties for grid model: {grid_name}")
    print(" ")
    if len(err_msg) > 0:
        print(
            "Warning: Some petrophysical parameters were not updated. Is that correct?"
        )


def code_per_name(code_name_dict: Dict[int, str], input_name: str) -> int:
    # Since name is (must be) unique, get it if found or return -1 if not found
    for code, name in code_name_dict.items():
        if input_name == name:
            return code
    return -1


def get_petro_var(used_petro_dict: Dict[str, Dict[str, List[str]]]) -> List[str]:
    petro_var_list = []
    for _, petro_var_per_facies_dict in used_petro_dict.items():
        for _, petro_list in petro_var_per_facies_dict.items():
            for petro_name in petro_list:
                if petro_name not in petro_var_list:
                    petro_var_list.append(petro_name)
    return petro_var_list
