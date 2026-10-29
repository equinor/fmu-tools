"""Nested hybrid grid creation.

Create a merged grid where one region is refined (subdivided) and stitched
back into the original grid via Non-Neighbour Connections (NNCs).

Public API
----------
create_nested_hybrid_grid : function
    Build a nested hybrid grid from a coarse grid, a region property,
    and a refinement specification.
nnc_to_gridproperty : function
    Convert NNC transmissibility DataFrames to GridProperty instances.
nnc_to_flowsimulator_input : function
    Write NNC transmissibilities to a flow-simulator input file.
"""

from __future__ import annotations

import logging
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, Self, TypeAlias

import numpy as np
import pandas as pd
import xtgeo
from pydantic import BaseModel, Field, ValidationError

if TYPE_CHECKING:
    import os
    from collections.abc import Iterable

    from xtgeo.common.types import Dimensions

_logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

FaceDirection: TypeAlias = Literal["i+", "i-", "j+", "j-", "k+", "k-"]
IJKIndex: TypeAlias = tuple[int, int, int]
BoundaryCellFace: TypeAlias = tuple[IJKIndex, IJKIndex, FaceDirection]
ORIGINAL_IJK_PROPERTY_NAMES = ("parent_I", "parent_J", "parent_K")


@dataclass(frozen=True)
class CellsByParent:
    """Group flattened cell indices by parent.

    group_start and group_stop are indexed by parent and define slices
    into cell_indices. Unmapped parents have both set to -1.
    """

    cell_indices: np.ndarray
    group_start: np.ndarray
    group_stop: np.ndarray

    @classmethod
    def from_parent_indices(
        cls,
        parent_indices: np.ndarray,
        selected_mask: np.ndarray,
        parent_cell_count: int,
    ) -> Self:
        selected_parent_indices = parent_indices[selected_mask]
        selected_cell_indices = np.flatnonzero(selected_mask)

        if selected_parent_indices.size == 0:
            raise ValueError("No selected parent indices found.")

        sort_order = np.argsort(selected_parent_indices)

        sorted_parent_indices = selected_parent_indices[sort_order]
        sorted_cell_indices = selected_cell_indices[sort_order]

        cuts = np.flatnonzero(np.diff(sorted_parent_indices)) + 1

        group_starts = np.r_[0, cuts]
        group_stops = np.r_[cuts, sorted_parent_indices.size]
        unique_parent_indices = sorted_parent_indices[group_starts]

        group_start = np.full(parent_cell_count, -1, dtype=np.intp)
        group_stop = np.full(parent_cell_count, -1, dtype=np.intp)

        group_start[unique_parent_indices] = group_starts
        group_stop[unique_parent_indices] = group_stops

        return cls(
            cell_indices=sorted_cell_indices,
            group_start=group_start,
            group_stop=group_stop,
        )

    @property
    def mapped_mask(self) -> np.ndarray:
        """Return a boolean mask indicating which parents have mapped cells."""
        return self.group_start >= 0

    @property
    def mapped_parent_indices(self) -> np.ndarray:
        """Return parent indices that have mapped cells."""
        return np.flatnonzero(self.mapped_mask)

    @property
    def counts(self) -> np.ndarray:
        """Return the number of cells mapped to each parent."""
        return self.group_stop - self.group_start

    def get_indices(self, parent_idx: int | np.intp) -> np.ndarray:
        start = self.group_start[parent_idx]

        if start == -1:
            raise ValueError(f"No cells found for parent index {parent_idx}.")

        return self.cell_indices[start : self.group_stop[parent_idx]]


class BoundingBox(BaseModel):
    imin: int = Field(ge=1)
    imax: int = Field(ge=1)
    jmin: int = Field(ge=1)
    jmax: int = Field(ge=1)
    kmin: int = Field(ge=1)
    kmax: int = Field(ge=1)

    @classmethod
    def from_condition(cls, condition: np.ma.MaskedArray) -> Self:
        """Get the ijk bounding box from a 3D boolean mask."""
        region_indices = condition.nonzero()

        return cls(
            imin=int(region_indices[0].min() + 1),
            imax=int(region_indices[0].max() + 1),
            jmin=int(region_indices[1].min() + 1),
            jmax=int(region_indices[1].max() + 1),
            kmin=int(region_indices[2].min() + 1),
            kmax=int(region_indices[2].max() + 1),
        )


class Refinement(BaseModel):
    col: int = Field(ge=1)
    row: int = Field(ge=1)
    lay: int = Field(ge=1)

    @classmethod
    def from_tuple(cls, refinement: tuple[int, int, int]) -> Self:
        """Create a refinement model from a 3-tuple."""
        try:
            col, row, lay = refinement
            return cls(col=col, row=row, lay=lay)
        except ValidationError:
            raise ValueError("Refinement factors must be >= 1")


def _crop_for_region(grid: xtgeo.Grid, refinement_bbox: BoundingBox) -> xtgeo.Grid:
    """Crop grid to the bounding box of the refinement region."""

    cropped_grid = grid.copy()

    irange = (refinement_bbox.imin, refinement_bbox.imax)
    jrange = (refinement_bbox.jmin, refinement_bbox.jmax)
    krange = (refinement_bbox.kmin, refinement_bbox.kmax)

    cropped_grid.crop(irange, jrange, krange, props="all")
    _logger.info("Cropped grid dimensions: %s", cropped_grid.dimensions)

    return cropped_grid


