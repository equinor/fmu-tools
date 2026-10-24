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

from dataclasses import dataclass
import logging
import warnings
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, Self, TypeAlias, TypeVar

import numpy as np
import pandas as pd
import xtgeo
from pydantic import BaseModel, Field, ValidationError

if TYPE_CHECKING:
    import os

    from xtgeo.common.types import Dimensions


_logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
FaceDirection: TypeAlias = Literal["I+", "I-", "J+", "J-", "K+", "K-"]

IJKIndex: TypeAlias = tuple[int, int, int]
IndexLike = TypeVar("IndexLike", int, np.ndarray)
BoundaryCellFace: TypeAlias = tuple[int, int, FaceDirection]
ORIGINAL_IJK_PROPERTY_NAMES = ("parent_I", "parent_J", "parent_K")

_FACE_OPPOSITES: dict[FaceDirection, FaceDirection] = {
    "I+": "I-",
    "I-": "I+",
    "J+": "J-",
    "J-": "J+",
    "K+": "K-",
    "K-": "K+",
}


@dataclass(frozen=True)
class ParentCellMapping:
    nested_indices: np.ndarray
    starts: np.ndarray
    stops: np.ndarray

    @classmethod
    def from_parent_indices(
        cls,
        parent_indices: np.ndarray,
        selected_mask: np.ndarray,
        n_parent_cells: int,
    ) -> Self:
        selected_parent_indices = parent_indices[selected_mask]
        selected_nested_indices = np.flatnonzero(selected_mask)

        if selected_parent_indices.size == 0:
            raise ValueError("No selected parent indices found.")

        sort_order = np.argsort(selected_parent_indices)

        sorted_parent_indices = selected_parent_indices[sort_order]
        sorted_nested_indices = selected_nested_indices[sort_order]

        # Identify the boundaries between groups of the same parent index
        cuts = np.flatnonzero(np.diff(sorted_parent_indices)) + 1

        group_starts = np.r_[0, cuts]
        group_stops = np.r_[cuts, sorted_parent_indices.size]
        parent_indices = sorted_parent_indices[group_starts]

        starts = np.full(n_parent_cells, -1, dtype=np.intp)
        stops = np.full(n_parent_cells, -1, dtype=np.intp)

        starts[parent_indices] = group_starts
        stops[parent_indices] = group_stops

        return cls(
            nested_indices=sorted_nested_indices,
            starts=starts,
            stops=stops,
        )

    def get(self, parent_idx: int) -> np.ndarray | None:
        start = self.starts[parent_idx]

        if start == -1:
            return None

        return self.nested_indices[start : self.stops[parent_idx]]


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


def _get_cell_boundary_mask(
    ii: np.ndarray,
    jj: np.ndarray,
    kk: np.ndarray,
    direction: FaceDirection,
) -> np.ndarray:
    """Return a boolean face-selection mask from precomputed I, J, K arrays."""

    if direction == "I-":
        return ii == ii.min()
    if direction == "I+":
        return ii == ii.max()
    if direction == "J-":
        return jj == jj.min()
    if direction == "J+":
        return jj == jj.max()
    if direction == "K-":
        return kk == kk.min()
    if direction == "K+":
        return kk == kk.max()
    raise ValueError(f"Unexpected face direction: {direction}")


