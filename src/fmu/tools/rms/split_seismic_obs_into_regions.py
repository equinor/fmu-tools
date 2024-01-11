"""
Split files with seismic observations into one file per specified region group.
A region group contains one or more region numbers. Metadata file with info
about region number is used to split the original observations into one
file per region group.
The purpose is to be able to define one GENERAL_OBSERVATION keyword per
region group for seismic observations and use this split in localisation in ERT for
cases where it is useful to update model parameters within isolated regions
conditioned to only observations within the same region.
"""
import numpy as np

SEIS_OBS_FILES = [
    "topvolantis_amplitude_mean_20200701_20180101_1.txt",
    "basevolantis_amplitude_mean_20200701_20180101_1.txt",
]
METADATA_FILE = "metadata.csv"
FILE_PATH = "../../ert/input/observations/seismic"

REGION_COLUMN = 3
REGION_GROUPS_SPECIFIED = {
    1: [5],
    2: [4, 6, 3],
}


def define_region_groups(region_groups, min_region_number, max_region_number):
    """
    Validate specified region groups and define a separate group for all region numbers
    not included in any of the region groups specified in the input region_groups.
    Returns updated region_groups.
    """
    all_reg_list = []
    err_list = []
    err_list_outside = []
    max_reg_nr_in_group = 0
    for grp in region_groups:
        reg_list = region_groups[grp]
        if max(reg_list) > max_reg_nr_in_group:
            max_reg_nr_in_group = max(reg_list)

        for i in reg_list:
            if not min_region_number <= i <= max_region_number:
                err_list_outside.append(i)
            if i not in all_reg_list:
                all_reg_list.append(i)
            else:
                err_list.append(i)
    if len(err_list_outside) > 0:
        raise ValueError(
            f"Some region numbers: {err_list_outside} is outside "
            f"[{min_region_number},{max_region_number}]."
        )
    if len(err_list) > 0:
        raise ValueError(
            f"Some region numbers: {err_list} specified in multiple region groups."
        )
    number_of_groups = len(region_groups)
    last_group_list = []
    for i in range(min_region_number, max_region_number + 1):
        if i not in all_reg_list:
            last_group_list.append(i)
    region_groups[number_of_groups + 1] = last_group_list
    return region_groups


def read_region_metadata(region_data_file, use_column=3):
    """
    Read metadatafile with region number from specified column.
    """
    with open(region_data_file, "r", encoding="UTF-8") as file:
        lines = file.readlines()

    # Skip counting heading line
    nsize = len(lines) - 1
    regions = np.zeros(nsize, dtype=np.int32)
    count = -1
    for line in lines:
        if count < 0:
            count += 1
            continue
        words = line.split(",")
        regions[count] = int(float(words[use_column - 1]))
        count += 1

    return regions


def read_obs_data(filename):
    """
    Read observation file used in GENERAL_OBSERVATION keyword for seismic observation.
    Return numpy array with observation values and observation uncertainties.
    """
    # Two column file with    value std_error and no heading
    with open(filename, "r", encoding="UTF-8") as file:
        lines = file.readlines()

    nsize = len(lines)
    obs_val = np.zeros(nsize, dtype=np.float32)
    obs_std = np.zeros(nsize, dtype=np.float32)

    count = 0
    for line in lines:
        words = line.split(" ")
        obs_val[count] = float(words[0])
        obs_std[count] = float(words[1])
        count += 1

    return obs_val, obs_std


def write_obs_data(filename, obs_val, obs_std):
    """
    Write two column file with observation value and observation uncertainty.
    """
    size = len(obs_val)
    with open(filename, "w", encoding="utf-8") as file:
        for i in range(size):
            file.write(f"{obs_val[i]:.6f}   {obs_std[i]:.6f}\n")


def write_obs_data_indices(filename, indices):
    """
    Write index file with one index per observation where the index refer to
    the prediction of the observation value calculated by a forward model.
    The index file is used in GENERAL_OBSERVATION keyword to link
    observations to their forward model predictions.
    """
    size = len(indices)
    with open(filename, "w", encoding="utf-8") as file:
        for i in range(size):
            file.write(f"{indices[i]}\n")


def main():
    """
    Read original observations files used by the original GENERAL_OBSERVATION
    keyword. Read metadata file for the observation files with region number
    per observation. Filter out the observations belonging to each region.
    Merge together all observations for regions belonging to the same region group.
    Write new observation files with corresponding index files for each region group.
    """
    # pylint: disable=R0914
    seismic_obs_input_files = []
    seismic_obs_input_files.append(FILE_PATH + "/" + SEIS_OBS_FILES[0])
    seismic_obs_input_files.append(FILE_PATH + "/" + SEIS_OBS_FILES[1])
    metadata_obs_input_file = FILE_PATH + "/" + METADATA_FILE
    #    print(f"filename: {metadata_obs_input_file}")

    print(f"Read file: {metadata_obs_input_file}")
    regions = read_region_metadata(metadata_obs_input_file, use_column=REGION_COLUMN)

    min_region_number = regions.min()
    max_region_number = regions.max()
    region_groups = define_region_groups(
        REGION_GROUPS_SPECIFIED, min_region_number, max_region_number
    )
    print(
        f"Minimum region number: {min_region_number}    "
        f"Maximum region number: {max_region_number}"
    )
    print(f"region_groups: {region_groups}")

    indexarray = np.arange(len(regions))

    for filename in seismic_obs_input_files:
        print(f"Read file: {filename}")
        obs_val, obs_std = read_obs_data(filename)
        assert len(regions) == len(obs_val)
        indices_for_region_group = []
        for region_grp_number, region_list in region_groups.items():
            for region_number in region_list:
                selected_indices = indexarray[regions == region_number]
                indices_for_region_group.extend(selected_indices)
            data_indices = np.array(indices_for_region_group)
            selected_obs_val = obs_val[data_indices]
            selected_obs_std = obs_std[data_indices]
            filename_selected = (
                filename[: len(filename) - 4]
                + "_regiongroup_"
                + str(region_grp_number)
                + ".txt"
            )
            print(f"Write file: {filename_selected}")
            write_obs_data(filename_selected, selected_obs_val, selected_obs_std)
            filename_for_indices = (
                filename[: len(filename) - 4]
                + "_regiongroup_"
                + str(region_grp_number)
                + "_indices"
                + ".txt"
            )
            print(f"Write file: {filename_for_indices}")
            write_obs_data_indices(filename_for_indices, data_indices)


if __name__ == "__main__":
    main()
