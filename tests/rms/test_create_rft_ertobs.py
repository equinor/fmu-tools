"""Testing the script create_rft_ertobs, both unit tests and integration tests"""

import datetime
import logging
import math
import os
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from fmu.tools._common import preserve_cwd
from fmu.tools.rms import create_rft_ertobs
from fmu.tools.rms.create_rft_ertobs import check_and_parse_config

logging.basicConfig(level=logging.INFO)

# Pylint exceptions for the mocked RMS object:
# pylint: disable=too-few-public-methods,no-self-use


class SurveyPointSeries:
    """Object representing all wellpaths in a gridmodel"""

    def __init__(self, wellname):
        self.wellname = wellname

    def get_measured_depths_and_points(self):
        """Return numpy array with coordinates/trajectory for individual wells.

        This mocked function can return some simple predefined wellname, and
        also load some trajectories from disk.

        Format::

            md, east, north, tvd

        """
        mock_coords = {"R-99": np.array([[0, 0, 0, 0], [2000, 0, 0, 2000]])}
        if self.wellname in mock_coords:
            return mock_coords[self.wellname]
        # Try to load coordinates from CSV on disk
        csvfilecandidate = (
            Path(__file__).parent
            / "rft_ertobs_data"
            / "coords"
            / ("coords-" + self.wellname + ".csv")
        )
        if csvfilecandidate.is_file():
            return np.array(pd.read_csv(csvfilecandidate, header=None))
        return None


class Trajectory:
    """Representing one trajectory for one well"""

    def __init__(self, wellname):
        self.wellname = wellname
        self.survey_point_series = SurveyPointSeries(wellname)


class Wellbore:
    """Represent "all" trajectories for one well"""

    def __init__(self, wellname):
        self.wellname = wellname
        self.trajectories = {
            # Add two trajectory name pointing to the same trajectories,
            # which trajectory is in use can be changed on a global basis.
            "Drilled trajectory": Trajectory(wellname),
            "Imported trajectory": Trajectory(wellname),
        }


class Well:
    """Represents a well, with multiple wellbores"""

    def __init__(self, wellname):
        self.wellname = wellname
        self.wellbore = Wellbore(wellname)


class Grid:
    """Represents the grid (geometry) in an RMS model"""

    def __init__(self):
        pass

    def get_cells_at_points(self, xyz):
        """Returns a cell index integer

        Args:
            xyz: List with three elements.

        Returns:
            integer being the cell index. nan if outside the grid.
        """
        # Simple mocked gridmodel, "three" cells, but with large indices.
        if xyz[0] > 1e8:
            return np.nan  # Outside grid
        if xyz[2] >= 1700:
            return 3000  # Volon
        if xyz[2] >= 1650:
            # Return as float, as this can be a later side effect
            # in pandas frames when other cells are np.nan
            return 2000.0  # Therys

        return 1000  # Valysar


class Property:
    """Represents a specific property for cells, here only zone
    values and names are mocked"""

    def __init__(self):
        self.code_names = {1: "Valysar", 2: "Therys", 3: "Volon"}

    def get_values(self):
        """Return a map from cell_index to zone_val"""
        # The mock assumes we have three grid cells, mapped to each zone.
        return {1000: 1, 2000: 2, 3000: 3}


class GridModel:
    """Represents a Gridmodel, that can associated to one grid."""

    def __init__(self):
        self.properties = {"Zone": Property()}

    def get_grid(self):
        """Get the associated grid"""
        return Grid()


class RMSMockedProject:
    """Represent the RMS/roxapi "project" magic variable"""

    def __init__(self):
        self.wells = {
            "R_A2": Well("R_A2"),
            "R_A3": Well("R_A3"),
            "R_A4": Well("R_A4"),
            "R_A5": Well("R_A5"),
            "R_A6": Well("R_A6"),
            "RFT_R_A2": Well("R_A2"),
            "RFT_R_A3": Well("R_A3"),
            "RFT_R_A4": Well("R_A4"),
            "RFT_R_A5": Well("R_A5"),
            "RFT_R_A6": Well("R_A6"),
            "RFT_55_33-A-2": Well("R_A2"),
            "RFT_55_33-A-3": Well("R_A3"),
            "RFT_55_33-A-4": Well("R_A4"),
            "RFT_55_33-A-5": Well("R_A5"),
            "RFT_55_33-A-6": Well("R_A6"),
            "R-99": Well("R-99"),
        }
        self.grid_models = {"Simgrid": GridModel()}