def _find_boundary_faces(
    refined_area: np.ma.MaskedArray,
) -> list[BoundaryCellFace]:
    """Find cell faces on the boundary of a refinement area.

    Args:
        refined_area: 3D boolean array where ``True`` marks cells to refine.

    Returns:
        A list of ``(outside_idx, inside_idx, face_dir)`` where indices are
        flattened parent-grid cell indices. ``face_dir`` is from the inside
        (refined) cell perspective.
    """
    _, nrow, nlay = refined_area.shape
    active = ~refined_area.mask

    inside_active = refined_area & active
    outside_active = ~refined_area & active

    faces: list[BoundaryCellFace] = []

    def add_face(
        ijk_outside: IJKIndex,
        ijk_inside: IJKIndex,
        face_direction: FaceDirection,
    ):
        outside_idx = _ijk_to_flat_index(*ijk_outside, jdim=nrow, kdim=nlay)
        inside_idx = _ijk_to_flat_index(*ijk_inside, jdim=nrow, kdim=nlay)

        faces.append((int(outside_idx), int(inside_idx), face_direction))

    # i+
    mask = inside_active[:-1, :, :] & outside_active[1:, :, :]
    for i, j, k in np.argwhere(mask):
        add_face((i + 1, j, k), (i, j, k), "I+")

    # i-
    mask = inside_active[1:, :, :] & outside_active[:-1, :, :]
    for i, j, k in np.argwhere(mask):
        add_face((i, j, k), (i + 1, j, k), "I-")

    # j+
    mask = inside_active[:, :-1, :] & outside_active[:, 1:, :]
    for i, j, k in np.argwhere(mask):
        add_face((i, j + 1, k), (i, j, k), "J+")

    # j-
    mask = inside_active[:, 1:, :] & outside_active[:, :-1, :]
    for i, j, k in np.argwhere(mask):
        add_face((i, j, k), (i, j + 1, k), "J-")

    # k+
    mask = inside_active[:, :, :-1] & outside_active[:, :, 1:]
    for i, j, k in np.argwhere(mask):
        add_face((i, j, k + 1), (i, j, k), "K+")

    # k-
    mask = inside_active[:, :, 1:] & outside_active[:, :, :-1]
    for i, j, k in np.argwhere(mask):
        add_face((i, j, k), (i, j, k + 1), "K-")

    _logger.info("Found %d boundary faces for refinement area", len(faces))
    return faces


