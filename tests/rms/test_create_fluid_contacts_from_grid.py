from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
import xtgeo

from fmu.tools.rms.fluid_contacts_from_grid import (
    FluidContact,
    _create_contact_surface,
    _filter_to_closest_contact_cell_in_pillars,
    _filter_to_deepest_cell_above_contact_in_pillars,
    _GridDataAssembler,
    _RMSDataLoader,
    create_fluid_contacts_from_grid,
)

SUBGRIDS = {
    "ZONE1": [1, 2, 3],
    "ZONE2": [4, 5],
}


@pytest.fixture
def grid():
    grid = xtgeo.create_box_grid(
        (5, 5, 5), origin=(0, 0, 2000), increment=(100, 100, 10)
    )
    grid.subgrids = SUBGRIDS
    return grid


@pytest.fixture
def contact_property():
    return xtgeo.GridProperty(ncol=5, nrow=5, nlay=5, name="FWL", values=3000)


@pytest.fixture
def zone_property():
    zone_prop = xtgeo.GridProperty(ncol=5, nrow=5, nlay=5, name="Zone", values=1)
    zone_prop.values[:, :, 3:] = 2  # different zone in two upper layers
    zone_prop.codes = {1: "ZONE1", 2: "ZONE2"}
    return zone_prop


@pytest.fixture
def mock_project():
    mock_project = MagicMock()
    mock_project.grid_models = {"mygrid": MagicMock(properties=["FWL", "Zone"])}
    return mock_project


@pytest.fixture
def mock_loader(mock_project, grid, contact_property, zone_property):
    """Create a mock RMS data loader."""
    loader = _RMSDataLoader(mock_project, "mygrid")
    loader.load_grid = MagicMock(return_value=grid)
    loader.load_property = MagicMock(
        side_effect=lambda name: contact_property if name == "FWL" else zone_property
    )
    return loader


@pytest.fixture
def grid_data_assembler(mock_loader):
    """Create a GridDataAssembler instance for testing."""
    contacts = [FluidContact(name="FWL", type="fwl")]
    return _GridDataAssembler(
        loader=mock_loader,
        contacts=contacts,
        zone_name="Zone",
    )


def test_get_grid_dataframe_includes_properties(grid_data_assembler):
    """Test the creation of a dataframe from the grid."""
    df = grid_data_assembler.get_dataframe()
    assert not df.empty
    # check that the added property are present in the dataframe
    assert "fwl" in df.columns
    assert "Zone" in df.columns


def test_grid_data_assembler_get_surface(grid_data_assembler):
    """Test the retrieval of a surface from the grid."""
    surf = grid_data_assembler.get_surface_with_grid_dimensions()
    assert isinstance(surf, xtgeo.RegularSurface)

    grid = grid_data_assembler.grid
    grid_geometrics = grid.get_geometrics(return_dict=True)
    assert surf.xinc == grid_geometrics["avg_dx"]
    assert surf.yinc == grid_geometrics["avg_dy"]
    assert surf.get_rotation() == grid_geometrics["avg_rotation"]


def test_grid_data_assembler_zone_codenames(grid_data_assembler):
    """Test getting zone codenames from GridDataAssembler."""
    zone_codenames = grid_data_assembler.zone_codenames
    assert zone_codenames == {1: "ZONE1", 2: "ZONE2"}


def test_filter_to_closest_contact_cell_in_pillars():
    """Test the filtering of the closest contact cell in each pillar."""
    df = pd.DataFrame(
        {
            "IX": [0, 0, 1, 1],
            "JY": [0, 0, 1, 1],
            "Z_TVDSS": [1000, 1100, 1200, 1300],
            "FWL": [1200, 1200, 1210, 1210],
        }
    )
    filtered_df = _filter_to_closest_contact_cell_in_pillars(df, "FWL")
    assert len(filtered_df) == 2
    # closest cell in first pillar is 100 m away from the contact
    # closest cell in second pillar is 10 m away from the contact
    assert list(filtered_df["abs_diff"]) == [100, 10]


