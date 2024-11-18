import logging

import numpy as np
import pytest
import xtgeo

from fmu.tools import sample_attributes_for_sim2seis
from fmu.tools.utilities.sample_attributes import Attrs, _get_layer

logger = logging.getLogger(__name__)


@pytest.fixture(scope="module", name="local_testdata")
def fixture_testdata(testdata_path):
    """Read test data from file as fixture."""
    gpath = testdata_path / "3dgrids/drogon/4/simgrid_with_region_zone_attr.roff"

    grid = xtgeo.grid_from_file(gpath)
    region = xtgeo.gridproperty_from_file(gpath, name="Region")
    attr = xtgeo.gridproperty_from_file(gpath, name="MyAttr")
    zone = xtgeo.gridproperty_from_file(gpath, name="Zone")

    attr_surface = xtgeo.surface_from_grid3d(grid, property=attr, rfactor=4)

    return grid, region, zone, attr_surface


@pytest.mark.parametrize(
    "where, expected",
    [
        (("Valysar", "top"), 1),
        (("Valysar", "center"), 6),
        (("Valysar", "base"), 10),
        (("Therys", "top"), 11),
        (("Therys", "center"), 19),
        (("Therys", "base"), 27),
        (("Volon", "top"), 28),
        (("Volon", "center"), 30),
        (("Volon", "base"), 32),
        (("", "top"), 1),
        (("", "center"), 16),
        (("", "base"), 32),
    ],
)
def test_getlayer_function(local_testdata, where, expected):
    """Test the internal _get_layer() function (where layer number has base 1)."""

    grid, _, zone, _ = local_testdata

    assert _get_layer(where, grid, zone) == expected


def test_attr_maps_sim2seis(local_testdata):
    """Test a basic case."""

    grid, region, zone, attr_surface = local_testdata

    attr_surface_error = attr_surface * 0.2
    attr_surface_error.values = np.abs(attr_surface_error.values)

    df = sample_attributes_for_sim2seis(
        grid,
        attr_surface,
        attribute_error=attr_surface_error,
        region=region,
        position=("Valysar", "top"),
        zone=zone,
        debug=False,  # this is a 'developer' kwargs to the function
    )
    assert Attrs.OBS.value in df.columns
    assert Attrs.OBS_ERROR.value in df.columns
    assert Attrs.REGION.value in df.columns
    assert df.OBS.mean() == pytest.approx(attr_surface.values.mean(), rel=0.05)
    assert df.REGION.max() == 7.0


def test_attr_maps_sim2seis_error_notabsolute(local_testdata):
    """Test a case where user do not give error map as absolute."""

    grid, region, zone, attr_surface = local_testdata

    attr_surface_error = attr_surface * 0.2
    assert attr_surface_error.values.min() < 0

    with pytest.raises(ValueError):
        _ = sample_attributes_for_sim2seis(
            grid,
            attr_surface,
            attribute_error=attr_surface_error,
            region=region,
            position=("Valysar", "top"),
            zone=zone,
            debug=False,  # this is a 'developer' kwargs to the function
        )


def test_attr_maps_sim2seis_set_min_error(local_testdata):
    """Test a case where user sets a minimum error value."""

    grid, region, zone, attr_surface = local_testdata

    attr_surface_error = attr_surface * 0.2
    attr_surface_error.values = np.abs(attr_surface_error.values)
    assert attr_surface_error.values.min() >= 0.0

    df = sample_attributes_for_sim2seis(
        grid,
        attr_surface,
        attribute_error=attr_surface_error,
        attribute_error_minimum=0.01,
        region=region,
        position=("Valysar", "top"),
        zone=zone,
    )

    assert Attrs.OBS.value in df.columns
    assert Attrs.OBS_ERROR.value in df.columns
    assert df.OBS.mean() == pytest.approx(attr_surface.values.mean(), rel=0.05)
    assert df.OBS_ERROR.min() >= 0.01


def test_attr_maps_sim2seis_no_region(local_testdata):
    """Test a case where there is no region, and attribute error as float."""

    grid, _, zone, attr_surface = local_testdata

    df = sample_attributes_for_sim2seis(
        grid,
        attr_surface,
        attribute_error=0.3,
        region=None,
        position=("Valysar", "top"),
        zone=zone,
    )

    assert Attrs.OBS.value in df.columns
    assert Attrs.OBS_ERROR.value in df.columns
    assert Attrs.REGION.value not in df.columns
    assert df.OBS_ERROR.mean() == pytest.approx(
        np.abs(attr_surface.values).mean() * 0.3, rel=0.05
    )