def _compute_nnc_table(
    refined_area: np.ma.MaskedArray,
    parent_cell_mapping: ParentCellMapping,
    nested_dimensions: Dimensions,
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
        parent_cell_mapping: Mapping from parent cell indices to merged grid indices.
        nested_dimensions: Dimensions of the merged grid.

    Returns:
        A DataFrame with columns ``I1, J1, K1, I2, J2, K2, DIRECTION``.
    """
    faces = _find_boundary_faces(refined_area)
    rows: list[dict[str, int | str]] = []

    for outside_idx, inside_idx, direction in faces:
        outside_cells = parent_cell_mapping.get(outside_idx)
        refined_cells = parent_cell_mapping.get(inside_idx)

        if outside_cells is None or refined_cells is None:
            # Missing mapping means one side is inactive.
            # Such boundaries should not produce NNC connections.
            continue

        if outside_cells.size != 1:
            raise ValueError(
                "Expected exactly one merged-grid cell for unrefined parent "
                f"{outside_idx}, found {outside_cells.size}."
            )

        outside_i, outside_j, outside_k = np.unravel_index(
            outside_cells[0], nested_dimensions
        )
        refined_i, refined_j, refined_k = np.unravel_index(
            refined_cells, nested_dimensions
        )

        boundary_mask = _get_cell_boundary_mask(
            refined_i, refined_j, refined_k, direction
        )

        for ri, rj, rk in zip(
            refined_i[boundary_mask],
            refined_j[boundary_mask],
            refined_k[boundary_mask],
        ):
            rows.append(
                {
                    "I1": int(outside_i) + 1,
                    "J1": int(outside_j) + 1,
                    "K1": int(outside_k) + 1,
                    "I2": int(ri) + 1,
                    "J2": int(rj) + 1,
                    "K2": int(rk) + 1,
                    "DIRECTION": _FACE_OPPOSITES[direction],
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
    i: IndexLike, j: IndexLike, k: IndexLike, jdim: int, kdim: int
) -> IndexLike:
    """Convert 0-based (i, j, k) indices to positions in a 1D flattened array.
    This follows NumPy C-order (row-major) indexing.
    """
    return i * jdim * kdim + j * kdim + k


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

        self._original_grid = coarse_grid
        self._original_dimensions = coarse_grid.dimensions
        self._original_subgrids = coarse_grid.subgrids
        self._original_region = region

        self._target_region_id = target_region_id
        self._refinement = Refinement.from_tuple(refinement)

        self._refined_area = region.values == target_region_id
        self._refined_bbox = BoundingBox.from_condition(self._refined_area)
        self._refined_nlay = self._get_num_refined_layers()

        self._layer_map_coarse = self._generate_layer_map_coarse()
        self._layer_map_refined = self._generate_layer_map_refined()

        self._grid = self._build_nested_hybrid_grid()
        self._parent_cell_mapping: ParentCellMapping | None = None

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

        coarse_grid = xtgeo.grid_from_roxar(project, grid_name)
        region = xtgeo.gridproperty_from_roxar(project, grid_name, region_name)

        for propname in properties or []:
            prop = xtgeo.gridproperty_from_roxar(project, grid_name, propname)
            coarse_grid.append_prop(prop)

        return cls(coarse_grid, region, refinement, target_region_id)

    def to_rms(self, project: Any, grid_name: str) -> None:
        """Write the nested hybrid grid and its properties to an RMS project."""
        self.grid.to_roxar(project, grid_name)

        for prop in self.properties:
            if prop.name not in ORIGINAL_IJK_PROPERTY_NAMES:
                prop.to_roxar(project, grid_name, prop.name)

    @staticmethod
    def _validate_inputs(
        coarse_grid: xtgeo.Grid,
        region: xtgeo.GridProperty,
        refinement: tuple[int, int, int],
        target_region_id: int,
    ) -> None:
        """Validate input arguments."""
        if region.dimensions != coarse_grid.dimensions:
            raise ValueError(
                f"Region property dimensions {region.dimensions} do not match "
                f"input grid dimensions {coarse_grid.dimensions}"
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
        coarse_grid = self._original_grid.copy()

        region_name = self._original_region.name
        if region_name not in coarse_grid.propnames:
            coarse_grid.append_prop(self._original_region)
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
    def dimensions(self) -> Dimensions:
        """The final nested hybrid grid dimensions."""
        return self._grid.dimensions

    @property
    def nnc_table(self) -> pd.DataFrame:
        """Non-Neighbour Connection (NNC) mapping table."""
        if self._nnc_table is None:
            self._nnc_table = self._compute_nnc_table()
        return self._nnc_table

    def write_nnc_table(self, filename: str | Path) -> None:
        """Write the NNC mapping table to CSV."""
        output_path = Path(filename)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        self.nnc_table.to_csv(output_path, index=False)

    @property
    def parent_cell_mapping(self) -> ParentCellMapping:
        """Lazy mapping from parent-grid indices to active merged-grid cells."""
        if self._parent_cell_mapping is None:
            self._parent_cell_mapping = self._create_parent_cell_mapping()
        return self._parent_cell_mapping

    def _compute_nnc_table(self) -> pd.DataFrame:
        """Compute the NNC mapping table."""
        return _compute_nnc_table(
            refined_area=self._refined_area,
            parent_cell_mapping=self.parent_cell_mapping,
            nested_dimensions=self.dimensions,
        )

    def _generate_layer_map_coarse(self) -> np.ndarray:
        """Map original coarse-layer indices to indices in the final merged grid.

        Layers below the refined K-window are unchanged; layers at/above the window are
        shifted to account for extra layers introduced by K-refinement.
        """
        rlay = self._refinement.lay
        k0 = self._refined_bbox.kmin - 1
        coarse_nlay = self._original_dimensions.nlay

        lmap = np.arange(coarse_nlay, dtype=np.int32)
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
        subgrid = self._original_subgrids
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

    def _create_parent_cell_mapping(self) -> ParentCellMapping:
        """Group active merged-grid cells by flattened parent-grid index."""
        parent_i = self._grid.get_prop_by_name("parent_I")
        parent_j = self._grid.get_prop_by_name("parent_J")
        parent_k = self._grid.get_prop_by_name("parent_K")

        parent_indices = _ijk_to_flat_index(
            i=parent_i.values - 1,
            j=parent_j.values - 1,
            k=parent_k.values - 1,
            jdim=self._original_dimensions.nrow,
            kdim=self._original_dimensions.nlay,
        )

        valid = ~np.ma.getmaskarray(parent_indices)
        return ParentCellMapping.from_parent_indices(
            parent_indices=parent_indices,
            selected_mask=valid,
            n_parent_cells=self._original_grid.ntotal,
        )


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