def test_filter_to_deepest_cell_above_contact_in_pillars():
    """Test the filtering of the deepest cell above the contact in each pillar."""
    df = pd.DataFrame(
        {
            "IX": [0, 0, 1, 1],
            "JY": [0, 0, 1, 1],
            "Z_TVDSS": [1000, 1100, 1200, 1300],
            "FWL": [1000, 1150, 1200, 1350],
            "KZ": [1, 2, 3, 4],
        }
    )
    # without min_value_filter
    filtered_df = _filter_to_deepest_cell_above_contact_in_pillars(
        df, "FWL", min_value_filter=0
    )
    assert len(filtered_df) == 2
    assert list(filtered_df["KZ"]) == [2, 4]

    # with min_value_filter
    filtered_df = _filter_to_deepest_cell_above_contact_in_pillars(
        df,
        "FWL",
        min_value_filter=1150,
    )
    # should only return data from the second pillar
    assert len(filtered_df) == 1
    assert list(filtered_df["KZ"]) == [4]


def test_create_contact_surface(grid_data_assembler):
    """Test the creation of a contact surface from the grid."""
    df = grid_data_assembler.get_dataframe()
    df = df[df["Zone"] == 1]

    # Adjust the contact values for testing
    # pretend each col is a different region
    df.loc[df["IX"] == 1, "FWL"] = 1000
    df.loc[df["IX"] == 2, "FWL"] = 2000
    df.loc[df["IX"] == 3, "FWL"] = 3000
    df.loc[df["IX"] == 4, "FWL"] = 4000
    df.loc[df["IX"] == 5, "FWL"] = 5000

    surf_from_grid = grid_data_assembler.get_surface_with_grid_dimensions()

    # Create the contact surface
    surface = _create_contact_surface(df, "FWL", 0, surf_from_grid)

    assert surface is not None
    assert isinstance(surface, xtgeo.RegularSurface)

    assert (surface.values[0, :] == 1000).all()
    assert (surface.values[1, :] == 2000).all()
    assert (surface.values[2, :] == 3000).all()
    assert (surface.values[3, :] == 4000).all()
    assert (surface.values[4, :] == 5000).all()

    assert surface.xinc == surf_from_grid.xinc
    assert surface.yinc == surf_from_grid.yinc
    assert surface.get_rotation() == surf_from_grid.get_rotation()


def test_rms_data_loader_find_available_contact_properties(mock_loader):
    """Test finding available contact properties using RMSDataLoader."""
    mock_loader.project.grid_models["mygrid"] = MagicMock(properties=["myfwl", "mygwc"])

    # GWC is not present in the grid model
    contacts = mock_loader.find_available_contact_properties("myfwl", "GOC", "mygwc")
    assert len(contacts) == 2
    assert contacts[0].name == "myfwl"
    assert contacts[0].type == "fwl"
    assert contacts[1].name == "mygwc"
    assert contacts[1].type == "gwc"


def test_rms_data_loader_raises_error_when_no_contacts_found(mock_loader):
    """Test that RMSDataLoader raises error when no contacts are found."""
    mock_loader.project.grid_models["mygrid"] = MagicMock(properties=["myfwl", "mygwc"])

    with pytest.raises(ValueError, match="None of the contact properties"):
        mock_loader.find_available_contact_properties("OWC", "GOC", "GWC")


def test_create_fluid_contacts_from_grid(mock_loader):
    """Test the creation of fluid contacts from grid."""
    with (
        patch(
            "fmu.tools.rms.fluid_contacts_from_grid._RMSDataLoader",
            return_value=mock_loader,
        ),
        patch.object(xtgeo.RegularSurface, "to_roxar") as mock_surface_to_roxar,
        patch.object(xtgeo.Polygons, "to_roxar") as mock_polygons_to_roxar,
    ):
        create_fluid_contacts_from_grid(
            project=mock_project,
            grid_name="mygrid",
            fwl_name="FWL",
            zone_name="Zone",
            grid_refinement=2,
        )

    mock_loader.load_grid.assert_called_once()
    mock_loader.load_property.assert_any_call("Zone")
    mock_loader.load_property.assert_any_call("FWL")

    # check that surfaces was created for both zones
    mock_surface_to_roxar.assert_any_call(
        mock_project, "ZONE1", "fluid_contact_surfaces/fwl", stype="general2d_data"
    )
    mock_surface_to_roxar.assert_any_call(
        mock_project, "ZONE2", "fluid_contact_surfaces/fwl", stype="general2d_data"
    )

    # check that polygons was created for both zones
    mock_polygons_to_roxar.assert_any_call(
        mock_project, "ZONE1", "fluid_contact_outlines/fwl", stype="general2d_data"
    )
    mock_polygons_to_roxar.assert_any_call(
        mock_project, "ZONE2", "fluid_contact_outlines/fwl", stype="general2d_data"
    )