def test_get_well_coords():
    """Reliance on this test depends on whether the mocked
    RMS project resembles the real ROXAPI.
    """
    rms_project_mock = RMSMockedProject()

    assert (
        create_rft_ertobs.get_well_coords(rms_project_mock, "R-99")
        == np.array([[0, 0, 0, 0], [2000, 0, 0, 2000]])
    ).all()

    # Alternative trajectory name in RMS:
    assert (
        create_rft_ertobs.get_well_coords(
            rms_project_mock, "R-99", trajectory_name="Imported trajectory"
        )
        == np.array([[0, 0, 0, 0], [2000, 0, 0, 2000]])
    ).all()

    with pytest.raises(KeyError):
        create_rft_ertobs.get_well_coords(
            rms_project_mock, "R-99", trajectory_name="Bogus traj-name"
        )


@pytest.mark.parametrize(
    "coords, expected",
    [
        (np.array([[0, 0, 0, 0]]), True),
        (np.array([[0, 0, 0, 0], [1, 0, 0, 1]]), True),
        (np.array([[0, 0, 0, 0], [1, 0, 0, 1], [2, 0, 0, 1]]), False),
        (np.array([[0, 0, 0, 0], [1, 0, 0, 1], [2, 0, 0, 0]]), False),
        (np.array([[0, 0, 0, 0], [1, 0, 0, 1], [1.001, 0, 0, 0.999]]), False),
    ],
)
def test_strictly_downward(coords, expected):
    """Test that we can determine if wells go strictly downwards"""
    assert create_rft_ertobs.strictly_downward(coords) == expected


def test_interp_from_md():
    """Test interpolation along a wellpath from MD to XYZ"""
    coords = np.array([[0, 0, 0, 0], [1, 0, 0, 1]])
    assert create_rft_ertobs.interp_from_md(0.5, coords, interpolation="linear") == (
        0,
        0,
        0.5,
    )
    assert create_rft_ertobs.interp_from_md(0.5, coords, interpolation="cubic") == (
        0,
        0,
        0.5,
    )


def test_interp_from_xyz():
    """Test interpolation along a wellpath from XYZ to MD"""
    coords = np.array([[0, 0, 0, 0], [1, 0, 0, 1]])
    assert create_rft_ertobs.interp_from_xyz((0, 0, 0.5), coords) == 0.5

    # A wellpath going straight down, and then up again at 45 degrees:
    coords = np.array([[0, 0, 0, 0], [1, 0, 0, 1], [1 + math.sqrt(2), 1, 0, 0]])
    assert (
        create_rft_ertobs.interp_from_xyz((0, 0, 0.5), coords, interpolation="linear")
        == 0.35  # verify this number
    )
    assert (
        create_rft_ertobs.interp_from_xyz(
            (0.5, 0.0, 0.5), coords, interpolation="linear"
        )
        == 2.0  # verify this number
    )


@preserve_cwd
def test_ertobs_df_to_files_1(tmpdir):
    """Test the writing of obs and txt files to disk, from a dataframe"""
    tmpdir.chdir()
    ertobs_df = pd.DataFrame(
        [
            {
                "WELL_NAME": "R-99",
                "DATE": datetime.date(2020, 6, 1),
                "EAST": 5555,
                "NORTH": 7777,
                "TVD": 2300,
                "MD": 2400,
                "ZONE": "Valyzar",
                "PRESSURE": 100,
                "ERROR": 3,
            }
        ]
    )
    create_rft_ertobs.ertobs_df_to_files(ertobs_df, tmpdir)
    assert Path("R-99.txt").read_text().strip() == "5555 7777 2400 2300 Valyzar"
    assert Path("R-99_1.obs").read_text().strip() == "100 3"
    assert Path("well_date_rft.txt").read_text().strip() == "R-99 2020-06-01 1"

    # Check that the file rft_ertobs.csv was created, this file
    # is for future use.
    pd.testing.assert_frame_equal(
        ertobs_df.astype(str),
        pd.read_csv(Path("rft_ertobs.csv")).astype(str),
    )


