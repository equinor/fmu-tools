"""
create_rft_ertobs creates txt, obs and welldatefile for usage together
with GENDATA in ERT assisted history match runs.

This script should be run from within RMS to be able to interpolate
along well trajectories::

    from fmu.tools.rms import create_rft_ertobs

    SETUP = {...yourconfiguration...}  # A Python dictionary

    create_rft_ertobs.main(SETUP)

Required keys in the SETUP dictionary:

* input_file or input_dframe: Path to CSV file with data for wellnames, dates
  wellpoint coordinates and pressure values.

Optional keys:

* rft_prefix: Eclipse well names will be prefixed with this string
* gridname: Name of grid in RMS project (for verification)
* zonename: Name of zone parameter in RMS grid (if zone names should be
  verified)
* welldatefile: Name of welldatefile, written to exportdir.
  Defaults to "well_date_rft.txt"

Result:

* ``txt`` files written to ert/input/observations
* ``obs`` files for each well written to ert/input/observations
* ``well_date_rft.txt``
"""

import logging
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import numpy as np
import pandas as pd
from scipy.interpolate import CubicSpline

logger = logging.getLogger(__name__)

SUPPORTED_OPTIONS = [
    "absolute_error",
    "alias",
    "alias_file",
    "ecl_name",
    "exportdir",
    "gridname",
    "input_dframe",
    "input_file",
    "interpolation",
    "loglevel",
    "project",
    "relative_error",
    "rft_prefix",
    "rms_name",
    "trajectory_name",
    "verbose",
    "welldatefile",  # WELL_AND_TIME_FILE in semeio
    "zonename",
    "clipboard_folder",
]