def _find_boundary_faces(refined_area: np.ma.MaskedArray) -> list[BoundaryCellFace]:
    """Find cell faces on the boundary of a refinement area.

    Args:
        refined_area: 3D boolean array where ``True`` marks cells to refine.

    Returns:
        A list of ``(outside_ijk, inside_ijk, face_dir)`` where indices are
        0-based and *face_dir* is one of ``'i+', 'i-', 'j+', 'j-', 'k+', 'k-'``.
    """
    ni, nj, nk = refined_area.shape
    active = ~refined_area.mask

    in_target = refined_area & active
    outside_active = ~refined_area & active

    faces: list[BoundaryCellFace] = []

    # i+
    mask = in_target[: ni - 1, :, :] & outside_active[1:ni, :, :]
    for i, j, k in np.argwhere(mask):
        faces.append(((int(i + 1), int(j), int(k)), (int(i), int(j), int(k)), "i+"))

    # i-
    mask = in_target[1:ni, :, :] & outside_active[: ni - 1, :, :]
    for idx, j, k in np.argwhere(mask):
        faces.append(((int(idx), int(j), int(k)), (int(idx + 1), int(j), int(k)), "i-"))

    # j+
    mask = in_target[:, : nj - 1, :] & outside_active[:, 1:nj, :]
    for i, j, k in np.argwhere(mask):
        faces.append(((int(i), int(j + 1), int(k)), (int(i), int(j), int(k)), "j+"))

    # j-
    mask = in_target[:, 1:nj, :] & outside_active[:, : nj - 1, :]
    for i, jdx, k in np.argwhere(mask):
        faces.append(((int(i), int(jdx), int(k)), (int(i), int(jdx + 1), int(k)), "j-"))

    # k+
    mask = in_target[:, :, : nk - 1] & outside_active[:, :, 1:nk]
    for i, j, k in np.argwhere(mask):
        faces.append(((int(i), int(j), int(k + 1)), (int(i), int(j), int(k)), "k+"))

    # k-
    mask = in_target[:, :, 1:nk] & outside_active[:, :, : nk - 1]
    for i, j, kdx in np.argwhere(mask):
        faces.append(((int(i), int(j), int(kdx)), (int(i), int(j), int(kdx + 1)), "k-"))

    _logger.info("Found %d boundary faces for refinement area", len(faces))
    return faces


def _compute_nnc_table(
    refined_area: np.ma.MaskedArray,
    refinement: Refinement,
    coarse_ncol: int,
    lmap1: np.ndarray,
    lmap2: np.ndarray,
) -> pd.DataFrame:
    """Compute NNC cell-pair mapping between mother and refined cells.

    For each boundary face between the target region and the surrounding mother
    cells, this function determines which refined sub-cells in the merged grid
    connect to which mother cell, and through which face direction.

    The mapping is purely topological (index-based) — no geometric computation
    is performed here.  The resulting table is intended to be passed to
    :meth:`xtgeo.Grid.get_transmissibilities` so that it can compute the
    actual transmissibility for each cell pair.

    Convention:
        - ``I1, J1, K1`` is always the **mother** cell (1-based, merged grid).
        - ``I2, J2, K2`` is always the **refined** cell (1-based, merged grid).
        - ``DIRECTION`` is from the mother cell's perspective (e.g. ``"I+"``
          means looking in the positive I-direction from the mother cell
          you reach the refined cell).

    Args:
        refined_area: 3D boolean array where ``True`` marks cells to refine.
        refinement: ``(rcol, rrow, rlay)`` refinement factors.
        coarse_ncol: Number of columns in the coarse grid (grid1 in the merge).
        lmap1: Numpy array with layer_mapping (input k -> output k) for grid1
        lmap2: Numpy array with layer_mapping (input k -> output k) for grid2


    Returns:
        A DataFrame with columns ``I1, J1, K1, I2, J2, K2, DIRECTION``.
    """
    faces = _find_boundary_faces(refined_area)
    bbox = BoundingBox.from_condition(refined_area)

    rcol, rrow, rlay = refinement.col, refinement.row, refinement.lay
    i0 = bbox.imin - 1
    j0 = bbox.jmin - 1
    k0 = bbox.kmin - 1

    # In the merged grid, grid2 (refined) starts after a 1-column gap:
    i_offset = coarse_ncol + 1

    rows: list[dict[str, int | str]] = []

    for outside_ijk, inside_ijk, face_dir in faces:
        # outside_ijk = mother cell (0-based in original/merged grid)
        mi, mj, mk = outside_ijk

        # inside_ijk = target cell (0-based in original grid) → cropped coords
        ci = inside_ijk[0] - i0
        cj = inside_ijk[1] - j0
        ck = inside_ijk[2] - k0

        # Determine direction from mother and which refined cells lie on the face.
        # face_dir is from the *inside* (target) cell's perspective;
        # the mother's perspective is the opposite sign.
        #
        # For I-faces: the varying refined indices are J and K  (rrow × rlay cells)
        # For J-faces: the varying refined indices are I and K  (rcol × rlay cells)
        # For K-faces: the varying refined indices are I and J  (rcol × rrow cells)
        ref_is: Iterable[int]
        ref_js: Iterable[int]
        ref_ks: Iterable[int]

        if face_dir == "i-":
            # Target at higher I than mother → mother's I+ face
            direction = "I+"
            ref_is = [ci * rcol]  # first i-column of refined block (I- face)
            ref_js = range(cj * rrow, cj * rrow + rrow)
            ref_ks = range(ck * rlay, ck * rlay + rlay)
        elif face_dir == "i+":
            # Target at lower I than mother → mother's I- face
            direction = "I-"
            ref_is = [ci * rcol + rcol - 1]  # last i-column (I+ face)
            ref_js = range(cj * rrow, cj * rrow + rrow)
            ref_ks = range(ck * rlay, ck * rlay + rlay)
        elif face_dir == "j-":
            # Target at higher J than mother → mother's J+ face
            direction = "J+"
            ref_is = range(ci * rcol, ci * rcol + rcol)
            ref_js = [cj * rrow]  # first j-row (J- face)
            ref_ks = range(ck * rlay, ck * rlay + rlay)
        elif face_dir == "j+":
            # Target at lower J than mother → mother's J- face
            direction = "J-"
            ref_is = range(ci * rcol, ci * rcol + rcol)
            ref_js = [cj * rrow + rrow - 1]  # last j-row (J+ face)
            ref_ks = range(ck * rlay, ck * rlay + rlay)
        elif face_dir == "k-":
            # Target at higher K than mother → mother's K+ face
            direction = "K+"
            ref_is = range(ci * rcol, ci * rcol + rcol)
            ref_js = range(cj * rrow, cj * rrow + rrow)
            ref_ks = [ck * rlay]  # first k-layer (K- face)
        elif face_dir == "k+":
            # Target at lower K than mother → mother's K- face
            direction = "K-"
            ref_is = range(ci * rcol, ci * rcol + rcol)
            ref_js = range(cj * rrow, cj * rrow + rrow)
            ref_ks = [ck * rlay + rlay - 1]  # last k-layer (K+ face)
        else:
            raise ValueError(f"Unexpected face direction: {face_dir!r}")

        for ri in ref_is:
            for rj in ref_js:
                for rk in ref_ks:
                    rows.append(
                        {
                            "I1": mi + 1,
                            "J1": mj + 1,
                            "K1": lmap1[mk] + 1,
                            "I2": ri + i_offset + 1,
                            "J2": rj + 1,
                            "K2": lmap2[rk] + 1,
                            "DIRECTION": direction,
                        }
                    )

    _logger.info(
        "NNC table: %d cell pairs from %d boundary faces", len(rows), len(faces)
    )
    return pd.DataFrame(rows, columns=["I1", "J1", "K1", "I2", "J2", "K2", "DIRECTION"])