@preserve_cwd
def test_main_mock_drogon(tmpdir):
    """Check that the code when executed on the Drogon case provides a
    predefined set of files (that has been manually verified)"""
    tmpdir.chdir()
    tmpdir.mkdir("exports")
    config = {
        "input_file": Path(__file__).parent / "rft_ertobs_data/input_table_drogon.csv",
        "exportdir": "exports",
        "project": RMSMockedProject(),
        "gridname": "Simgrid",
        "zonename": "Zone",
        "alias_file": Path(__file__).parent / "rft_ertobs_data/rms_eclipse.csv",
        "ecl_name": "ECLIPSE_WELL_NAME",
        "rms_name": "RMS_WELL_NAME",
    }
    create_rft_ertobs.main(config)

    expected_files_dir = Path(__file__).parent / "rft_ertobs_data" / "expected_files"
    for filename in (
        list(expected_files_dir.glob("R*obs"))
        + list(expected_files_dir.glob("R*.txt"))
        + [
            Path(__file__).parent
            / "rft_ertobs_data"
            / "expected_files"
            / "well_date_rft.txt"
        ]
    ):
        assert (Path("exports") / Path(filename)).is_file()
        pd.testing.assert_frame_equal(
            # Generated by code:
            pd.read_csv(
                Path("exports") / (Path(filename).name),
                sep=r"\s+",
                index_col=None,
                header=None,
            ),
            # Reference/expected data:
            pd.read_csv(filename, sep=r"\s+", index_col=None, header=None),
            check_dtype=False,
        )
    assert Path("exports/well_date_rft.txt").is_file()


@preserve_cwd
def test_alternative_trajectory_name(tmpdir):
    """Test that we can use a different trajectory in RMS, but it has to be
    the same for all wells"""
    tmpdir.chdir()
    tmpdir.mkdir("exports")
    config = {
        "input_file": Path(__file__).parent / "rft_ertobs_data/input_table_drogon.csv",
        "exportdir": "exports",
        "project": RMSMockedProject(),
        "gridname": "Simgrid",
        "zonename": "Zone",
        "trajectory_name": "Imported trajectory",
    }
    create_rft_ertobs.main(config)
    assert not pd.read_csv(Path("exports") / "rft_ertobs.csv").empty

    # Check that we fail when the trajectory is wrongly named:
    config["trajectory_name"] = "fooo"
    with pytest.raises(KeyError):
        create_rft_ertobs.main(config)


@preserve_cwd
def test_main_no_rms(tmpdir):
    """Test that if we have a full CSV file with all values we don't need
    the RMS project"""
    tmpdir.chdir()

    input_dframe = pd.DataFrame(
        data=[
            {
                "DATE": "2099-01-01",
                "WELL_NAME": "A-1",
                "MD": 4,
                "EAST": 1,
                "NORTH": 2,
                "TVD": 3,
                "PRESSURE": 100,
                "ERROR": 5,
            }
        ]
    )

    config = {"input_dframe": input_dframe}
    create_rft_ertobs.main(config)
    assert (
        pd.read_csv("A-1.txt", sep=r"\s+", index_col=None, header=None).iloc[0].values
        == [1, 2, 4, 3]
    ).all()
    assert (
        pd.read_csv("A-1_1.obs", sep=r"\s+", index_col=None, header=None).iloc[0].values
        == [100, 5]
    ).all()
    assert Path("well_date_rft.txt").read_text().strip() == "A-1 2099-01-01 1"


@preserve_cwd
@pytest.mark.parametrize(
    "data, expected_error",
    [
        ({"PRESSURE": ""}, "PRESSURE not provided"),
        ({"PRESSURE": np.nan}, "PRESSURE not provided"),
        ({"ERROR": np.nan}, "ERROR not provided"),
        ({"ERROR": ""}, "ERROR not provided"),
    ],
)
def test_missing_dframe_data(data, expected_error, tmpdir):
    """Test error message when something is missing in the input dataframe"""
    tmpdir.chdir()
    dframe_dict = {
        "DATE": "2099-01-01",
        "WELL_NAME": "A-1",
        "MD": 4,
        "EAST": 1,
        "NORTH": 2,
        "TVD": 3,
        "PRESSURE": "100",
        "ERROR": 5,
    }
    dframe_dict.update(data)
    with pytest.raises(ValueError, match=expected_error):
        create_rft_ertobs.main({"input_dframe": pd.DataFrame(data=[dframe_dict])})


@preserve_cwd
def test_absolute_error(tmpdir):
    """Test that we can specify absolute_error in the config"""
    tmpdir.chdir()
    dframe_dict = {
        "DATE": "2099-01-01",
        "WELL_NAME": "A-1",
        "MD": 4,
        "EAST": 1,
        "NORTH": 2,
        "TVD": 3,
        "PRESSURE": "100",
    }
    create_rft_ertobs.main(
        {"input_dframe": pd.DataFrame(data=[dframe_dict]), "absolute_error": 4}
    )
    assert (
        pd.read_csv("A-1_1.obs", sep=r"\s+", index_col=None, header=None).iloc[0].values
        == [100, 4]
    ).all()


