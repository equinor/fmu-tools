"""
Filter to FLUID zone OIL in 2024, and create surface of the top oil points

"""

from copy import deepcopy
from typing import Any, Literal

import numpy as np
import pandas as pd
import xtgeo
from pydantic import BaseModel

from fmu.tools.utilities._surface_operations import (
    nearest_node_gridding,
    resample_surf_to_template,
)

OUTPUT_FOLDER = "fluid_contacts"
STYPE = "general2d_data"


class FluidContact(BaseModel):
    """Fluid contact class."""

    name: str
    type: Literal["fwl", "goc"]


class _GridProcessor:
    def __init__(self, grid: xtgeo.Grid) -> None:
        self.grid = grid
        self._dataframe = None

    @property
    def dataframe(self) -> pd.DataFrame:
        """Get the grid dataframe."""
        if self._dataframe is None:
            self._dataframe = self.grid.get_dataframe(activeonly=True)
        return self._dataframe

    def get_surface_with_grid_dimension(self) -> xtgeo.RegularSurface:
        """Get an xtgeo surface with the grid dimension."""
        return xtgeo.surface_from_grid3d(self.grid, "native")

    def get_layerlist_for_zones(
        self, coarse_zones: dict[str, list[str]] | None = None
    ) -> dict[str, list[int]]:
        """Get a list of layers for coarse zones or individual zones."""
        if coarse_zones is None:
            return deepcopy(self.grid.subgrids)
        return {
            coarse_zone_name: self._get_layerlist_for_zones(zones)
            for coarse_zone_name, zones in coarse_zones.items()
        }

    def _get_layerlist_for_zones(self, zones: list[str]) -> list[int]:
        """Get list of corresponding layers for a list of zones."""
        invalid_zones = [zone for zone in zones if zone not in self.grid.subgrids]
        if invalid_zones:
            raise ValueError(f"Unknown zones found: {invalid_zones}")

        layers = []
        for zone in zones:
            layers.extend(self.grid.subgrids[zone])
        return layers

    def _get_df_filtered_on_layers(self, layerlist: list[int]) -> pd.DataFrame:
        """Filter the dataframe to only include the layers in the layerlist."""
        return self.dataframe[self.dataframe["KZ"].isin(layerlist)].copy()


def _filter_to_closest_contact_cell_in_pillars(
    df: pd.DataFrame, contact: str
) -> pd.DataFrame:
    """
    Filter a grid dataframe to only include the cell in each grid
    pillar (each 'IX'/'JY') that are closest to the contact.
    """
    df = df.copy()
    df["abs_diff"] = np.abs(df["Z_TVDSS"].values - df[contact].values)
    min_abs_diff = df.groupby(["IX", "JY"])["abs_diff"].transform("min")
    return df[df["abs_diff"] == min_abs_diff]


def _filter_to_deepest_cell_above_contact_in_pillars(
    df: pd.DataFrame, contact: str, min_value_filter: float
) -> pd.DataFrame:
    """
    Filter a grid dataframe to only include the cells that are above the contact
    and deeper then the value filter, and return the deepest cell in each
    grid pillar (each 'IX'/'JY').
    """
    df = df[(df[contact] > df["Z_TVDSS"]) & (df[contact] > min_value_filter)]

    deepest_cell = df.groupby(["IX", "JY"])["KZ"].transform("max")
    return df[df["KZ"] == deepest_cell]


def _create_contact_surface(
    df: pd.DataFrame,
    contact: str,
    min_value_filter: float,
    template: xtgeo.RegularSurface,
) -> xtgeo.RegularSurface:
    """
    Create a contact surface for points in a dataframe."
    The surface will be masked where the contact value is below the value filter,
    and where nodes are further away than the maximum distance between the grid
    cells in the x and y directions.
    """
    df = _filter_to_closest_contact_cell_in_pillars(df, contact)

    surf = nearest_node_gridding(
        surf=template,
        points=xtgeo.Points(df, zname=contact),
        distance_threshold=max(template.xinc, template.yinc),
    )
    surf.values = np.ma.masked_where(surf.values <= min_value_filter, surf.values)
    return surf


def _create_fluid_contact_outline(
    df: pd.DataFrame, contact: str, min_value_filter: float
) -> xtgeo.Polygons | None:
    """
    Create a fluid contact outline by filtering the input dataframe to cells
    above the contact and extracting the outline from it.
    """
    df = _filter_to_deepest_cell_above_contact_in_pillars(df, contact, min_value_filter)

    if len(df) < 4:
        return None

    points = xtgeo.Points(df, zname=contact)
    return xtgeo.Polygons.boundary_from_points(points, alpha_factor=1)


