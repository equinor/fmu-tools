import logging
from pathlib import Path
from typing import Any

import numpy as np
import pytest
import xtgeo

from fmu.tools import sample_attributes_for_sim2seis
from fmu.tools.utilities.sample_attributes import Attrs, Position, _get_layer

logger = logging.getLogger(__name__)


@pytest.fixture(scope="module", name="local_testdata")
def fixture_testdata(
    testdata_path: Path,
) -> tuple[xtgeo.grid3d, xtgeo.GridProperty, xtgeo.GridProperty, xtgeo.surface]:
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
        (("Valysar", Position.TOP), 1),
        (("Valysar", Position.CENTER), 6),
        (("Valysar", Position.BASE), 10),
        (("Therys", Position.TOP), 11),
        (("Therys", Position.CENTER), 19),
        (("Therys", Position.BASE), 27),
        (("Volon", Position.TOP), 28),
        (("Volon", Position.CENTER), 30),
        (("Volon", Position.BASE), 32),
        (("", Position.TOP), 1),
        (("", Position.CENTER), 16),
        (("", Position.BASE), 32),
    ],
)
def test_getlayer_function(
    local_testdata: tuple[Any, xtgeo.GridProperty, xtgeo.GridProperty, Any],
    where: tuple[str, Position],
    expected: int,
) -> None:
    """Test the internal _get_layer() function (where layer number has base 1)."""

    grid, _, zone, _ = local_testdata

    assert _get_layer(where, grid, zone) == expected


def test_attr_maps_sim2seis(
    local_testdata: tuple[Any, xtgeo.GridProperty, xtgeo.GridProperty, xtgeo.surface],
) -> None:
    """Test a basic case."""

    grid, region, zone, attr_surface = local_testdata

    attr_surface_error = attr_surface * 0.2
    attr_surface_error.values = np.abs(attr_surface_error.values)

    df = sample_attributes_for_sim2seis(
        grid,
        attr_surface,
        attribute_error=attr_surface_error,
        region=region,
        position=("Valysar", Position.TOP),
        zone=zone,
        debug=False,  # this is a 'developer' kwargs to the function
    )
    assert Attrs.OBS.value in df.columns
    assert Attrs.OBS_ERROR.value in df.columns
    assert Attrs.REGION.value in df.columns
    assert df.OBS.mean() == pytest.approx(attr_surface.values.mean(), rel=0.05)
    assert df.REGION.max() == 7.0


def test_attr_maps_sim2seis_error_notabsolute(
    local_testdata: tuple[Any, xtgeo.GridProperty, xtgeo.GridProperty, xtgeo.surface],
) -> None:
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
            position=("Valysar", Position.TOP),
            zone=zone,
            debug=False,  # this is a 'developer' kwargs to the function
        )


def test_attr_maps_sim2seis_set_min_error(
    local_testdata: tuple[Any, xtgeo.GridProperty, xtgeo.GridProperty, xtgeo.surface],
) -> None:
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
        position=("Valysar", Position.TOP),
        zone=zone,
    )

    assert Attrs.OBS.value in df.columns
    assert Attrs.OBS_ERROR.value in df.columns
    assert df.OBS.mean() == pytest.approx(attr_surface.values.mean(), rel=0.05)
    assert df.OBS_ERROR.min() >= 0.01


def test_attr_maps_sim2seis_no_region(
    local_testdata: tuple[Any, xtgeo.GridProperty, xtgeo.GridProperty, xtgeo.surface],
) -> None:
    """Test a case where there is no region, and attribute error as float."""

    grid, _, zone, attr_surface = local_testdata

    df = sample_attributes_for_sim2seis(
        grid,
        attr_surface,
        attribute_error=0.3,
        region=None,
        position=("Valysar", Position.TOP),
        zone=zone,
    )

    assert Attrs.OBS.value in df.columns
    assert Attrs.OBS_ERROR.value in df.columns
    assert Attrs.REGION.value not in df.columns
    assert df.OBS_ERROR.mean() == pytest.approx(
        np.abs(attr_surface.values).mean() * 0.3, rel=0.05
    )