@preserve_cwd
def test_absolute_error_ignored(tmpdir):
    """Test that we can absolute_error in the config is ignored if ERROR is specified"""
    tmpdir.chdir()
    dframe_dict = {
        "DATE": "2099-01-01",
        "WELL_NAME": "A-1",
        "MD": 4,
        "EAST": 1,
        "NORTH": 2,
        "TVD": 3,
        "PRESSURE": "100",
        "ERROR": 5,
    }
    create_rft_ertobs.main(
        {"input_dframe": pd.DataFrame(data=[dframe_dict]), "absolute_error": 4}
    )
    assert (
        pd.read_csv("A-1_1.obs", sep=r"\s+", index_col=None, header=None).iloc[0].values
        == [100, 5]
    ).all()


@preserve_cwd
def test_configparsing(tmpdir, caplog):
    """Test that the function that validates and parses the config dictionary
    gives correct error messages, and returns a dict with defaults filled in"""

    with pytest.raises(TypeError):
        # pylint: disable=no-value-for-parameter
        check_and_parse_config()
    with pytest.raises(AssertionError):
        check_and_parse_config({})

    with pytest.raises(ValueError, match="Missing columns"):
        check_and_parse_config({"input_dframe": pd.DataFrame()})

    minimal_config = {
        "input_dframe": pd.DataFrame(
            columns=["DATE", "MD", "WELL_NAME", "PRESSURE"],
            data=[[np.datetime64(datetime.date(2020, 3, 12)), 1000, "C-19", 222]],
        )
    }

    processed_df = check_and_parse_config(minimal_config)["input_dframe"]
    tmpdir.chdir()

    # Dump the dataframe to CSV and reload as disk dataframe:
    processed_df.to_csv("tmp.csv", index=False)
    viadisk_df = check_and_parse_config({"input_file": "tmp.csv"})["input_dframe"]
    pd.testing.assert_frame_equal(processed_df, viadisk_df, check_dtype=False)

    with pytest.raises(ValueError):
        check_and_parse_config(
            {"input_dframe": pd.DataFrame(), "input_file": "tmp.csv"}
        )

    check_and_parse_config({**minimal_config, "foobar": "com"})
    assert "Unknown options ignored: {'foobar'}" in caplog.text

    assert check_and_parse_config(minimal_config)["exportdir"] == "."

    with pytest.raises(
        AssertionError, match="Only linear and cubic interpolation is supported"
    ):
        check_and_parse_config({**minimal_config, "interpolation": "bilinear"})

    with pytest.raises(AssertionError, match="create upfront"):
        check_and_parse_config({**minimal_config, "exportdir": "nonexistingdir"})

    assert check_and_parse_config(minimal_config)["welldatefile"] == "well_date_rft.txt"


@preserve_cwd
def test_date_parsing(tmpdir):
    """Check that the ambiguous "DD MM YYYY" date format
    can be parsed "correctly" in input CSV files."""
    tmpdir.chdir()
    pd.DataFrame(
        columns=["DATE", "MD", "WELL_NAME", "PRESSURE"],
        data=[["2009-03-01", "100", "A-1", "123"]],
    ).to_csv("inputframe.csv", header=True, index=False)

    minimal_config = {"input_file": "inputframe.csv"}
    processed_config = check_and_parse_config(minimal_config)
    assert processed_config["input_dframe"]["DATE"].values[0] == np.datetime64(
        datetime.date(2009, 3, 1)
    )


