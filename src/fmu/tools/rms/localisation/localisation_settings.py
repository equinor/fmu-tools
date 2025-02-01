import copy
import math
from pathlib import Path

import xtgeo
import yaml

config_file = (
    "/private/olia/fmu-tools-olia/src/fmu/tools/rms/localisation/example_dist_loc3.yml"
)


def read_ert_summary_obs_file(filename: str):
    with open(filename, "r") as file:
        all_lines = file.readlines()
    line_number = 0
    obs_list = []
    for line in all_lines:
        line_number += 1
        # Remove endline
        line = line.strip()
        words = line.split()

        # Skip empty lines
        if len(words) == 0:
            continue

        # Skip comment lines
        if words[0].strip() == "--":
            continue

        # First word should be ERT key for summary observation
        ert_key = words[0].strip()
        if ert_key != "SUMMARY_OBSERVATION":
            continue

        # Now split the line at { and }
        words = line.split("{")
        string1 = words[0]
        string2 = words[1]

        # First part of string1 is ert keyword, second is ERT-ID for observation
        _, ert_id = string1.split()

        w = string2.split("}")
        # First part of string2 consists of all observation attributes
        obs_attributes_line = w[0]

        # Split the line of obs attributes into separate attributes
        # where each word consists of keyword=value
        obs_attributes_words = obs_attributes_line.split(";")
        obs_dict = {}
        for w2 in obs_attributes_words:
            w2 = w2.strip()
            if len(w2) == 0:
                continue
            # Split into keyword, '=' and value
            attribute_item = w2.split("=")
            if len(attribute_item) == 0:
                continue
            if len(attribute_item) != 2:
                raise ValueError(
                    f"Format error in file: {filename} for line number: {line_number}\n"
                )
            obs_attribute_key = attribute_item[0].strip()
            obs_attribute_value = attribute_item[1].strip()
            obs_dict[obs_attribute_key] = obs_attribute_value

        # Get obs_type and wellname
        ecl_key = obs_dict["KEY"]
        obs_type, well_name = ecl_key.split(":")

        # Add additional info to obs
        obs_dict["ert_id"] = ert_id.strip()
        obs_dict["wellname"] = well_name.strip()
        obs_dict["obs_type"] = obs_type.strip()
        obs_list.append(obs_dict)
    return obs_list


def write_ert_summary_obs_file(obs_dict_list: list[dict], filename: str):
    filepath = Path(filename)
    if filepath.exists():
        raise IOError(
            f"The file {filename} already exists. "
            "Choose another filename to write ERT summary observations."
        )
    print(f"Write file:  {filename}")
    with open(filename, "w") as file:
        for obs_dict in obs_dict_list:
            file.write("SUMMARY_OBSERVATION    ")
            file.write(obs_dict["ert_id"])
            file.write("  { ")
            file.write("VALUE = ")
            file.write(obs_dict["VALUE"])
            file.write(";  ")
            file.write("ERROR = ")
            file.write(obs_dict["ERROR"])
            file.write(";  ")
            file.write("DATE = ")
            file.write(obs_dict["DATE"])
            file.write(";  ")
            file.write("KEY = ")
            file.write(obs_dict["KEY"])
            file.write(";  ")
            if "XPOS" in obs_dict:
                file.write("XPOS = ")
                file.write(obs_dict["XPOS"])
                file.write(";  ")
            if "YPOS" in obs_dict:
                file.write("YPOS = ")
                file.write(obs_dict["YPOS"])
                file.write(";  ")
            file.write("};\n")


def read_field_param_names(ert_config_field_param_file):
    with open(ert_config_field_param_file, "r") as file:
        all_lines = file.readlines()
    field_names = []
    for line in all_lines:
        words = line.split()
        if len(words) == 0:
            continue
        w = words[0].strip()
        if w[:2] == "--":
            continue
        if w.upper() == "GRID":
            grid_file_name = words[1].strip()
            continue
        if words[0].strip() == "FIELD":
            field_name = words[1].strip()
            field_names.append(field_name)
    return {
        "grid": grid_file_name,
        "fields": field_names,
    }