def _set_actnum_in_grid(grid: xtgeo.Grid, active_mask: np.ndarray) -> None:
    """Deactivate cells where active_mask is False."""
    actnum = grid.get_actnum()
    actnum.values[~active_mask] = 0
    grid.set_actnum(actnum)


def _ijk_to_flat_index(
    i: np.ndarray, j: np.ndarray, k: np.ndarray, jdim: int, kdim: int
) -> np.ndarray:
    """Convert 0-based (i, j, k) indices to positions in a 1D flattened array.
    This follows NumPy C-order (row-major) indexing.
    """
    return i * jdim * kdim + j * kdim + k


def _validate_create_upscaling_mapping_inputs(
    geo_parent_i: xtgeo.GridProperty,
    geo_parent_j: xtgeo.GridProperty,
    geo_parent_k: xtgeo.GridProperty,
    parent_dimensions: Dimensions,
) -> None:
    """Validate geogrid parent-IJK properties before upscaling remapping."""

    for prop in (geo_parent_i, geo_parent_j, geo_parent_k):
        if not isinstance(prop, xtgeo.GridProperty):
            raise ValueError("Input IJK mapping properties must be xtgeo.GridProperty.")

    if not (
        geo_parent_i.dimensions == geo_parent_j.dimensions == geo_parent_k.dimensions
    ):
        raise ValueError("Input IJK mapping properties must have the same dimensions.")

    bounds = (
        (geo_parent_i, parent_dimensions.ncol),
        (geo_parent_j, parent_dimensions.nrow),
        (geo_parent_k, parent_dimensions.nlay),
    )
    for prop, upper_bound in bounds:
        prop_values = prop.values[~prop.values.mask]

        if not np.all(prop_values % 1 == 0):
            raise ValueError(f"Property '{prop.name}' must contain integer values.")

        if prop_values.min() < 0 or prop_values.max() > upper_bound:
            raise ValueError(
                f"Property '{prop.name}' contains values outside the valid "
                f"range [0, {upper_bound}]."
            )

    i_zero = geo_parent_i.values == 0
    j_zero = geo_parent_j.values == 0
    k_zero = geo_parent_k.values == 0

    if np.any((i_zero != j_zero) | (i_zero != k_zero)):
        raise ValueError(
            "If one input IJK mapping is zero for a cell, all must be zero."
        )


