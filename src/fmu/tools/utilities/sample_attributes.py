"""Sample attributes on grid resolution as dataframe points sets.

This usage is for setting attributes on grid resolution, e.g. a seismic attribute
(from a map) combined with a region parameter from the same 3D grid.

This is targeted to the "sim2seis" workflow in FMU.
"""

from __future__ import annotations

import logging
import pathlib
import tempfile
from enum import Enum
from typing import TYPE_CHECKING, Any

import numpy as np
import xtgeo

if TYPE_CHECKING:
    import pandas as pd

# custom logger for this module
logger = logging.getLogger(__name__)


class Attrs(str, Enum):
    OBS = "OBS"
    OBS_ERROR = "OBS_ERROR"
    REGION = "REGION"
    VALUES = "VALUES"


class Position(str, Enum):
    TOP = "top"
    CENTER = "center"
    BASE = "base"


def _get_layer(
    position: tuple[str, Position], grid: xtgeo.Grid, zone: xtgeo.GridProperty
) -> int:
    """Get the layer index (base=1!) based on the position and zone."""
    zone_name, where = position

    position_values = [pos.value for pos in Position]
    if where not in position_values:
        raise ValueError(f"Position shall be one of: {position_values}")

    top_value = 1
    center_value = round(0.5 * (grid.nlay + 1))
    base_value = grid.nlay

    if zone and zone_name:
        if zone_name not in zone.codes.values():
            raise ValueError(f"Zone name '{zone_name}' not found in the grid.")

        nzone = {v: k for k, v in zone.codes.items()}.get(zone_name)
        logger.debug("Zone index to apply for %s is: %s", zone_name, nzone)

        indices = np.where(zone.values == nzone)
        upper, lower = indices[2].min() + 1, indices[2].max() + 1  # base=1

        top_value = upper
        center_value = round(0.5 * (upper + lower))
        base_value = lower

    if Position.TOP in where:
        return top_value

    if Position.BASE in where:
        return base_value

    return center_value  # default is center


def _dataframe_from_surface(
    surface: xtgeo.RegularSurface, newname: str | None = None, debug: bool = False
) -> pd.DataFrame:
    """Get the data frame via xtgeo Points (makes it easier to debug)"""

    points = xtgeo.points_from_surface(surface)
    points.zname = newname if newname else Attrs.VALUES.value
    df = points.get_dataframe()
    if debug:
        temp_dir = pathlib.Path(tempfile.gettempdir())
        out = temp_dir / f"debug_points_{newname}.poi"
        points.to_file(out)
        print("Debug points written to:", out)

    return df


def sample_attributes_for_sim2seis(
    grid: xtgeo.Grid,
    attribute: xtgeo.RegularSurface,
    attribute_error: xtgeo.RegularSurface | float = 0.05,
    attribute_error_minimum: float | None = None,
    region: xtgeo.GridProperty | None = None,
    zone: xtgeo.GridProperty | None = None,
    position: tuple[str, Position] = ("", Position.CENTER),
    **kwargs: Any,
) -> pd.DataFrame:
    """Sample attributes on grid resolution as poinst sets.

    This usage is for setting attributes on grid resolution, e.g. a seismic attribute
    (from a map) combined with a region parameter from the grid.

    This is targeted to the "sim2seis" workflow in FMU.

    Args:
        grid: The grid to sample the attributes on.
        attribute: The seismic (or custom) map/surface to sample the attribute from.
        attribute_error: The error to apply to the attribute (optional).
            Shall be absolute (positive) values. If the user wants to apply a polygons
            with different error values, the user can ise surface-polygons functions
            in xtgeo to achieve this.
        attribute_error_minimum: The minimum error to apply to the attribute (optional).
        region: The region parameter to sample from the grid (optional).
        zone: The zone parameter to sample from the grid (optional).
        position: The position to sample the attributes on the grid. This
            shall be given as a tuple, as e.g. ("MyZone", "center") where the first
            is zone name, and the second is vertical position ("top", "center", "base")
            in that zone. Default is ("", "center") which will take the middle layer
            of the total grid. The zone name is case sensitive. If zone is not given,
            the full grid interval will be applied to determine the layer.
        **kwargs: Additional keywords (developer settings).

    Returns:
        pd.Dataframe: Points with the sampled attributes and attributes combined.
    """
    logger.info("Sampling attributes on grid resolution as points set.")

    debug = kwargs.get("debug", False)

    layer = _get_layer(position, grid, zone)
    logger.debug("Layer index (base=1) to apply is: %s", layer)

    template = xtgeo.surface_from_grid3d(
        grid,
        template="native",  # used to appromimate the native grid resolution
        where=layer,
        property="i",
    )
    # prepare the attribute and error to the grid
    attribute_sampled = template.copy()
    attribute_error_sampled = template.copy()

    # do the resampling and get the points as dataframe
    attribute_sampled.resample(attribute)
    dataframe = _dataframe_from_surface(
        attribute_sampled, newname=Attrs.OBS.value, debug=debug
    )

    if isinstance(attribute_error, float):
        if attribute_error < 0:
            raise ValueError("The attribute error shall be an absolute value.")
        err = attribute * attribute_error
        err.values = np.abs(err.values)
    else:
        err = attribute_error
        if err.values.min() < 0:
            raise ValueError("The attribute error shall be an absolute value.")

    if attribute_error_minimum:
        err.values = np.maximum(err.values, attribute_error_minimum)

    attribute_error_sampled.resample(err)
    df_err = _dataframe_from_surface(
        attribute_error_sampled, newname=Attrs.OBS_ERROR.value, debug=debug
    )
    dataframe[Attrs.OBS_ERROR.value] = df_err[Attrs.OBS_ERROR.value]

    df_region = None
    if region:
        region_sampled = xtgeo.surface_from_grid3d(
            grid, template=template, where=layer, property=region
        )
        df_region = _dataframe_from_surface(
            region_sampled, newname=Attrs.REGION.value, debug=debug
        )
        dataframe[Attrs.REGION.value] = df_region[Attrs.REGION.value]

    return dataframe.dropna()
