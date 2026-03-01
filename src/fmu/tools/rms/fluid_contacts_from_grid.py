"""Create fluid contact surfaces and outlines from grid contact parameters."""

from typing import Any, Literal

import numpy as np
import pandas as pd
import xtgeo
from pydantic import BaseModel

from fmu.tools.utilities._surface_operations import (
    nearest_node_gridding,
    resample_surf_to_template,
)

OUTPUT_FOLDER_SURFACES = "fluid_contact_surfaces"
OUTPUT_FOLDER_OUTLINES = "fluid_contact_outlines"

STYPE = "general2d_data"


class FluidContact(BaseModel):
    """Fluid contact class."""

    name: str
    type: Literal["fwl", "goc", "gwc"]


class _RMSDataLoader:
    """Helper class for loading grid and properties from RMS/Roxar."""

    def __init__(self, project: Any, grid_name: str):
        self.project = project
        self.grid_name = grid_name

    def load_grid(self) -> xtgeo.Grid:
        """Load grid from RMS."""
        return xtgeo.grid_from_roxar(self.project, self.grid_name)

    def load_property(self, property_name: str) -> xtgeo.GridProperty:
        """Load a property from RMS."""
        return xtgeo.gridproperty_from_roxar(
            self.project, self.grid_name, property_name
        )

    def find_available_contact_properties(
        self, fwl_name: str, goc_name: str, gwc_name: str
    ) -> list[FluidContact]:
        """Return contact properties that are available in the project."""
        properties = self.project.grid_models[self.grid_name].properties
        contacts = []
        if fwl_name in properties:
            contacts.append(FluidContact(name=fwl_name, type="fwl"))
        if goc_name in properties:
            contacts.append(FluidContact(name=goc_name, type="goc"))
        if gwc_name in properties:
            contacts.append(FluidContact(name=gwc_name, type="gwc"))

        if not contacts:
            raise ValueError(
                f"None of the contact properties {fwl_name}, {goc_name}, or "
                f"{gwc_name} were found in the project."
            )
        return contacts


class _GridDataAssembler:
    """Helper class for assembling grid data with contact and zone properties."""

    def __init__(
        self,
        loader: _RMSDataLoader,
        contacts: list[FluidContact],
        zone_name: str | None = None,
        grid_refinement: int | None = None,
    ):
        self._loader = loader
        self._grid = loader.load_grid()

        for contact in contacts:
            prop = self._loader.load_property(contact.name)
            self._append_property_to_grid(prop, name=contact.type)

        if zone_name:
            self._zone_prop = loader.load_property(zone_name)
            self._append_property_to_grid(self._zone_prop, name="Zone")
        else:
            self._zone_prop = self.grid.get_zoneprop_from_subgrids()

        if grid_refinement:
            self._grid.refine(
                refine_col=grid_refinement,
                refine_row=grid_refinement,
                refine_layer=grid_refinement,
            )

    @property
    def grid(self) -> xtgeo.Grid:
        """Get the grid."""
        return self._grid

    @property
    def zone_codenames(self) -> dict[int, str]:
        """Get the zone property codenames."""
        return self._zone_prop.codes

    def get_dataframe(self) -> pd.DataFrame:
        """Get dataframe with active cells and all loaded properties."""
        return self._grid.get_dataframe(activeonly=True)

    def get_surface_with_grid_dimensions(self) -> xtgeo.RegularSurface:
        """Get an xtgeo surface with the grid dimension."""
        return xtgeo.surface_from_grid3d(self._grid, "native")

    def _append_property_to_grid(self, prop: xtgeo.GridProperty, name: str):
        """Load and append a property to the grid."""
        prop.name = name
        self._grid.append_prop(prop)


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
) -> xtgeo.RegularSurface | None:
    """
    Create a contact surface for points in a dataframe.
    The surface will be masked where the contact value is below the value filter,
    and where nodes are further away than the maximum distance between the grid
    cells in the x and y directions. If all values are masked after filtering,
    None is returned.
    """
    df = _filter_to_closest_contact_cell_in_pillars(df, contact)

    surf = nearest_node_gridding(
        surf=template,
        points=xtgeo.Points(df, zname=contact),
        distance_threshold=max(template.xinc, template.yinc),
    )
    surf.values = np.ma.masked_where(surf.values <= min_value_filter, surf.values)
    return surf if not surf.values.mask.all() else None


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