def read_renaming_table(filename):
    with open(filename, "r") as file:
        all_lines = file.readlines()
    # Skip first two lines
    renaming_dict = {}
    for line in all_lines[2:]:
        words = line.split()
        rms_well_name = words[0]
        eclipse_well_name = words[1].strip()
        renaming_dict[eclipse_well_name] = rms_well_name.strip()
    return renaming_dict


def convert_to_rms_well_names(observation_list, renaming_dict):
    new_obs_list = []
    for obs_dict in observation_list:
        eclipse_well_name = obs_dict["wellname"]
        rms_well_name = renaming_dict.get(eclipse_well_name)
        if rms_well_name is None:
            raise KeyError(
                f"The eclipse well name: {eclipse_well_name} "
                f"is not defined in the renaming table. "
                "Cannot get RMS well name for this eclipse well"
            )
        new_obs_dict = copy.deepcopy(obs_dict)

        # Replace wellname
        new_obs_dict["wellname"] = rms_well_name
        new_obs_list.append(new_obs_dict)
    return new_obs_list


def read_yml_config(filename: str):
    with open(filename, encoding="utf-8") as yml_file:
        return yaml.safe_load(yml_file)


def get_position_of_well_observations(
    project,
    observation_list: dict,
    grid_model,
    blocked_well_set="BW",
    selected_wells: list = [],
    trajectory: str = "Drilled trajectory",
    use_well_head_position: bool = False,
):
    if use_well_head_position:
        print("Use well HEAD position as position of summary observations.")
        """Get well HEAD position and modify input observations by adding position"""
        use_selected_list = len(selected_wells) > 0
        for obs_dict in observation_list:
            wellname = obs_dict["wellname"]
            if not use_selected_list or wellname in selected_wells:
                well = xtgeo.well_from_roxar(project, wellname, trajectory=trajectory)
                obs_dict["xpos"] = well.xpos
                obs_dict["ypos"] = well.ypos
                obs_dict["hlength"] = 0.0
                obs_dict["well_path_angle"] = 0.0
    else:
        # Calculate mean position along blocked well and length of horizontal well path
        print(
            f"Use average well position from blocked well set: {blocked_well_set} "
            f"from grid model: {grid_model}"
        )
        for obs_dict in observation_list:
            wellname = obs_dict["wellname"]
            wellnames = [wellname]
            mean_position_dict = calculate_average_position_of_well_path(
                project, wellnames, grid_model, bw_name=blocked_well_set
            )
            obs_dict["xpos"] = mean_position_dict[wellname]["xpos"]
            obs_dict["ypos"] = mean_position_dict[wellname]["ypos"]
            obs_dict["hlength"] = mean_position_dict[wellname]["hlength"]
            obs_dict["well_path_angle"] = mean_position_dict[wellname]["angle"]

    return observation_list


def get_obs_types(obs_dict_list: list[dict]):
    obs_types = []
    for obs_dict in obs_dict_list:
        obs_type = obs_dict["obs_type"]
        if obs_type not in obs_types:
            obs_types.append(obs_type)
    return obs_types


def get_well_names(obs_dict_list):
    well_names = []
    for obs_dict in obs_dict_list:
        wellname = obs_dict["wellname"]
        if wellname not in well_names:
            well_names.append(wellname)
    return well_names


def get_ert_obs_id(obs_dict_list):
    ert_id_list = []
    for obs_dict in obs_dict_list:
        ert_obs_id = obs_dict["ert_id"]
        if ert_obs_id not in ert_id_list:
            ert_id_list.append(ert_obs_id)
    return ert_id_list


def check_specified_strings(
    string_list: list[str],
    defined_string_list: list[str],
    string_name: str,
    config_file_name: str,
):
    err_strings = []
    err = 0
    for value in string_list:
        if value not in defined_string_list:
            err += 1
            err_strings.append(value)
    if err > 0:
        print(f"Errors: Unknown {string_name} is specified in {config_file_name}")
        for s in err_strings:
            print(f"  {s}")
        raise ValueError(f"Unknown {string_name}")


