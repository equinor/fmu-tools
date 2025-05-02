from unittest.mock import MagicMock

import pandas as pd
import pytest
import xtgeo

from fmu.tools.rms.create_fluid_contacts_from_grid import (
    _create_contact_surface,
    _filter_to_closest_contact_cell_in_pillars,
    _filter_to_deepest_cell_above_contact_in_pillars,
    _get_available_contact_properties,
    _GridProcessor,
)

SUBGRIDS = {
    "ZONE1": [1, 2, 3],
    "ZONE2": [4, 5],
}


@pytest.fixture
def mock_project():
    project = MagicMock()
    project.grid_models = {"test_grid": MagicMock(properties=["FWL", "GOC"])}
    return project


@pytest.fixture
def mock_contact_param():
    return xtgeo.GridProperty(ncol=3, nrow=3, nlay=5, name="FWL", values=1000)


@pytest.fixture
def mock_grid(mock_contact_param):
    grid = xtgeo.create_box_grid(
        (3, 3, 5), origin=(0, 0, 2000), increment=(100, 100, 10)
    )
    grid.subgrids = SUBGRIDS
    grid.append_prop(mock_contact_param)
    return grid


def test_grid_processor_dataframe(mock_grid):
    """Test the creation of a dataframe from the grid."""
    processor = _GridProcessor(mock_grid)
    df = processor.dataframe
    assert not df.empty
    # check that the added property are present in the dataframe
    assert "FWL" in df.columns


def test_grid_processor_get_surface(mock_grid):
    """Test the retrieval of a surface from the grid."""
    processor = _GridProcessor(mock_grid)
    surf = processor.get_surface_with_grid_dimension()
    assert isinstance(surf, xtgeo.RegularSurface)

    grid_geometrics = processor.grid.get_geometrics(return_dict=True)
    assert surf.xinc == grid_geometrics["avg_dx"]
    assert surf.yinc == grid_geometrics["avg_dy"]
    assert surf.get_rotation() == grid_geometrics["avg_rotation"]


def test_grid_processor_get_layers_per_zone(mock_grid):
    """Test the retrieval of layers for each zone."""
    processor = _GridProcessor(mock_grid)
    layers = processor.get_layerlist_for_zones()
    assert layers == SUBGRIDS


def test_grid_processor_get_layers_per_coarse_zone(mock_grid):
    """Test the retrieval of layers for a coarse zone."""
    processor = _GridProcessor(mock_grid)
    coarse_zone = {"MERGED": ["ZONE1", "ZONE2"]}
    layers = processor.get_layerlist_for_zones(coarse_zone)
    expected_layers = {"MERGED": [1, 2, 3, 4, 5]}
    assert layers == expected_layers


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


def test_create_contact_surface(mock_grid):
    """Test the creation of a contact surface from the grid."""
    processor = _GridProcessor(mock_grid)
    df = processor.dataframe.copy()

    # Adjust the contact values for testing
    # pretend each col is a different region
    df.loc[df["JY"] == 1, "FWL"] = 1000
    df.loc[df["JY"] == 2, "FWL"] = 2000
    df.loc[df["JY"] == 3, "FWL"] = 3000

    surf_from_grid = processor.get_surface_with_grid_dimension()

    # Create the contact surface
    surface = _create_contact_surface(df, "FWL", 0, surf_from_grid)

    assert surface is not None
    assert isinstance(surface, xtgeo.RegularSurface)

    assert (surface.values[:, 0] == 1000).all()
    assert (surface.values[:, 1] == 2000).all()
    assert (surface.values[:, 2] == 3000).all()

    assert surface.xinc == surf_from_grid.xinc
    assert surface.yinc == surf_from_grid.yinc
    assert surface.get_rotation() == surf_from_grid.get_rotation()


def test_get_available_contact_properties(mock_project):
    contacts = _get_available_contact_properties(
        mock_project, "test_grid", "FWL", "GOC"
    )
    assert len(contacts) == 2
    assert contacts[0].name == "FWL"
    assert contacts[0].type == "fwl"
    assert contacts[1].name == "GOC"
    assert contacts[1].type == "goc"