def create_fluid_contacts_from_grid(
    project: Any,
    grid_name: str,
    fwl_name: str = "FWL",
    goc_name: str = "GOC",
    gwc_name: str = "GWC",
    zone_name: str | None = None,
    min_value_filter: float = 0,
    template_surf: xtgeo.RegularSurface | None = None,
    grid_refinement: int | None = None,
) -> None:
    """
    Function to create fluid contacts surfaces and outlines from grid contact
    parameters. Output will be stored inside RMS under General 2D data in folders
    ``fluid_contact_surfaces`` and ``fluid_contact_outlines``.

    By default, the function creates a contact surface and outline for each zone
    defined in the grid. To instead create contacts for groups of zones that share
    a contact, a custom zone property can be provided.

    The contact surface will be created by finding the closest contact cell in each
    grid pillar, and gridding them with nearest-node. The contact outline will be
    extracted as the boundary polygon of cells whose centers lie above the contact.

    The supported contact types are ``FWL`` (free water level), ``GOC``
    (gas-oil contact), and ``GWC`` (gas-water contact). The function will check which
    of these are available in the project. It is not necessary to have all contact types
    in the project, and the function will create output only for the ones available.

    A value filter can be applied to remove values below a certain threshold via the
    ``min_value_filter`` argument. This is useful for removing contact values in
    surrounding areas where the value is often set to a low number.

    By default, output surfaces have the same resolution as the input grid. To increase
    resolution, the grid can be refined before processing using the ``grid_refinement``
    argument. It is also possible to match a specific output geometry by providing
    a template surface via ``template_surf`` - the contact surface will be resampled
    to this template as a final step.

    Args:
        project: The magic ``project`` variable from RMS.
        grid_name: The name of the grid.
        fwl_name: The name of the free water level property. Default is ``FWL``.
        goc_name: The name of the gas-oil contact property. Default is ``GOC``.
        gwc_name: The name of the gas-water contact property. Default is ``GWC``.
        zone_name: Optional name of the zone property to use for creating contacts for
          coarse zones.
        min_value_filter: Minimum value filter. Surface values below this will be set
          to undefined. Default is ``0``.
        template_surf: Optional template surface to resample the contact surface to.
          If not provided, the contact surface will have the same dimension as the grid.
        grid_refinement: Optional refinement factor to refine the grid before processing
          to increase resolution of the output. Be aware that a high refinement factor
          will reduce performance. Note, this does not affect the grid in RMS.
    """
    loader = _RMSDataLoader(project, grid_name)
    contacts = loader.find_available_contact_properties(fwl_name, goc_name, gwc_name)

    grid_data = _GridDataAssembler(
        loader=loader,
        contacts=contacts,
        zone_name=zone_name,
        grid_refinement=grid_refinement,
    )

    df = grid_data.get_dataframe()
    surface_from_grid = grid_data.get_surface_with_grid_dimensions()

    for contact in contacts:
        print(f"Working on contact {contact.type} using parameter {contact.name}.")
        for code, zonename in grid_data.zone_codenames.items():
            print(f"  - processing {zonename=}.")
            zonedf = df[df["Zone"] == code]

            if surf := _create_contact_surface(
                zonedf,
                contact.type,
                min_value_filter,
                surface_from_grid,
            ):
                # For performance the contact surfaces are created using the
                # grid surface, and resampling applied afterwards.
                if template_surf:
                    surf = resample_surf_to_template(surf, template_surf)

                surf.to_roxar(
                    project,
                    zonename,
                    f"{OUTPUT_FOLDER_SURFACES}/{contact.type}",
                    stype=STYPE,
                )

            if outline := _create_fluid_contact_outline(
                zonedf,
                contact.type,
                min_value_filter,
            ):
                outline.to_roxar(
                    project,
                    zonename,
                    f"{OUTPUT_FOLDER_OUTLINES}/{contact.type}",
                    stype=STYPE,
                )
    print(
        "\nFluid contacts stored in 'General 2D Data' under folders "
        f"{OUTPUT_FOLDER_SURFACES} and {OUTPUT_FOLDER_OUTLINES}'."
    )