def write_results(
    result_file: str, output_dict: dict, scaling_function_name: str = "gauss"
):
    print(f"Write file:  {result_file}")

    max_ert_id_length = 5
    max_field_name_length = 5
    max_obs_type_length = 5
    max_well_name_length = 5
    for key, obs_dict in output_dict.items():
        (field_name, ert_id) = key
        obs_type = obs_dict["obs_type"]
        wellname = obs_dict["wellname"]
        if max_ert_id_length < len(ert_id):
            max_ert_id_length = len(ert_id)
        if max_field_name_length < len(field_name):
            max_field_name_length = len(field_name)
        if max_obs_type_length < len(obs_type):
            max_obs_type_length = len(obs_type)
        if max_well_name_length < len(wellname):
            max_well_name_length = len(wellname)
    max_ert_id_length += 2
    max_field_name_length += 2
    max_obs_type_length += 2
    max_well_name_length += 2

    with open(result_file, "w") as file:
        for key, obs_dict in output_dict.items():
            (field_name, ert_id) = key
            field_name_fixed_size = field_name + " " * (
                max_field_name_length - len(field_name)
            )
            ert_id_fixed_size = ert_id + " " * (max_ert_id_length - len(ert_id))
            obs_type = obs_dict["obs_type"]
            obs_type_fixed_size = obs_type + " " * (max_obs_type_length - len(obs_type))
            wellname = obs_dict["wellname"]
            wellname_fixed_size = wellname + " " * (
                max_well_name_length - len(wellname)
            )

            content = ""
            content += field_name_fixed_size
            content += ert_id_fixed_size
            content += obs_type_fixed_size
            content += wellname_fixed_size

            content += str(f"{obs_dict['xpos']:12.1f}") + "   "
            content += str(f"{obs_dict['ypos']:12.1f}") + "   "
            content += str(f"{obs_dict['hlength']:6.1f}") + "   "
            content += str(f"{obs_dict['well_path_angle']:5.1f}") + "   "
            content += str(f"{obs_dict['xrange']:6.1f}") + "   "
            content += str(f"{obs_dict['yrange']:6.1f}") + "   "
            content += str(f"{obs_dict['anisotropy_angle']:5.1f}") + "   "
            content += scaling_function_name
            print(content)
            content += "\n"
            file.write(content)
    print(f"Finished writing file {result_file}")


def expand_wildcards(patterns: list[str], list_of_words: list[str], err_msg: str):
    all_matches = []
    errors = []
    for pattern in patterns:
        matches = [words for words in list_of_words if Path(words).match(pattern)]
        if len(matches) > 0:
            all_matches.extend(matches)
        else:
            errors.append(f"No match for: {pattern}")
    all_matches_set = set(all_matches)
    if len(errors) > 0:
        raise ValueError(f" {err_msg}\n     {errors}, available: {list_of_words}")
    return all_matches_set


def calculate_average_position_of_well_path(
    project,
    well_names,
    grid_model,
    bw_name="BW",
    zone_log_name="Zone",
    min_length=150.0,
):
    mean_position_dict = {}
    for wname in well_names:
        well = xtgeo.blockedwell_from_roxar(
            project, grid_model, bw_name, wname, lognames=[zone_log_name]
        )
        well.create_relative_hlen()
        df = well.get_dataframe()
        mean_position_dict[wname] = {
            "xpos": df["X_UTME"].mean(axis=0),
            "ypos": df["Y_UTMN"].mean(axis=0),
        }

        nrows = df.shape[0]
        horizontal_length = math.fabs(df.at[nrows - 1, "R_HLEN"])
        if horizontal_length < min_length:
            horizontal_length = 0.0
            rotation_angle = 0.0
        else:
            x_start_pos = df.at[0, "X_UTME"]
            y_start_pos = df.at[0, "Y_UTMN"]
            x_end_pos = df.at[nrows - 1, "X_UTME"]
            y_end_pos = df.at[nrows - 1, "Y_UTMN"]
            delta_x = math.fabs(x_end_pos - x_start_pos)
            delta_y = math.fabs(y_end_pos - y_start_pos)

            if delta_y > min_length:
                if delta_x > min_length:
                    # In degrees
                    rotation_angle = 180.0 * math.atan(delta_y / delta_x) / math.pi
                else:
                    rotation_angle = 90.0
            else:
                if delta_x > min_length:
                    rotation_angle = 0.0
        mean_position_dict[wname]["hlength"] = horizontal_length
        mean_position_dict[wname]["angle"] = rotation_angle
    return mean_position_dict