def _create_upscaling_mappings_arrays(
    geo_parent_i_values: np.ndarray,
    geo_parent_j_values: np.ndarray,
    geo_parent_k_values: np.ndarray,
    nested_cells_by_parent: CellsByParent,
    nested_dimensions: Dimensions,
    parent_dimensions: Dimensions,
    layer_map_coarse: np.ndarray,
    refinement: Refinement,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Remap geogrid-to-parent IJK references into geogrid-to-nestedgrid
    IJK references. Parent here refers to the parent input grid that the
    nested grid is derived from.

    Inputs 'geo_parent_i', 'geo_parent_j' and 'geo_parent_k' are geogrid properties
    that reference the IJK of the parent grid.

    For each refined parent cell:

    1. Identify geogrid cells mapped to that parent cell.
    2. Derive the corresponding refined block origin in nested-grid IJK.
    3. Compute each geogrid cell's local position within that refined block.
    4. Convert local positions into merged-grid IJK coordinates.

    Cells outside refined regions only require a K-layer remapping through
    the supplied layer mapping for the unrefined area.
    A zero on any input axis excludes that cell and leaves all output axes zero.

    Returns:
        A 3-tuple of mapped geogrid-to-nested-grid references, ordered as I, J, K.
    """

    expected_refined_cell_count = refinement.col * refinement.row * refinement.lay
    geo_dimensions = geo_parent_i_values.shape
    parent_ncol, parent_nrow, parent_nlay = parent_dimensions

    # ------------------------------------------------------------------
    # Build parent-cell identifiers for geogrid
    # ------------------------------------------------------------------

    geo_parent_i_values1d = geo_parent_i_values.ravel()
    geo_parent_j_values1d = geo_parent_j_values.ravel()
    geo_parent_k_values1d = geo_parent_k_values.ravel()

    geo_active = ~np.ma.getmaskarray(geo_parent_i_values1d)

    cells_to_map = geo_active & (
        (geo_parent_i_values1d > 0)
        & (geo_parent_j_values1d > 0)
        & (geo_parent_k_values1d > 0)
    )

    geo_parent_cell_indices = np.full(geo_parent_i_values1d.size, -1, dtype=np.intp)
    geo_parent_cell_indices[cells_to_map] = _ijk_to_flat_index(
        geo_parent_i_values1d[cells_to_map] - 1,
        geo_parent_j_values1d[cells_to_map] - 1,
        geo_parent_k_values1d[cells_to_map] - 1,
        parent_nrow,
        parent_nlay,
    )

    geo_cells_by_parent = CellsByParent.from_parent_indices(
        parent_indices=geo_parent_cell_indices,
        selected_mask=cells_to_map,
        parent_cell_count=parent_ncol * parent_nrow * parent_nlay,
    )

    # Validate that referenced parent cells actually exist
    if not np.all(
        nested_cells_by_parent.mapped_mask[geo_cells_by_parent.mapped_parent_indices]
    ):
        raise ValueError(
            "The input I/J/K mappings do not match the original coarse grid"
            "used to create this nested hybrid grid."
        )

    is_refined_parent_cell = (
        nested_cells_by_parent.counts == expected_refined_cell_count
    )
    refined_parent_indices = np.flatnonzero(is_refined_parent_cell)

    # ------------------------------------------------------------------
    # Prepare output arrays for geogrid-nested mapping
    # ------------------------------------------------------------------

    i_map_values = geo_parent_i_values1d.copy()
    j_map_values = geo_parent_j_values1d.copy()
    k_map_values = geo_parent_k_values1d.copy()

    i_map_values[~cells_to_map] = 0
    j_map_values[~cells_to_map] = 0
    k_map_values[~cells_to_map] = 0

    # Update layer mapping for non-refined cells
    k = k_map_values[cells_to_map].astype(np.intp) - 1
    k_map_values[cells_to_map] = layer_map_coarse[k] + 1

    # Lists to collect updates and apply them in one batch for performance
    geo_cell_updates: list[np.ndarray] = []
    i_updates: list[np.ndarray] = []
    j_updates: list[np.ndarray] = []
    k_updates: list[np.ndarray] = []

    # ------------------------------------------------------------------
    # Compute merged-grid IJK coordinates for refined regions
    # ------------------------------------------------------------------

    for parent_idx in refined_parent_indices:
        geo_cells = geo_cells_by_parent.get_indices(parent_idx)
        geo_i, geo_j, geo_k = np.unravel_index(geo_cells, geo_dimensions)

        geo_i_min = geo_i.min()
        geo_j_min = geo_j.min()
        geo_k_min = geo_k.min()

        geo_i_span = geo_i.max() - geo_i_min + 1
        geo_j_span = geo_j.max() - geo_j_min + 1
        geo_k_span = geo_k.max() - geo_k_min + 1

        n_geo_cells = geo_cells.size
        expected_geo_cells = geo_i_span * geo_j_span * geo_k_span

        if (
            geo_i_span % refinement.col != 0
            or geo_j_span % refinement.row != 0
            or geo_k_span % refinement.lay != 0
            or n_geo_cells != expected_geo_cells
        ):
            parent_i, parent_j, parent_k = np.unravel_index(
                parent_idx, parent_dimensions
            )
            raise ValueError(
                "Invalid input mapping for cells referencing parent cell IJK: "
                f"({parent_i}, {parent_j}, {parent_k}). Expected geogrid spans per "
                f"parent cell must be divisible by refinement {refinement}, got "
                f"spans (col={geo_i_span}, row={geo_j_span}, lay={geo_k_span})."
            )

        nested_cells = nested_cells_by_parent.get_indices(parent_idx)
        nested_i, nested_j, nested_k = np.unravel_index(nested_cells, nested_dimensions)

        geo_cells_per_nested_i = geo_i_span // refinement.col
        geo_cells_per_nested_j = geo_j_span // refinement.row
        geo_cells_per_nested_k = geo_k_span // refinement.lay

        i_out = (geo_i - geo_i_min) // geo_cells_per_nested_i + nested_i.min() + 1
        j_out = (geo_j - geo_j_min) // geo_cells_per_nested_j + nested_j.min() + 1
        k_out = (geo_k - geo_k_min) // geo_cells_per_nested_k + nested_k.min() + 1

        geo_cell_updates.append(geo_cells)
        i_updates.append(i_out)
        j_updates.append(j_out)
        k_updates.append(k_out)

    if geo_cell_updates:
        all_geo_cell = np.concatenate(geo_cell_updates)
        i_map_values[all_geo_cell] = np.concatenate(i_updates)
        j_map_values[all_geo_cell] = np.concatenate(j_updates)
        k_map_values[all_geo_cell] = np.concatenate(k_updates)

    return (
        i_map_values.reshape(geo_dimensions),
        j_map_values.reshape(geo_dimensions),
        k_map_values.reshape(geo_dimensions),
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


class NestedHybridGrid:
    """Class to build a nested hybrid grid with a refined target region.

    The target region is refined and merged back into the coarse grid.
    A **NNC mapping table** is computed that lists every coarse ↔ refined cell
    pair that should be connected by a Non-Neighbour Connection (NNC).
    """

    def __init__(
        self,
        coarse_grid: xtgeo.Grid,
        region: xtgeo.GridProperty,
        refinement: tuple[int, int, int],
        target_region_id: int = 1,
    ) -> None:
        """Create a NestedHybridGrid instance."""

        self._validate_inputs(coarse_grid, region, refinement, target_region_id)

        self._nnc_table: pd.DataFrame | None = None

        self._parent_grid = coarse_grid
        self._parent_dimensions = coarse_grid.dimensions
        self._parent_subgrids = coarse_grid.subgrids
        self._parent_region = region

        self._target_region_id = target_region_id
        self._refinement = Refinement.from_tuple(refinement)

        self._refined_area = region.values == target_region_id
        self._refined_bbox = BoundingBox.from_condition(self._refined_area)
        self._refined_nlay = self._get_num_refined_layers()

        self._layer_map_coarse = self._generate_layer_map_coarse()
        self._layer_map_refined = self._generate_layer_map_refined()

        self._grid = self._build_nested_hybrid_grid()
        self._nested_cells_by_parent: CellsByParent | None = None

    @classmethod
    def from_rms(
        cls,
        project: Any,
        grid_name: str,
        region_name: str,
        refinement: tuple[int, int, int],
        properties: list[str] | None = None,
        *,
        target_region_id: int = 1,
    ) -> Self:
        """Create a NestedHybridGrid instance from an RMS project.

        Args:
            project: RMS project instance.
            grid_name: Name of the grid in the RMS project.
            region_name: Name of the region property in the RMS project.
            refinement: Refinement factors as (ncol, nrow, nlay).
            properties: Optional list of property names to load from the project.
            target_region_id: Region value to refine (default: 1).
        """

        parent_grid = xtgeo.grid_from_roxar(project, grid_name)
        region = xtgeo.gridproperty_from_roxar(project, grid_name, region_name)

        for propname in properties or []:
            prop = xtgeo.gridproperty_from_roxar(project, grid_name, propname)
            parent_grid.append_prop(prop)

        return cls(parent_grid, region, refinement, target_region_id)

    def to_rms(self, project: Any, grid_name: str) -> None:
        """Write the nested hybrid grid and its properties to an RMS project."""
        self.grid.to_roxar(project, grid_name)

        for prop in self.properties:
            if prop.name not in ORIGINAL_IJK_PROPERTY_NAMES:
                prop.to_roxar(project, grid_name, prop.name)

    @staticmethod
    def _validate_inputs(
        parent_grid: xtgeo.Grid,
        region: xtgeo.GridProperty,
        refinement: tuple[int, int, int],
        target_region_id: int,
    ) -> None:
        """Validate input arguments."""
        if region.dimensions != parent_grid.dimensions:
            raise ValueError(
                f"Region property dimensions {region.dimensions} do not match "
                f"input grid dimensions {parent_grid.dimensions}"
            )

        if not (region.values == target_region_id).any():
            raise ValueError(
                f"No cells found for target_region_id={target_region_id} "
                f"in region property {region.name}"
            )

        if not isinstance(refinement, tuple) or len(refinement) != 3:
            raise ValueError(
                "Refinement must be a tuple of three integers: (rcol, rrow, rlay)"
            )

    def _build_nested_hybrid_grid(self) -> xtgeo.Grid:
        """Build the nested hybrid grid."""
        coarse_grid = self._parent_grid.copy()

        region_name = self._parent_region.name
        if region_name not in coarse_grid.propnames:
            coarse_grid.append_prop(self._parent_region)
        for prop in coarse_grid.get_ijk(names=ORIGINAL_IJK_PROPERTY_NAMES):
            coarse_grid.append_prop(prop)

        # Create the refined grid, i.e. crop and refine.
        refined_grid = _crop_for_region(coarse_grid, self._refined_bbox)
        refined_grid.refine(
            self._refinement.col, self._refinement.row, self._refinement.lay
        )

        # Deactivate outside the target region in the refined grid
        refined_region = refined_grid.get_prop_by_name(region_name)
        active_area = refined_region.values == self._target_region_id
        _set_actnum_in_grid(refined_grid, active_area)

        # Deactivate the target region in the coarse grid
        coarse_region = coarse_grid.get_prop_by_name(region_name)
        active_area = coarse_region.values != self._target_region_id
        _set_actnum_in_grid(coarse_grid, active_area)

        grid = xtgeo.grid_merge(
            grid1=coarse_grid,
            grid2=refined_grid,
            layer_map1=self._layer_map_coarse,
            layer_map2=self._layer_map_refined,
        )
        _logger.info("Merged grid dimensions: %s", grid.dimensions)

        grid.subgrids = self._set_zonation(grid.nlay)
        return grid

    @property
    def grid(self) -> xtgeo.Grid:
        """The final nested hybrid grid."""
        return self._grid

    @property
    def properties(self) -> list[xtgeo.GridProperty]:
        """The final nested hybrid grid properties."""
        return self.grid.props

    @property
    def nnc_table(self) -> pd.DataFrame:
        """Non-Neighbour Connection (NNC) mapping table."""
        if self._nnc_table is None:
            self._nnc_table = self._compute_nnc_table()
        return self._nnc_table

    @property
    def nested_cells_by_parent(self) -> CellsByParent:
        """Lazy mapping from parent-grid indices to active merged-grid cells."""
        if self._nested_cells_by_parent is None:
            self._nested_cells_by_parent = self._create_nested_cells_by_parent()
        return self._nested_cells_by_parent

    def _create_nested_cells_by_parent(self) -> CellsByParent:
        """Group active merged-grid cells by flattened parent-grid index."""
        parent_i = self._grid.get_prop_by_name("parent_I")
        parent_j = self._grid.get_prop_by_name("parent_J")
        parent_k = self._grid.get_prop_by_name("parent_K")

        parent_indices = _ijk_to_flat_index(
            i=parent_i.values - 1,
            j=parent_j.values - 1,
            k=parent_k.values - 1,
            jdim=self._parent_dimensions.nrow,
            kdim=self._parent_dimensions.nlay,
        )

        valid = ~np.ma.getmaskarray(parent_indices)
        return CellsByParent.from_parent_indices(
            parent_indices=parent_indices,
            selected_mask=valid,
            parent_cell_count=self._parent_grid.ntotal,
        )

    def create_upscaling_mappings(
        self,
        i_map: xtgeo.GridProperty,
        j_map: xtgeo.GridProperty,
        k_map: xtgeo.GridProperty,
    ) -> tuple[xtgeo.GridProperty, xtgeo.GridProperty, xtgeo.GridProperty]:
        """
        Method to remap geogrid-to-parent IJK references into
        geogrid-to-nestedgrid IJK references. These properties can in turn be used
        when upscaling properties from geogrid to the nested hybrid grid.

        Inputs 'i_map', 'j_map' and 'k_map' are geogrid properties
        that reference the IJK of the input grid that the nested grid is based on.
        The nested grid already contains the same parent grid references through the
        'parent_I', 'parent_J' and 'parent_K' properties.

        Returns:
            A 3-tuple of :class:`xtgeo.GridProperty` objects with mapped
            geogrid-to-nested-grid references, ordered as I, J, K.
        """

        _validate_create_upscaling_mapping_inputs(
            geo_parent_i=i_map,
            geo_parent_j=j_map,
            geo_parent_k=k_map,
            parent_dimensions=self._parent_dimensions,
        )
        i_map_values, j_map_values, k_map_values = _create_upscaling_mappings_arrays(
            geo_parent_i_values=i_map.values,
            geo_parent_j_values=j_map.values,
            geo_parent_k_values=k_map.values,
            nested_cells_by_parent=self.nested_cells_by_parent,
            nested_dimensions=self.grid.dimensions,
            parent_dimensions=self._parent_dimensions,
            layer_map_coarse=self._layer_map_coarse,
            refinement=self._refinement,
        )
        return (
            xtgeo.GridProperty(i_map, name="nested_I", values=i_map_values),
            xtgeo.GridProperty(j_map, name="nested_J", values=j_map_values),
            xtgeo.GridProperty(k_map, name="nested_K", values=k_map_values),
        )

    def write_nnc_table(self, filename: str | Path) -> None:
        """Write the NNC mapping table to CSV."""
        output_path = Path(filename)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        self.nnc_table.to_csv(output_path, index=False)

    def _compute_nnc_table(self) -> pd.DataFrame:
        """Compute the NNC mapping table."""
        return _compute_nnc_table(
            refined_area=self._refined_area,
            refinement=self._refinement,
            coarse_ncol=self._parent_dimensions.ncol,
            lmap1=self._layer_map_coarse,
            lmap2=self._layer_map_refined,
        )

    def _generate_layer_map_coarse(self) -> np.ndarray:
        """Map original coarse-layer indices to indices in the final merged grid.

        Layers below the refined K-window are unchanged; layers at/above the window are
        shifted to account for extra layers introduced by K-refinement.
        """
        rlay = self._refinement.lay
        k0 = self._refined_bbox.kmin - 1
        parent_nlay = self._parent_dimensions.nlay

        lmap = np.arange(parent_nlay, dtype=np.int32)
        return lmap + np.where(
            lmap < k0,
            0,
            (rlay - 1) * np.minimum(int(self._refined_nlay / rlay), lmap - k0),
        )

    def _generate_layer_map_refined(self) -> np.ndarray:
        """Map original refined grid layer indices to indices in the final merged grid.

        Refined layers are offset by the first layer index of the refined
        K-window in the original coarse grid.
        """
        lmap = np.arange(self._refined_nlay, dtype=np.int32)
        return lmap + self._refined_bbox.kmin - 1

    def _get_num_refined_layers(self) -> int:
        """Get the number of layers of the refined grid."""
        bbox = self._refined_bbox
        return (bbox.kmax - bbox.kmin + 1) * self._refinement.lay

    def _set_zonation(self, nlay: int) -> dict | None:
        """Create an updated subgrid dictionary for the merged grid."""
        subgrid = self._parent_subgrids
        if subgrid is None:
            return None

        lmap = self._layer_map_coarse

        updated_subgrid = {}

        # sorted list of zones to add
        zl = sorted(subgrid, key=lambda x: subgrid[x][0])

        for zi in range(len(zl)):
            zn = zl[zi]
            zmin = lmap[subgrid[zn][0] - 1] + 1
            zmax = (
                nlay + 1 if zi == len(zl) - 1 else lmap[subgrid[zl[zi + 1]][0] - 1] + 1
            )
            updated_subgrid[zn] = range(zmin, zmax)

        return updated_subgrid


def create_nested_hybrid_grid(
    grid: xtgeo.Grid,
    region: xtgeo.GridProperty,
    target_region_id: int,
    refinement: tuple[int, int, int],
) -> tuple[
    xtgeo.Grid,
    pd.DataFrame,
]:
    """Create a nested hybrid grid by refining one region and merging it back.

    The cells belonging to *target_region_id* are replaced by a refined
    (subdivided) version of the same region.

    A **NNC mapping table** is returned that lists every
    mother ↔ refined cell pair that should be connected by a Non-Neighbour
    Connection (NNC).  The table is derived from the topological knowledge
    available at merge time (which original cell was refined and how its
    sub-cells map into the merged grid).

    The table columns are:

    - ``I1, J1, K1``: mother cell indices (1-based) in the merged grid.
    - ``I2, J2, K2``: refined cell indices (1-based) in the merged grid.
    - ``DIRECTION``: face direction from the mother cell's perspective
      (``I+``, ``I-``, ``J+``, ``J-``, ``K+``, ``K-``).

    This table can be passed to
    :meth:`xtgeo.Grid.get_transmissibilities` to compute NNC
    transmissibilities for the specified cell pairs.

    Args:
        grid: The original coarse grid.
        region: A :class:`xtgeo.GridProperty` whose values identify the
            regions (e.g. an integer region parameter).
        target_region_id: The region value to refine.
        refinement: ``(ncol, nrow, nlay)`` refinement factors.

    Returns:
        A tuple ``(merged_grid, nnc_table)`` where *merged_grid*
        is a new :class:`xtgeo.Grid` with the refined region stitched back into
        the coarse grid and *nnc_table* is a :class:`pandas.DataFrame` mapping
        mother cells to their connected refined cells.
    """
    warnings.warn(
        "create_nested_hybrid_grid is currently experimental. It may undergo "
        "breaking changes in future versions without notice.",
        FutureWarning,
    )

    nhg = NestedHybridGrid(
        coarse_grid=grid,
        region=region,
        refinement=refinement,
        target_region_id=target_region_id,
    )

    return nhg.grid, nhg.nnc_table


def nnc_to_gridproperty(
    grid: xtgeo.Grid,
    nnc_df: pd.DataFrame,
) -> tuple[xtgeo.GridProperty, xtgeo.GridProperty, xtgeo.GridProperty]:
    """Convert NNC transmissibility data to three GridProperty instances.

    Takes the NNC DataFrame produced by :meth:`xtgeo.Grid.get_transmissibilities`
    and maps transmissibility values onto grid cells, producing one property per
    direction (I, J, K).

    For rows where DIRECTION contains ``"+"``, the transmissibility value is
    placed in cell ``(I1, J1, K1)``.  For rows where DIRECTION contains
    ``"-"``, the value is placed in cell ``(I2, J2, K2)``.  Index columns
    (I1, J1, K1, I2, J2, K2) are expected to be **1-based**.

    If multiple rows map to the same cell and direction, the transmissibility
    values are summed (parallel flow paths are additive).

    Args:
        grid: The xtgeo Grid that defines the geometry.
        nnc_df: A DataFrame with at least columns
            ``I1, J1, K1, I2, J2, K2, T, DIRECTION``.

    Returns:
        A tuple ``(tranx_nnc, trany_nnc, tranz_nnc)`` of
        :class:`xtgeo.GridProperty` instances named ``"TRANX_NNC"``,
        ``"TRANY_NNC"``, and ``"TRANZ_NNC"`` respectively.
        Cells without an NNC value are set to ``-1.0``.
    """
    required_cols = {"I1", "J1", "K1", "I2", "J2", "K2", "T", "DIRECTION"}
    missing = required_cols - set(nnc_df.columns)
    if missing:
        raise ValueError(f"Missing required columns in nnc_df: {missing}")

    ncol, nrow, nlay = grid.ncol, grid.nrow, grid.nlay
    fill = -1.0

    arrays = {
        "I": np.zeros((ncol, nrow, nlay), dtype=np.float64),
        "J": np.zeros((ncol, nrow, nlay), dtype=np.float64),
        "K": np.zeros((ncol, nrow, nlay), dtype=np.float64),
    }
    touched = {
        "I": np.zeros((ncol, nrow, nlay), dtype=bool),
        "J": np.zeros((ncol, nrow, nlay), dtype=bool),
        "K": np.zeros((ncol, nrow, nlay), dtype=bool),
    }

    direction_col = nnc_df["DIRECTION"].astype(str)
    is_plus = direction_col.str.contains(r"\+", regex=True)
    is_minus = direction_col.str.contains("-")
    prefix_col = direction_col.str[0].str.upper()

    for prefix in ("I", "J", "K"):
        arr = arrays[prefix]
        tch = touched[prefix]
        mask_prefix = prefix_col == prefix

        # "+" rows → use (I1, J1, K1)
        sel_plus = nnc_df.loc[mask_prefix & is_plus]
        if not sel_plus.empty:
            ii = sel_plus["I1"].values.astype(int) - 1
            jj = sel_plus["J1"].values.astype(int) - 1
            kk = sel_plus["K1"].values.astype(int) - 1
            tt = sel_plus["T"].values.astype(float)
            valid = (
                (ii >= 0)
                & (ii < ncol)
                & (jj >= 0)
                & (jj < nrow)
                & (kk >= 0)
                & (kk < nlay)
            )
            np.add.at(arr, (ii[valid], jj[valid], kk[valid]), tt[valid])
            tch[ii[valid], jj[valid], kk[valid]] = True

        # "-" rows → use (I2, J2, K2)
        sel_minus = nnc_df.loc[mask_prefix & is_minus]
        if not sel_minus.empty:
            ii = sel_minus["I2"].values.astype(int) - 1
            jj = sel_minus["J2"].values.astype(int) - 1
            kk = sel_minus["K2"].values.astype(int) - 1
            tt = sel_minus["T"].values.astype(float)
            valid = (
                (ii >= 0)
                & (ii < ncol)
                & (jj >= 0)
                & (jj < nrow)
                & (kk >= 0)
                & (kk < nlay)
            )
            np.add.at(arr, (ii[valid], jj[valid], kk[valid]), tt[valid])
            tch[ii[valid], jj[valid], kk[valid]] = True

        # Set untouched cells to fill value
        arr[~tch] = fill

    prop_names = {"I": "TRANX_NNC", "J": "TRANY_NNC", "K": "TRANZ_NNC"}
    props = {}
    for prefix in ("I", "J", "K"):
        props[prefix] = xtgeo.GridProperty(
            grid,
            name=prop_names[prefix],
            values=np.ma.array(arrays[prefix]),
            discrete=False,
        )

    return props["I"], props["J"], props["K"]


def nnc_to_flowsimulator_input(
    nnc_df: pd.DataFrame,
    filepath: str | os.PathLike[str],
) -> None:
    """Write NNC transmissibilities to a flow-simulator input file.

    Produces a file with the ``NNC`` keyword suitable for reservoir
    simulators that use Eclipse-style input decks, such as Eclipse and
    OPM Flow.  The file can be included in the deck via ``INCLUDE``.
    Each row of *nnc_df* becomes one NNC record with the six cell
    indices and the transmissibility value.

    Args:
        nnc_df: A DataFrame with at least columns
            ``I1, J1, K1, I2, J2, K2, T``.  Optional columns ``TYPE``
            and ``DIRECTION`` are written as end-of-line comments.
        filepath: Path to the output file.
    """
    required_cols = {"I1", "J1", "K1", "I2", "J2", "K2", "T"}
    missing = required_cols - set(nnc_df.columns)
    if missing:
        raise ValueError(f"Missing required columns in nnc_df: {missing}")

    has_type = "TYPE" in nnc_df.columns
    has_dir = "DIRECTION" in nnc_df.columns

    with open(filepath, "w") as f:
        f.write("NNC\n")
        for _, row in nnc_df.iterrows():
            line = (
                f"    {int(row['I1']):>4} {int(row['J1']):>4} {int(row['K1']):>4}"
                f"    {int(row['I2']):>4} {int(row['J2']):>4} {int(row['K2']):>4}"
                f"   {row['T']:.6f}  /"
            )
            comment_parts = []
            if has_type:
                comment_parts.append(str(row["TYPE"]))
            if has_dir:
                comment_parts.append(str(row["DIRECTION"]))
            if comment_parts:
                line += "  -- " + " ".join(comment_parts)
            f.write(line + "\n")
        f.write("/\n")

    _logger.info("NNC keyword written to %s", filepath)