@preserve_cwd
def test_parse_alias_config(tmpdir):
    """Test that alias files can be parsed"""
    tmpdir.chdir()
    minimal_config = {
        "input_dframe": pd.DataFrame(columns=["DATE", "MD", "WELL_NAME", "PRESSURE"])
    }

    # Alias is defaulted to empty dict
    assert check_and_parse_config(minimal_config)["alias"] == {}

    # Empty alias dict ok to submit:
    check_and_parse_config({**minimal_config, "alias": {}})

    assert (
        check_and_parse_config({**minimal_config, "alias": {"foo": "bar"}})["alias"][
            "foo"
        ]
        == "bar"
    )

    # First with no header
    alias_dframe = pd.DataFrame(data=[["NO 33/44 A-1", "A-1"], ["NO 33/44 A-2", "A-2"]])
    alias_dframe.to_csv("alias.csv", index=False)
    with pytest.raises(ValueError):
        # pylint: disable=expression-not-assigned
        check_and_parse_config({**minimal_config, "alias_file": "alias.csv"})["alias"]

    # Use default header names
    alias_dframe = pd.DataFrame(
        columns=["RMS_WELL_NAME", "ECLIPSE_WELL_NAME"],
        data=[["NO 33/44 A-1", "A-1"], ["NO 33/44 A-2", "A-2"]],
    )
    alias_dframe.to_csv("alias.csv", index=False)
    assert (
        check_and_parse_config({**minimal_config, "alias_file": "alias.csv"})["alias"][
            "NO 33/44 A-1"
        ]
        == "A-1"
    )

    # Use custom header names for alias:
    alias_dframe = pd.DataFrame(
        columns=["RMS_NAME", "ECLIPSE_NAME"],
        data=[["NO 33/44 A-1", "A-1"], ["NO 33/44 A-2", "A-2"]],
    )
    alias_dframe.to_csv("alias.csv", index=False)
    assert (
        check_and_parse_config(
            {
                **minimal_config,
                "alias_file": "alias.csv",
                "rms_name": "RMS_NAME",
                "ecl_name": "ECLIPSE_NAME",
            }
        )["alias"]["NO 33/44 A-1"]
        == "A-1"
    )


@preserve_cwd
@pytest.mark.parametrize("rftzone", [("Volon"), ("Nansen")])
def test_zones(rftzone, tmpdir, caplog):
    """Test that a warning is emitted for RFT observations that in the RMS grid
    has ended up in a different zone than the one requested in the input"""
    tmpdir.chdir()
    dframe_dict = {
        "DATE": "2099-01-01",
        "WELL_NAME": "R-99",
        "MD": 1900,
        "EAST": 0,
        "NORTH": 0,
        "TVD": 1900,
        "PRESSURE": "100",
        "ERROR": 5,
    }
    dframe_dict.update({"ZONE": rftzone})
    create_rft_ertobs.main(
        {
            "input_dframe": pd.DataFrame(data=[dframe_dict]),
            "project": RMSMockedProject(),
            "gridname": "Simgrid",
            "zonename": "Zone",
        }
    )
    # The zone in the RMS grid is set to Volon in the mocked RMS project.
    if rftzone == "Volon":
        assert "Some points are in a different zone in the RMS grid" not in caplog.text
    else:
        assert "Some points are in a different zone in the RMS grid" in caplog.text


@preserve_cwd
def test_rft_outside_grid(tmp_path, caplog):
    """Test behaviour when points are outside the grid."""
    os.chdir(tmp_path)
    dframe_dict = {
        "DATE": "2099-01-01",
        "WELL_NAME": "R-99",
        "MD": 4,
        "EAST": 1e10,
        "NORTH": 2,
        "TVD": 3,
        "PRESSURE": "100",
        "ERROR": 5,
        "ZONE": "Volon",  # Presence of this give a warning when grid is not supplied
    }
    create_rft_ertobs.main({"input_dframe": pd.DataFrame(data=[dframe_dict])})

    assert "Cannot verify zones when no RMS project is provided" in caplog.text

    # No problems in this script.
    # These data points will be ignored later with GENDATA_RFT.
    assert (
        pd.read_csv("R-99.txt", sep=r"\s+", index_col=None, header=None).iloc[0].values
        == np.array([1e10, 2, 4, 3, "Volon"], dtype="object")
    ).all()


@preserve_cwd
def test_rft_outside_grid_with_zone(tmp_path, caplog):
    """Test behaviour when points are outside the grid and we try
    to match with a zone (which can't be done when the point is outside the grid).
    """
    os.chdir(tmp_path)
    dframe_dict = {
        "DATE": "2099-01-01",
        "WELL_NAME": "R-99",
        "MD": 4,
        "EAST": 1e10,
        "NORTH": 2,
        "TVD": 3,
        "PRESSURE": "100",
        "ERROR": 5,
        "ZONE": "Volon",
    }

    create_rft_ertobs.main(
        {
            "input_dframe": pd.DataFrame(data=[dframe_dict]),
            "project": RMSMockedProject(),
            "gridname": "Simgrid",
            "zonename": "Zone",
        }
    )
    # The script only warns about the situation.
    assert "RFT points outside the grid" in caplog.text

    # Output files are still written with the data. GENDATA_RFT is responsible
    # for ignoring the observation as it will not be able to find the cell index for
    # it.
    assert (
        pd.read_csv("R-99.txt", sep=r"\s+", index_col=None, header=None).iloc[0].values
        == np.array([1e10, 2, 4, 3, "Volon"], dtype="object")
    ).all()