def _get_available_contact_properties(
    project: Any, gridname: str, fwl_name: str, goc_name: str
) -> list[FluidContact]:
    """Return contact properties that are available in the project."""
    properties = project.grid_models[gridname].properties

    contacts = []
    if fwl_name in properties:
        contacts.append(FluidContact(name=fwl_name, type="fwl"))
    if goc_name in properties:
        contacts.append(FluidContact(name=goc_name, type="goc"))

    if not contacts:
        raise ValueError(
            f"None of the contact properties {fwl_name} or {goc_name} were "
            "found in the project."
        )
    return contacts


def _load_grid_and_contacts_from_project(
    project: Any, gridname: str, contacts: list[FluidContact]
) -> xtgeo.Grid:
    """
    Load the grid and contact properties from RMS. The contact properties are
    added to the grid so that their values are included in the grid dataframe.
    """
    grid = xtgeo.grid_from_roxar(project, gridname)
    for contact in contacts:
        prop = xtgeo.gridproperty_from_roxar(project, gridname, contact.name)
        grid.append_prop(prop)
    return grid


def create_fluid_contacts_from_grid(
    project: Any,
    gridname: str,
    fwl_name: str = "FWL",
    goc_name: str = "GOC",
    min_value_filter: float = 0,
    coarse_zones: dict[str, list[str]] | None = None,
    template_surf: xtgeo.RegularSurface | None = None,
) -> None:
    """
    Create fluid contacts surfaces and outlines from grid contact parameters.
    Output will be stored inside RMS under 'General 2D data/fluid_contacts'.

    The function will automatically create a contact surface and a contact outline
    for each zone in the grid. It is also possible to output additional data for
    collection of zones that share a contact. This is done by using the coarse_zones
    argument.

    The contact surface will be created by finding the closest contact cell in each
    grid pillar, and gridding them with nearest node. The contact outline will be
    extracted as the boundary polygon of cells that have their cell center depth
    above the contact.

    A value filter can be applied to the contact surface, where all values below
    the filter will be masked. This is useful for removing contact values in
    surrounding areas where the value is often set to a low number.

    By default the surfaces will have the same dimension as the grid, but it is possible
    to resample the contact surface to a template surface.

    args:
        project: The magic project variable from RMS.
        gridname: The name of the grid.
        fwl_name: The name of the Free Water Level property in RMS. Default is "FWL".
        goc_name: The name of the Gas-Oil Contact property in RMS. Default is "GOC".
        min_value_filter: Optional value filter. Surface values below this will be set
          to undefined. Default is 0.
        coarse_zones: Optional. A dictionary used to create contacts for a collection
          of zones that shares a contact. The keys in the dictionary are the desired
          names of the coarse zone and the values are lists of zone names to group.
          Example: {"Draupne": ["Draupne_Fm_1", "Draupne_Fm_2"]}.
        template_surf: Optional template surface to resample the contact surface to.
          If not provided, the contact surface will have the same dimension as the grid.
    """

    contacts = _get_available_contact_properties(project, gridname, fwl_name, goc_name)
    grid = _load_grid_and_contacts_from_project(project, gridname, contacts)

    gridprocessor = _GridProcessor(grid)
    surface_from_grid = gridprocessor.get_surface_with_grid_dimension()
    zone_layers = gridprocessor.get_layerlist_for_zones(coarse_zones)

    for contact in contacts:
        print(f"Working on contact {contact.type} using parameter {contact.name}.")
        for zone, layerlist in zone_layers.items():
            print(f"  - processing {zone=}.")
            zonedf = gridprocessor._get_df_filtered_on_layers(layerlist)

            if surf := _create_contact_surface(
                zonedf,
                contact.name,
                min_value_filter,
                surface_from_grid,
            ):
                # For performance the contact surfaces are created using the
                # grid surface, and resampling applied afterwards.
                if template_surf:
                    surf = resample_surf_to_template(surf, template_surf)

                surf.to_roxar(
                    project,
                    zone,
                    f"{OUTPUT_FOLDER}/surfaces/{contact.type}",
                    stype=STYPE,
                )

            if outline := _create_fluid_contact_outline(
                zonedf,
                contact.name,
                min_value_filter,
            ):
                outline.to_roxar(
                    project,
                    zone,
                    f"{OUTPUT_FOLDER}/outlines/{contact.type}",
                    stype=STYPE,
                )

    print(f"\nFluid contacts created in 'General 2D data/{OUTPUT_FOLDER}' folder.")