def check_and_parse_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Checks config, and returns a validated and defaults-filled config
    dictionary"""
    config = config.copy()
    unknown_options = set(config.keys()) - set(SUPPORTED_OPTIONS)
    if unknown_options:
        logger.warning("Unknown options ignored: %s", str(unknown_options))

    if config.get("verbose", False):
        config["loglevel"] = logging.INFO
    else:
        config["loglevel"] = logging.WARNING

    assert not ("input_dframe" not in config and "input_file" not in config), (
        "Specify either input_file or input_dframe"
    )

    if "input_dframe" in config and "input_file" in config:
        raise ValueError("Do not specify both input_dframe and input_file")

    required_input_dframe_columns = ["DATE", "MD", "WELL_NAME", "PRESSURE"]
    if "input_dframe" not in config and "input_file" in config:
        input_dframe = pd.read_csv(config["input_file"])
        input_dframe["DATE"] = pd.to_datetime(input_dframe["DATE"])
        config["input_dframe"] = input_dframe
    missing_columns = set(required_input_dframe_columns) - set(
        config["input_dframe"].columns
    )
    optional_columns = ["TVD", "NORTH", "EAST"]
    for col in optional_columns:
        if col not in config["input_dframe"]:
            config["input_dframe"][col] = np.nan

    if missing_columns:
        raise ValueError(f"Missing columns {str(missing_columns)} in input table")

    config["exportdir"] = config.get("exportdir", ".")
    assert Path(config["exportdir"]).is_dir(), "exportdir did not exist, create upfront"

    config["interpolation"] = config.get("interpolation", "cubic")
    assert config["interpolation"] in [
        "linear",
        "cubic",
    ], "Only linear and cubic interpolation is supported"

    if "alias_file" in config:
        assert "alias" not in config, "Do not provide both alias and alias_file"
        try:
            alias_dframe = pd.read_csv(
                config["alias_file"], index_col=config.get("rms_name", "RMS_WELL_NAME")
            )
            config["alias"] = alias_dframe.to_dict()[
                config.get("ecl_name", "ECLIPSE_WELL_NAME")
            ]
            logger.info("Parsed RMS to Eclipse aliases from %s", config["alias_file"])
        except ValueError as err:
            raise ValueError(
                "Could not load RMS-Eclipse well alias file. Check column names"
            ) from err
    else:
        config["alias"] = config.get("alias", {})

    config["welldatefile"] = config.get("welldatefile", "well_date_rft.txt")
    assert isinstance(config["welldatefile"], str), "welldatefile must be a string"

    if "welldatefile" not in config:
        config["welldatefile"] = "well_date_rft.txt"

    config["rft_prefix"] = config.get("rft_prefix", "")
    assert isinstance(config["rft_prefix"], str), "rft_prefix must be a string"

    config["trajectory_name"] = config.get("trajectory_name", "Drilled trajectory")
    assert isinstance(config["trajectory_name"], str), (
        "trajectory_name must be a string"
    )

    return config


def get_well_coords(
    project, wellname: str, trajectory_name: str = "Drilled trajectory"
):
    """Extracts  well coordinates as a (wellpoints, 3) numpy array
    from a ROXAPI RMS project reference.

    Args:
        project: Roxapi project reference.
        wellname: Name of well as it exists in the RMS project
    """
    return (
        project.wells[wellname]
        .wellbore.trajectories[trajectory_name]
        .survey_point_series.get_measured_depths_and_points()
    )


def strictly_downward(coords: np.ndarray) -> bool:
    """Check if a well trajectory has absolutely no horizontal sections

    Args:
        coords: n x 4 array of coordinates, only
            z values in 4th column is used.

    Returns:
        True if there are no horizontals.
    """
    return bool(np.all(coords[:-1, 3] < coords[1:, 3]))


def interp_from_md(
    md_value: float, coords, interpolation: str = "cubic"
) -> Tuple[float, float, float]:
    """
    Function to interpolate East, North, TVD values of a well point
    defined by its name (wname) and its corresponding MD point (md_value).

    The interpolation of the well trajectory will be linear if linear = True,
    using cubic spline otherwise.

    The coords input array should consist of rows::

        md, x, y, z

    Returns:
        x, y and z along the wellpath at requested measured depth value.
    """
    if coords is None:
        raise ValueError("Can't interpolate with no well coordinates")
    if interpolation.lower() == "linear":
        logger.info("Interpolating (linear) East, North, TVD from MD")
        return (
            float(np.interp(md_value, coords[:, 0], coords[:, 1])),
            float(np.interp(md_value, coords[:, 0], coords[:, 2])),
            float(np.interp(md_value, coords[:, 0], coords[:, 3])),
        )
    if interpolation.lower() == "cubic":
        logger.info("Interpolating (cubic spline) East, North, TVD from MD")
        cs_x = CubicSpline(coords[:, 0], coords[:, 1])  # East
        cs_y = CubicSpline(coords[:, 0], coords[:, 2])  # North
        cs_z = CubicSpline(coords[:, 0], coords[:, 3])  # TVD
        return (float(cs_x(md_value)), float(cs_y(md_value)), float(cs_z(md_value)))
    raise ValueError(f"Non-supported interpolation method: {interpolation}")


def interp_from_xyz(
    xyz: Tuple[float, float, float],
    coords: np.ndarray,
    interpolation: str = "cubic",
) -> float:
    """Interpolate MD value of a well point defined by its name (wellname)
    and its corresponding East, North, TVD values (xyz tuple)

    The coords input array should consist of rows::

        md, x, y, z

    The interpolation of the TVD well trajectory will be used
    (with linear algorithm if linear = True, using cubic spline otherwise)
    if the well is strictly going downward (TVD series stricly increasing).

    If the well is horizontal or in a hook shape, a projection of the point
    on the well trajectory will be used, using cubic spline interpolation
    of the well trajectory points.

    Args:
        coords
        xyz: x, y and z for the coordinate where MD is requested.
        interpolation: Use either "cubic" (default) or "linear"

    Returns:
        Measured depth value at (x,y,z)
    """

    # Interpolate to get corresponding MD

    logger.info("Interpolating MD from East, North, TVD")
    if strictly_downward(coords):
        # Interpolation from TVD survey can be used
        if interpolation.lower() == "linear":
            md_value = float(np.interp(xyz[2], coords[:, 3], coords[:, 0]))
        else:
            md_value = float(CubicSpline(coords[:, 3], coords[:, 0])(xyz[2]))
        logger.info("MD estimated on strictly downward wellpath: %s", str(md_value))
        return md_value

    # When the well is not strictly downward MD must be used as a
    # parametrization of the trajectory coordinates (East, North, TVD)

    # RFT pressure point X0(x0,y0,z0) defined by:
    #     x0 = obs['EAST']
    #     y0 = obs['NORTH']
    #     z0 = obs['TVD']

    # distance of point X0 to any point X(x,y,z) of the well trajectory is:
    #     dist(X,X0)  = sqrt[ (x-x0)**2 + (y-y0)**2 + (z-z0)**2 ]
    #     dist(MD,X0) = sqrt[ (f1(MD)-x0)**2 + (f2(MD)-y0)**2 + (f3(MD)-z0)**2 ]

    # We are looking for the point X, belonging to the well, which is the closest
    # from X0, so we want to find the value of MD for which minimizes dist(MD,X0).
    # This MD value is a root of the derivative of the distance. We drop the sqrt()
    # since this is equivalent to minimazing the square of the distance.
    #
    #     d dist(MD,X0) / d MD = 0
    #
    # <=> 2[ (f1(MD)-x0)*f1'(MD) + (f2(MD)-y0)*f2'(MD) + (f3(MD)-z0)*f3'(MD) ] = 0
    #
    # <=> (f1(MD)-x0)*f1'(MD) + (f2(MD)-y0)*f2'(MD) + (f3(MD)-z0)*f3'(MD) = 0
    #
    # using the notation f' for the derivative of function f
    #
    # This can be computed analytically when using polynomial interpolations for
    # f1, f2, f3 (having this function as a new polynom and finding its real roots),
    # but this method is quite unstable depending the degree of the polynom,
    # it may respect the survey points but being quite erratic in-between.
    #
    # Instead, we use cubic spline interpolations which provide a much smoother curve,
    # but we cannot define analytically the sum and multiplication of splines,
    # so we need to compute numerically the distance and find the minimum

    # x = f1(MD) for any point X(x,y,z) of the trajectory defined by MD (x = East)
    poly_x = CubicSpline(coords[:, 0], coords[:, 1])
    # y = f2(MD) for any point X(x,y,z) of the trajectory defined by MD (y = North)
    poly_y = CubicSpline(coords[:, 0], coords[:, 2])
    # z = f3(MD) for any point X(x,y,z) of the trajectory defined by MD (z = TVD)
    poly_z = CubicSpline(coords[:, 0], coords[:, 3])

    # compute the square of the distance every 5 cm MD (can take a couple of seconds)
    step = 0.05
    dist_min = np.inf
    closest_md = None
    for my_md in np.arange(0, coords[-1, 0], step):
        dist = (
            (poly_x(my_md) - xyz[0]) ** 2
            + (poly_y(my_md) - xyz[1]) ** 2
            + (poly_z(my_md) - xyz[2]) ** 2
        )
        if dist < dist_min:
            closest_md = my_md
            dist_min = dist
    dist_min = dist_min ** (0.5)
    if closest_md is not None:
        md_value = round(closest_md, 2)
    logger.info(
        f"MD estimated on undulating wellpath: {md_value} (mismatch = {dist_min:.4f} m)"
    )

    # Alternative using polynoms
    # degree = 7
    # poly_x = np.polyfit(coord[:, 0], coord[:, 1], degree) # x = f1(MD)
    # poly_y = np.polyfit(coord[:, 0], coord[:, 2], degree) # y = f2(MD)
    # poly_z = np.polyfit(coord[:, 0], coord[:, 3], degree) # z = f3(MD)

    # pder_x = np.polyder(poly_x)             # derivative, f1'(MD)
    # pder_y = np.polyder(poly_y)             # derivative, f2'(MD)
    # pder_z = np.polyder(poly_z)             # derivative, f3'(MD)

    # poly_x[-1] = poly_x[-1] - x0            # f1(MD) := f1(MD)-x0
    # poly_y[-1] = poly_y[-1] - y0            # f2(MD) := f2(MD)-y0
    # poly_z[-1] = poly_z[-1] - z0            # f3(MD) := f3(MD)-z0

    # Derivative of the distance function
    # pder_dist  = np.polyadd(np.polyadd(np.polymul(poly_x, pder_x),
    #                                    np.polymul(poly_y, pder_y)),
    #                         np.polymul(poly_z, pder_z))

    # Minimum of the (squared) distance function is the real root of this polynom
    # roots = np.roots(pder_dist)
    # interp_md = roots[np.isreal(roots)].real

    # Only one root should be real
    # assert len(interp_md) == 1, ('0 or more than 1 point have been found ({}) to fit '
    #                              'the well trajectory for this RFT data point!'
    #                              .format(len(interp_md)))

    # md_value = interp_md[0]
    # print('   Methode 3: MD = {}'.format(md_value))

    return md_value


def ertobs_df_to_files(
    dframe: pd.DataFrame,
    exportdir: str = ".",
    welldatefile: str = "well_date_rft.txt",
    filename: str = "rft_ertobs.csv",
) -> None:
    """
    Exports data from a dataframe into ERT observations files.
    The input here is essentially the input dataframe, but where all "holes" in
    MD or XYZ have been filled.

    If ZONE is included, it will be added to the output.

    Gendata will read well_date_rft.txt and then each of the obs and txt files.

    Syntax of the output of the .txt files are determined by semeio:
    https://github.com/equinor/semeio/blob/master/semeio/jobs/rft/utility.py#L21

    semeio.jobs.rft.trajectory.load_from_file() will parse the ``.txt`` files.
    https://github.com/equinor/semeio/blob/master/semeio/jobs/rft/trajectory.py#L273

    This function produces such files::

      <WELL_NAME>.txt  # (for all wells)
      <WELL_NAME>_<REPORT_STEP>.obs
      well_date_rft.txt

    <wellname>.txt is a hardcoded filename pattern in GENDATA_RFT (semeio)
    well_date_rft.txt is supplied as configuration to GENDATA_RFT (semeio)

    The obs-files must match the GENERAL_OBSERVATION arguments in the
    ERT config.

    In the welldatefile, a choice is made by this function on how to
    enumerate the REPORTSTEPS parameter, which is to be given to GENDATA in ERT config.
    Here it will be constructed on the enumeration of DATE for each given well,
    meaning the number will be 1 for the first date for each well, and 2 on the
    second DATE pr. well etc.

    Args:
        dframe: Contains data for RFT observations, one
            observations pr. row
        exportdir: Path to directory where export is to happen. Must
            exists.
        welldatefile: Filename to write the "index" of observations to.
        filename: Filename for raw CSV data, for future use in GENDATA_RFT
    """

    # Dump directly to CSV, this is for future use:
    dframe.to_csv(Path(exportdir) / filename, index=False, header=True)
    logger.info("Written CSV to %s", Path(exportdir) / filename)

    dframe = dframe.copy()  # Since we will modify it.

    if "ZONE" not in dframe:
        dframe["ZONE"] = ""

    dframe["DATE"] = pd.to_datetime(dframe["DATE"])
    dframe["REPORT_STEP"] = (
        dframe.groupby("WELL_NAME")["DATE"]
        .rank(method="dense", ascending=True)
        .astype(int)
    )

    for wellname, wellframe in dframe.groupby("WELL_NAME"):
        traj_filename = Path(exportdir) / (wellname + ".txt")

        well_trajectory = wellframe[
            ["EAST", "NORTH", "MD", "TVD", "ZONE"]
        ].drop_duplicates()

        well_trajectory.to_csv(traj_filename, sep=" ", index=False, header=False)
        logger.info("Written trajectory data to %s", traj_filename)

        for wname_rep_step, well_rep_step_frame in wellframe.groupby("REPORT_STEP"):
            obs_filename = Path(exportdir) / (
                wellname + "_" + str(wname_rep_step) + ".obs"
            )

            # Left join with the well trajectory frame, to ensure we
            # can output -1 for RFT measurements for points that are only
            # active on a subset of the report steps (i.e. dates):
            obs_frame = pd.merge(well_trajectory, well_rep_step_frame, how="left")
            obs_frame["PRESSURE"] = obs_frame["PRESSURE"].fillna(value=-1)
            obs_frame["ERROR"] = obs_frame["ERROR"].fillna(value=0)
            obs_frame[["PRESSURE", "ERROR"]].to_csv(
                obs_filename,
                sep=" ",
                index=False,
                header=False,
            )
            logger.info("Written obs file to %s", obs_filename)

    dframe.groupby(["WELL_NAME", "DATE"])[
        ["WELL_NAME", "DATE", "REPORT_STEP"]
    ].first().to_csv(Path(exportdir) / welldatefile, sep=" ", index=False, header=False)
    logger.info("Written welldata file to %s", Path(exportdir) / welldatefile)
    return dframe


def fill_missing_md_xyz(
    dframe: pd.DataFrame,
    coords_pr_well: Dict[str, np.ndarray],
    interpolation: str = "cubic",
) -> pd.DataFrame:
    """
    Fill missing MD or XYZ values in incoming dataframe, interpolating
    in given well trajectories.

    Args:
        dframe: Must contain WELL_NAME, EAST, NORTH, MD, TVD
        coords_pr_well: One key for each WELL_NAME, pointing to a n by 3
            numpy matrix with well coordinates (as outputted by roxapi)
    """
    for row_idx, row in dframe.iterrows():
        if pd.isnull(row["TVD"]):
            if pd.isnull(row["MD"]):
                logger.error("Both TVD and MD is missing for well %s", row["WELL_NAME"])
            else:
                xyz = interp_from_md(
                    row["MD"],
                    coords_pr_well[row["WELL_NAME"]],
                    interpolation=interpolation,
                )
                dframe.at[row_idx, "EAST"] = xyz[0]
                dframe.at[row_idx, "NORTH"] = xyz[1]
                dframe.at[row_idx, "TVD"] = xyz[2]
        elif pd.isnull(row["MD"]):
            if any(
                (
                    pd.isnull(row["EAST"]),
                    pd.isnull(row["NORTH"]),
                    pd.isnull(row["TVD"]),
                )
            ):
                logger.error(
                    "EAST, NORTH and/or TVD is missing, can't compute MD for well %s",
                    row["WELL_NAME"],
                )
            else:
                xyz = (row["EAST"], row["NORTH"], row["TVD"])
                dframe.at[row_idx, "MD"] = interp_from_xyz(
                    xyz, coords_pr_well[row["WELL_NAME"]], interpolation=interpolation
                )
    return dframe


def store_rft_as_points_inside_project(dframe, project, clipboard_folder):
    """
    Store RFT observations for ERT as points in RMS under Clipboard.
    The points will be stored per zone, well, and year and will include
    useful attributes as pressure, wellname, date etc.
    """

    dframe = dframe.copy()
    dframe["DATE"] = dframe["DATE"].dt.strftime("%Y-%m-%d")

    # create zone mismatch column to include as attribute
    if "rms_cell_zone_str" in dframe:
        dframe["ZONE_MISMATCH"] = np.where(
            dframe["ZONE"] == dframe["rms_cell_zone_str"], 1, 0
        )

    # create points and store in rms
    create_clipboard_points_with_attributes(
        project, "All_RFT_observations", dframe, [clipboard_folder]
    )

    groupby = (col for col in ("ZONE", "YEAR", "WELL_NAME") if col in dframe)
    for col in groupby:
        for name, df in dframe.groupby(col):
            create_clipboard_points_with_attributes(
                project, name, df, [clipboard_folder, f"RFT points by {col}"]
            )

    print(f"Stored RFT points under clipboard folder {clipboard_folder}")


def create_clipboard_points_with_attributes(project, name, df, folder):
    attribute_dtypes = {
        "PRESSURE": float,
        "DATE": str,
        "ZONE": str,
        "WELL_NAME": str,
        "ERROR": float,
        "YEAR": int,
        "ZONE_MISMATCH": int,
    }

    points = project.clipboard.create_points(str(name), folder)

    # set XYZ for the points
    points.set_values(df[["EAST", "NORTH", "TVD"]].to_numpy())

    # set attributes for the points
    for attr, dtype in attribute_dtypes.items():
        if attr in df:
            values = df[attr].values.astype(dtype)
            points.set_attribute_values(attr, values)


def main(config: Optional[Dict[str, Any]] = None) -> None:
    """The main function to be called from a RMS client python script.

    Args:
        config (dict): configuration as a dictionary.

    """
    if config is None:
        config = {}
    config = check_and_parse_config(config)
    if config is None:
        raise ValueError("Configuration is invalid")

    logger.setLevel(config["loglevel"])

    welldatefile = "well_date_rft.txt"

    dframe = config["input_dframe"].copy()
    dframe["WELL_NAME"] = config["rft_prefix"] + dframe["WELL_NAME"]

    no_value = dframe["PRESSURE"].replace("", np.nan).isnull()
    if no_value.any():
        logger.error("PRESSURE missing for some rows:")
        logger.error("\n %s", str(dframe[no_value]))
        raise ValueError("PRESSURE not provided")

    if "project" in config:
        grid_model = config["project"].grid_models[config["gridname"]]
        grid = grid_model.get_grid()
        coords_pr_well = {}
        for well in dframe["WELL_NAME"].unique():
            coords_pr_well[well] = get_well_coords(
                config["project"], well, trajectory_name=config["trajectory_name"]
            )
        dframe = fill_missing_md_xyz(dframe, coords_pr_well)

        dframe["rms_cell_index"] = dframe.apply(
            lambda df: grid.get_cells_at_points([df["EAST"], df["NORTH"], df["TVD"]]),
            axis=1,
        )

    else:
        assert not dframe["MD"].isnull().any() and not dframe["TVD"].isnull().any(), (
            "MD and TVD must be supplied for all points "
            "when there is no RMS project available."
        )

    if "ERROR" not in dframe:
        dframe["ERROR"] = np.nan
    no_error_rows = dframe["ERROR"].replace("", np.nan).isnull()
    if "absolute_error" in config:
        dframe.loc[no_error_rows, "ERROR"] = config["absolute_error"]
    elif "relative_error" in config:
        dframe.loc[no_error_rows, "ERROR"] = (
            config["relative_error"] * dframe["PRESSURE"]
        )
    else:
        if no_error_rows.any():
            logger.error("No ERROR given for some or all points.")
            logger.error(
                "Provide defaults or insert in data table input.\n%s",
                str(dframe[no_error_rows]),
            )
            raise ValueError("ERROR not provided")

    if "ZONE" in dframe and "project" in config:
        cells_outside_grid = dframe["rms_cell_index"].isnull()
        # WARNING: If there are nan's in the dataframe, the dtype of
        # these index columns changes to float

        if cells_outside_grid.any():
            logger.warning("RFT points outside the grid:")
            logger.warning("\n %s", str(dframe[cells_outside_grid]))

        dframe.loc[~cells_outside_grid, "rms_cell_zone_val"] = dframe.loc[
            ~cells_outside_grid, "rms_cell_index"
        ].apply(
            lambda cell_index: grid_model.properties[config["zonename"]].get_values()[
                int(cell_index)
            ]
        )
        # What happens when there is no code_names in the RMS project? Which
        # exception will RMS raise?
        dframe.loc[~cells_outside_grid, "rms_cell_zone_str"] = dframe.loc[
            ~cells_outside_grid, "rms_cell_zone_val"
        ].apply(
            lambda zone_value: grid_model.properties[config["zonename"]].code_names[
                int(zone_value)
            ]
        )

        # Determine points that in the grid are not in the zone provided
        # in the input CSV:
        cells_in_wrong_zone = dframe["rms_cell_zone_str"] != dframe["ZONE"]
        if cells_in_wrong_zone.any():
            logger.warning(
                "Some points are in a different zone in the RMS grid:\n %s",
                str(dframe[cells_in_wrong_zone]),
            )
    elif "ZONE" in dframe:
        logger.warning("Cannot verify zones when no RMS project is provided")

    # Translate all well names according to alias:
    dframe["WELL_NAME"] = dframe["WELL_NAME"].apply(lambda x: config["alias"].get(x, x))

    # Export *.obs, *.txt and well_date_rft.txt
    dframe = ertobs_df_to_files(
        dframe, exportdir=config["exportdir"], welldatefile=welldatefile
    )

    if "project" in config and "clipboard_folder" in config:
        store_rft_as_points_inside_project(
            dframe, config["project"], config["clipboard_folder"]
        )