@preserve_cwd
def test_report_step_same_xyz(tmpdir):
    """For wells with RFT observations at multiple dates, the REPORT_STEP
    parameter must be set to something unique, the current code enumerates it
    from 1 and up. This test is with a measurement repeated in the same point"""
    tmpdir.chdir()
    obs_1 = {
        "DATE": "2000-01-01",
        "WELL_NAME": "R-99",
        "MD": 1900,
        "EAST": 0,
        "NORTH": 0,
        "TVD": 1900,
        "PRESSURE": "100",  # (here we also test that strings go well)
        "ERROR": 5,
    }
    obs_2 = obs_1.copy()
    obs_2.update({"DATE": "2010-01-01", "PRESSURE": 90})
    create_rft_ertobs.main(
        {
            "input_dframe": pd.DataFrame(data=[obs_1, obs_2]),
        }
    )

    # RFT at multiple dates but at the same point in the reservoir should only have
    # one point in the trajectory file:
    pd.testing.assert_frame_equal(
        pd.read_csv(Path("R-99.txt"), sep=r"\s+", header=None),
        pd.DataFrame([[0, 0, 1900, 1900]]),
    )

    # But there must be multiple observation files, coupled with REPORT_STEP.
    print(pd.read_csv(Path("R-99_1.obs"), sep=r"\s+", header=None))
    pd.testing.assert_frame_equal(
        pd.read_csv(Path("R-99_1.obs"), sep=r"\s+", header=None),
        pd.DataFrame([[100, 5]]),
    )
    pd.testing.assert_frame_equal(
        pd.read_csv(Path("R-99_2.obs"), sep=r"\s+", header=None),
        pd.DataFrame([[90, 5]]),
    )

    # Check that we get REPORT_STEP 1 for the first date, and 2 for the second:
    pd.testing.assert_frame_equal(
        pd.read_csv(Path("well_date_rft.txt"), sep=r"\s+", header=None),
        pd.DataFrame([["R-99", "2000-01-01", 1], ["R-99", "2010-01-01", 2]]),
    )


@preserve_cwd
def test_report_step_different_xyz(tmpdir):
    """Multiple dates for a well at different xyz.

    This requires a setup compatible with GENDATA_RFT in semeio and GEN_DATA in ERT.

    See also:
    https://github.com/equinor/semeio/blob/master/tests/jobs/rft/test_gendata_rft.py
    """
    tmpdir.chdir()
    obs_1 = {
        "DATE": "2000-01-01",
        "WELL_NAME": "R-99",
        "MD": 1900,
        "EAST": 0,
        "NORTH": 0,
        "TVD": 1900,
        "PRESSURE": "100",  # (here we also test that strings go well)
        "ERROR": 5,
    }
    obs_2 = obs_1.copy()
    obs_2.update({"DATE": "2010-01-01", "PRESSURE": 90, "TVD": 1920, "MD": 1920})
    create_rft_ertobs.main(
        {
            "input_dframe": pd.DataFrame(data=[obs_1, obs_2]),
        }
    )

    # Both points should be mentioned:
    pd.testing.assert_frame_equal(
        pd.read_csv(Path("R-99.txt"), sep=r"\s+", header=None),
        pd.DataFrame([[0, 0, 1900, 1900], [0, 0, 1920, 1920]]),
    )

    # But there must be multiple observation files, and points with no data
    # must be padded with -1, and filename coupled with REPORT_STEP.
    pd.testing.assert_frame_equal(
        pd.read_csv(Path("R-99_1.obs"), sep=r"\s+", header=None),
        pd.DataFrame([[100, 5.0], [-1, 0.0]]),
    )
    pd.testing.assert_frame_equal(
        pd.read_csv(Path("R-99_2.obs"), sep=r"\s+", header=None),
        pd.DataFrame([[-1, 0.0], [90, 5.0]]),
    )

    # Check that we get REPORT_STEP 1 for the first date, and 2 for the second:
    pd.testing.assert_frame_equal(
        pd.read_csv(Path("well_date_rft.txt"), sep=r"\s+", header=None),
        pd.DataFrame([["R-99", "2000-01-01", 1], ["R-99", "2010-01-01", 2]]),
    )