def main(project, config_file):
    if not Path(config_file).exists():
        raise IOError("No such file:" + config_file)
    print(f"Read file: {config_file}")
    spec = read_yml_config(config_file)

    if "localisation" not in spec:
        raise KeyError(f"Missing keyword 'localisation' in {config_file}")
    local_dict = spec["localisation"]

    # Result output file name
    if "result_file" not in local_dict:
        raise KeyError(
            f"Missing keyword 'result_file' in {config_file} "
            "under keyword 'localisation'"
        )
    result_file = local_dict["result_file"]

    if "rms_settings" in local_dict:
        rms_settings_dict = local_dict["rms_settings"]
    else:
        raise ValueError("Missing keyword 'rms_settings' under keyword 'localisation'")

    # Optional. Use well head position
    use_well_head_position = False
    if "use_well_head_position" in rms_settings_dict:
        use_well_head_position = rms_settings_dict["use_well_head_position"]

    # Optional if use well head position is True, otherwise required
    grid_model_name = None
    if "grid_model" in rms_settings_dict:
        grid_model_name = rms_settings_dict["grid_model"]
    else:
        if not use_well_head_position:
            raise ValueError("Missing keyword 'grid_model' under key 'rms_settings'")

    # Optional if use well head position is True, otherwise required
    blocked_well_set_name = None
    if "blocked_well_set" in rms_settings_dict:
        blocked_well_set_name = rms_settings_dict["blocked_well_set"]
    else:
        if not use_well_head_position:
            raise ValueError(
                "Missing keyword 'blocked_well_set' under key 'rms_settings'"
            )

    # Optional. Trajectory type as text string compatible with RMS wells
    trajectory_name = "Drilled trajectory"
    if "trajectory" in rms_settings_dict:
        trajectory_name = rms_settings_dict["trajectory"]

    # Read ert observation file
    if "input_files" not in local_dict:
        raise KeyError(
            f"Missing keyword 'input_files' in {config_file} "
            "under keyword 'localisation'"
        )
    input_files_dict = local_dict["input_files"]

    # Read summary observation ERT file
    if "ert_summary_obs_file" not in input_files_dict:
        raise KeyError(
            f"Missing keyword 'ert_summary_obs_file' in {config_file} "
            "under keyword 'input_files'"
        )
    obs_summary_file = input_files_dict["ert_summary_obs_file"]
    print(f"Read file: {obs_summary_file}")
    obs_dict_list = read_ert_summary_obs_file(obs_summary_file)

    # Update obs_dict_list by renaming well names to RMS well names
    if "well_renaming_table" not in input_files_dict:
        raise KeyError(
            f"Missing keyword 'well_renaming_table' in {config_file} "
            "under keyword 'input_files'"
        )
    well_renaming_table_file = input_files_dict["well_renaming_table"]
    print(f"Read file: {well_renaming_table_file}")
    renaming_dict = read_renaming_table(well_renaming_table_file)
    new_obs_dict_list = convert_to_rms_well_names(obs_dict_list, renaming_dict)
    defined_obs_types = get_obs_types(new_obs_dict_list)
    defined_well_names = get_well_names(new_obs_dict_list)
    defined_ert_obs_id = get_ert_obs_id(new_obs_dict_list)

    # Get position of observations from RMS
    print("Get well positions from RMS")
    new_obs_dict_list = get_position_of_well_observations(
        project,
        new_obs_dict_list,
        grid_model_name,
        blocked_well_set=blocked_well_set_name,
        trajectory=trajectory_name,
        use_well_head_position=use_well_head_position,
    )

    # Get all defined field names
    if "ert_config_field_param_file" not in input_files_dict:
        raise KeyError(
            f"Missing keyword 'ert_config_field_param_file' in {config_file} "
            "under keyword 'input_files'"
        )
    field_param_config_file = input_files_dict["ert_config_field_param_file"]
    print(f"Read file:  {field_param_config_file}")
    field_dict = read_field_param_names(field_param_config_file)
    defined_field_names = field_dict["fields"]

    # Get default range settings to be used if not another specification is given
    if "default_field_settings" not in local_dict:
        raise KeyError(
            f"Missing keyword 'default_field_settings' in {config_file} "
            "under keyword 'localisation'"
        )
    default_settings_spec = local_dict["default_field_settings"]
    if "ranges" not in default_settings_spec:
        raise KeyError(
            f"Missing keyword 'ranges' in {config_file} "
            "under keyword 'default_field_settings'"
        )
    default_ranges = default_settings_spec["ranges"]

    # Get tapering function
    scaling_function_name = "gauss"
    if "tapering" in local_dict:
        scaling_function_name = local_dict["tapering"]

    # Set default settings for all observations initially
    output_dict_default = {}
    output_dict = {}
    for field_name in defined_field_names:
        for obs_dict in new_obs_dict_list:
            obs_localisation_dict = {}
            ert_id = obs_dict["ert_id"]
            result_id = (field_name, ert_id)
            obs_localisation_dict["wellname"] = obs_dict["wellname"]
            obs_localisation_dict["obs_type"] = obs_dict["obs_type"]
            obs_localisation_dict["xpos"] = obs_dict["xpos"]
            obs_localisation_dict["ypos"] = obs_dict["ypos"]
            obs_localisation_dict["hlength"] = obs_dict["hlength"]
            obs_localisation_dict["well_path_angle"] = obs_dict["well_path_angle"]
            obs_localisation_dict["xrange"] = default_ranges[0]
            obs_localisation_dict["yrange"] = default_ranges[1]
            obs_localisation_dict["anisotropy_angle"] = default_ranges[2]
            obs_localisation_dict["summary_key"] = obs_dict["KEY"]
            if result_id not in output_dict_default:
                output_dict_default[result_id] = obs_localisation_dict

    # Optional keyword 'field_settings'
    if "field_settings" in local_dict:
        # Update field settings for specified fields, wells, obs_types
        field_settings_spec_list = local_dict["field_settings"]
        print("Start field settings")
        for field_settings in field_settings_spec_list:
            if "field_name" not in field_settings:
                raise KeyError(
                    f"Missing keyword 'field_name' in {config_file} "
                    "under keyword 'field_settings'"
                )

            field_names = field_settings["field_name"]
            #            print(f"Field names: {field_names}")

            if "obs_type" not in field_settings:
                raise KeyError(
                    f"Missing keyword 'obs_type' in {config_file} "
                    "under keyword 'field_settings'"
                )
            obs_types = field_settings["obs_type"]
            #            print(f"Obs types: {obs_types}")

            if "well_names" not in field_settings:
                raise KeyError(
                    f"Missing keyword 'well_names' in {config_file} "
                    "under keyword 'field_settings'"
                )
            well_names = field_settings["well_names"]
            #            print(f"Well names:  {well_names}")
            if "ranges" not in field_settings:
                raise KeyError(
                    f"Missing keyword 'ranges' in {config_file} "
                    "under keyword 'field_settings'"
                )
            ranges = field_settings["ranges"]
            #            print(f"Ranges: {ranges}")
            # Field names when 'all' is specified
            if len(field_names) == 1 and field_names[0].lower() == "all":
                # Use all fields defined in ERT config file
                field_names = defined_field_names

            # Obs types when 'all' is specified
            if len(obs_types) == 1 and obs_types[0].lower() == "all":
                obs_types = defined_obs_types

            # Well names when 'all' is specified
            if len(well_names) == 1 and well_names[0].lower() == "all":
                well_names = defined_well_names

            # Expand wildcard specifications
            field_names = expand_wildcards(
                field_names,
                defined_field_names,
                "Cannot expand wildcard notation of fieldnames "
                "to any defined field names in ERT model",
            )
            #            print(f"Expanded field names: {field_names}")

            obs_types = expand_wildcards(
                obs_types,
                defined_obs_types,
                "Cannot expand wildcard notation of observation types "
                "to any defined observation types defined in "
                f"observation file {obs_summary_file}",
            )
            #            print(f"Expanded observation types: {obs_types}")

            well_names = expand_wildcards(
                well_names,
                defined_well_names,
                "Cannot expand wildcard notation of wellnames "
                "to any defined well name in RMS model",
            )
            #            print(f"Expanded well names: {well_names}")

            check_specified_strings(
                field_names, defined_field_names, "field names", config_file
            )

            check_specified_strings(
                obs_types, defined_obs_types, "observation types", config_file
            )

            check_specified_strings(
                well_names, defined_well_names, "well names", config_file
            )
            #            print(f"Field names: {field_names}")
            #            print(f"Obs types: {obs_types}")
            #            print(f"Well names:  {well_names}")

            for field_name in field_names:
                #                print(f"Field name: {field_name}")
                for obs_dict in new_obs_dict_list:
                    if (
                        obs_dict["obs_type"] in obs_types
                        and obs_dict["wellname"] in well_names
                    ):
                        ert_id = obs_dict["ert_id"]
                        result_id = (field_name, ert_id)
                        if result_id not in output_dict:
                            #                            print(f"Add   {result_id}")
                            obs_localisation_dict = {}
                            obs_localisation_dict["wellname"] = obs_dict["wellname"]
                            obs_localisation_dict["obs_type"] = obs_dict["obs_type"]
                            obs_localisation_dict["xpos"] = obs_dict["xpos"]
                            obs_localisation_dict["ypos"] = obs_dict["ypos"]
                            obs_localisation_dict["hlength"] = obs_dict["hlength"]
                            obs_localisation_dict["well_path_angle"] = obs_dict[
                                "well_path_angle"
                            ]
                            obs_localisation_dict["xrange"] = ranges[0]
                            obs_localisation_dict["yrange"] = ranges[1]
                            obs_localisation_dict["anisotropy_angle"] = ranges[2]
                            obs_localisation_dict["summary_key"] = obs_dict["KEY"]
                            output_dict[result_id] = obs_localisation_dict

    # All observations not specified under field_settings is
    # added with default settings
    for key, obs_localisation_dict in output_dict_default.items():
        if key not in output_dict:
            #            print(f"Add default for: {key}")
            output_dict[key] = obs_localisation_dict

    if "individual_obs_settings" in local_dict:
        individual_settings_list = local_dict["individual_obs_settings"]
        for single_setting in individual_settings_list:
            if "field_name" not in single_setting:
                ValueError(
                    "Missing keyword 'field_name' under 'individual_obs_settings'"
                )
            field_name = single_setting["field_name"]
            if field_name not in defined_field_names:
                raise ValueError(
                    f"Unknown field name: {field_name} "
                    "in keyword 'field_name' under 'individual_obs_settings'"
                )

            if "ert_obs_id" not in single_setting:
                ValueError(
                    "Missing keyword 'ert_obs_id' under 'individual_obs_settings'"
                )
            ert_obs_id = single_setting["ert_obs_id"]
            if ert_obs_id not in defined_ert_obs_id:
                raise ValueError(
                    f"Unknown ert observation identifier: {ert_obs_id} "
                    "in keyword 'ert_obs_id' under 'individual_obs_settings'"
                )

            if "ranges" not in single_setting:
                ValueError("Missing keyword 'ranges' under 'individual_obs_settings'")
            ranges = single_setting["ranges"]
            if ranges[0] < 0.0 or ranges[1] < 0.0:
                raise ValueError(
                    "Ranges for influence ellipse must be positive "
                    "in keyword 'ranges' under keyword 'individual_obs_settings'"
                )

            key = (field_name, ert_obs_id)
            obs_localisation_dict = output_dict[key]
            obs_localisation_dict["xrange"] = ranges[0]
            obs_localisation_dict["yrange"] = ranges[1]
            obs_localisation_dict["anisotropy_angle"] = ranges[2]
            print(
                f"Modify {key}: "
                f"Changed ranges from default to: "
                f" xrange = {obs_localisation_dict['xrange']}"
                f" yrange = {obs_localisation_dict['yrange']}"
                f" rotation: {obs_localisation_dict['anisotropy_angle']}"
            )
            output_dict[key] = obs_localisation_dict

    # Write result
    write_results(result_file, output_dict, scaling_function_name)


# if __name__ == "__main__":
#        main(project, config_file)
