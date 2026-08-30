"""Nested hybrid grid creation.

Create a merged grid where one region is refined (subdivided) and stitched
back into the original grid via Non-Neighbour Connections (NNCs).

Public API
----------
NestedHybridGrid : class
    Build a nested hybrid grid and, optionally, rewrite upscaling maps so
    that they address the merged grid (see the ``upscale_map`` property).
create_nested_hybrid_grid : function
    Convenience wrapper around :class:`NestedHybridGrid` returning the merged
    grid and the NNC table.
nnc_to_gridproperty : function
    Convert NNC transmissibility DataFrames to GridProperty instances.
nnc_to_flowsimulator_input : function
    Write NNC transmissibilities to a flow-simulator input file.
"""

from __future__ import annotations

import logging
import warnings
from typing import TYPE_CHECKING, Literal, Self, TypeAlias

import numpy as np
import pandas as pd
import xtgeo
from pydantic import BaseModel, ConfigDict, Field, ValidationError

if TYPE_CHECKING:
    import os
    from collections.abc import Iterable

_logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

FaceDirection: TypeAlias = Literal["i+", "i-", "j+", "j-", "k+", "k-"]
IJKIndex: TypeAlias = tuple[int, int, int]
BoundaryCellFace: TypeAlias = tuple[IJKIndex, IJKIndex, FaceDirection]


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


class Upscale(BaseModel):
    """An (I, J, K) triplet of upscaling maps defined on the geogrid.

    Each property holds, for every geogrid cell, the **1-based** index of the
    grid cell it upscales to.  A value of ``0`` means "exclude this geogrid
    cell from upscaling".

    Note that assigning a plain :class:`numpy.ndarray` to
    ``GridProperty.values`` discards the property mask, so masked input is
    carried through explicitly as masked arrays.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    imap: xtgeo.GridProperty
    jmap: xtgeo.GridProperty
    kmap: xtgeo.GridProperty

    @classmethod
    def from_tuple(
        cls,
        upscaling: tuple[xtgeo.GridProperty, xtgeo.GridProperty, xtgeo.GridProperty],
    ) -> Self:
        """Create an upscaling model from an ``(imap, jmap, kmap)`` 3-tuple."""
        imap, jmap, kmap = upscaling
        return cls(imap=imap, jmap=jmap, kmap=kmap)

    def as_tuple(
        self,
    ) -> tuple[xtgeo.GridProperty, xtgeo.GridProperty, xtgeo.GridProperty]:
        """Return the maps as an ``(imap, jmap, kmap)`` 3-tuple."""
        return (self.imap, self.jmap, self.kmap)


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


def _zero_based_source_indices(
    up: Upscale,
) -> tuple[np.ma.MaskedArray, np.ma.MaskedArray, np.ma.MaskedArray]:
    """Flatten the 1-based upscaling maps into 0-based index arrays.

    A value of ``0`` in the input (meaning "exclude this geogrid cell") becomes
    ``-1``.  The property masks are deliberately preserved: they are carried
    all the way through to the output properties.
    """
    return (
        up.imap.values.reshape(-1) - 1,
        up.jmap.values.reshape(-1) - 1,
        up.kmap.values.reshape(-1) - 1,
    )


def _validate_source_indices(
    iv: np.ma.MaskedArray,
    jv: np.ma.MaskedArray,
    kv: np.ma.MaskedArray,
    region: xtgeo.GridProperty,
) -> None:
    """Check that every mapped index lies inside the input grid.

    Raises:
        ValueError: if any axis maps outside ``0 .. n`` (1-based, 0 = excluded).
    """
    for axis, values, size in (
        ("I", iv, region.ncol),
        ("J", jv, region.nrow),
        ("K", kv, region.nlay),
    ):
        if values.min() < -1 or values.max() >= size:
            raise ValueError(
                "Invalid input upscaling relationships: "
                f"{axis} map values must lie between 0 (excluded) and {size}, "
                f"but range from {values.min() + 1:.0f} to {values.max() + 1:.0f}"
            )


def _map_geogrid_to_input_cells(
    iv: np.ma.MaskedArray,
    jv: np.ma.MaskedArray,
    kv: np.ma.MaskedArray,
    region: xtgeo.GridProperty,
) -> tuple[np.ndarray, np.ndarray]:
    """Resolve, for every geogrid cell, the input-grid cell it maps to.

    Args:
        iv, jv, kv: Flattened 0-based index maps, ``-1`` meaning "excluded".
        region: Region property, used only for the input grid dimensions.

    Returns:
        ``(flat_index, valid)`` where *flat_index* is a C-order flat index into
        the input grid (undefined where *valid* is ``False``) and *valid* marks
        geogrid cells that carry a usable mapping.
    """
    excluded = (iv == -1) | (jv == -1) | (kv == -1)
    # Masked entries in any of the three maps count as excluded.
    valid = ~np.ma.filled(excluded, True)

    # TODO: geogrid cells that map onto an *inactive* input-grid cell should
    # also be excluded here, but never were: the original implementation used
    # chained fancy indexing (``iv[~mask][...] = -1``), which writes into a
    # temporary copy and is therefore a silent no-op.  Preserved as-is on
    # purpose; see the accompanying refactoring report for the analysis and a
    # suggested fix.

    flat = np.zeros(iv.size, dtype=np.intp)
    flat[valid] = np.ravel_multi_index(
        (
            iv[valid].astype(np.intp),
            jv[valid].astype(np.intp),
            kv[valid].astype(np.intp),
        ),
        region.dimensions,
    )
    return flat, valid


def _target_region_mask(
    region: xtgeo.GridProperty, target_region_id: int
) -> np.ndarray:
    """Boolean 3D mask of input-grid cells belonging to the target region.

    Masked (inactive) cells are treated as *not* belonging to the region.
    """
    return np.ma.filled(region.values == target_region_id, False)


def _geogrid_cells_in_target(
    flat_index: np.ndarray,
    valid: np.ndarray,
    in_target: np.ndarray,
) -> np.ndarray:
    """Boolean mask of geogrid cells whose input cell is in the target region."""
    geo_in_target = np.zeros(valid.shape, dtype=bool)
    geo_in_target[valid] = in_target.reshape(-1)[flat_index[valid]]
    return geo_in_target


def _derive_geo_per_coarse(
    in_target: np.ndarray,
    geo_in_target: np.ndarray,
    geo_shape: tuple[int, int, int],
    refinement: Refinement,
) -> tuple[int, int, int]:
    """Derive how many geogrid cells cover one input-grid cell, per axis.

    The target region is counted along each axis both on the input grid and on
    its geogrid image; the quotient is the number of geogrid cells per input
    cell.  It must be a whole multiple of the corresponding refinement factor,
    otherwise the refined sub-grid cannot be addressed from the geogrid.

    Raises:
        ValueError: if the two grids do not correspond on some axis.
    """
    geo_in_target_3d = geo_in_target.reshape(geo_shape)
    factors = (refinement.col, refinement.row, refinement.lay)

    per_coarse = []
    for axis, (name, factor) in enumerate(zip("IJK", factors)):
        others = tuple(other for other in range(3) if other != axis)
        n_input = int(in_target.any(axis=others).sum())
        n_geo = int(geo_in_target_3d.any(axis=others).sum())

        if n_input == 0 or n_geo % n_input or (n_geo // n_input) % factor:
            raise ValueError(
                "Invalid correspondence upscaling between geogrid and input "
                f"grid: the {name} axis spans {n_geo} geogrid cells for "
                f"{n_input} input cells, which is not a whole multiple of the "
                f"refinement factor {factor}"
            )
        per_coarse.append(n_geo // n_input)

    return (per_coarse[0], per_coarse[1], per_coarse[2])


def _refined_block_indices(
    offset: BoundingBox,
    refinement: Refinement,
    geo_per_coarse: tuple[int, int, int],
    coarse_ncol: int,
) -> tuple[tuple[np.ndarray, ...], tuple[np.ndarray, ...]]:
    """Index maps for the geogrid block covering the refined bounding box.

    The block spans exactly the geogrid cells lying inside the refinement
    bounding box.  For every such cell two 0-based ijk triplets are produced:

    * *source*: the input-grid cell it was upscaled from;
    * *dest*: the cell it maps to in the merged grid, where the refined
      sub-grid is appended after the coarse columns plus a one-column gap.

    Args:
        offset: 1-based bounding box of the refined region in the input grid.
        refinement: Refinement factors applied to the target region.
        geo_per_coarse: Geogrid cells per input cell along each axis.
        coarse_ncol: Column count of the coarse grid within the merged grid.

    Returns:
        ``(source_ijk, dest_ijk)``, each a 3-tuple of 3D integer arrays.
    """
    origin = (offset.imin - 1, offset.jmin - 1, offset.kmin - 1)
    ncells = (
        offset.imax - origin[0],
        offset.jmax - origin[1],
        offset.kmax - origin[2],
    )
    factors = (refinement.col, refinement.row, refinement.lay)
    # Geogrid cells per *refined* cell; a whole number because geo_per_coarse
    # is a multiple of the refinement factor (checked in _derive_geo_per_coarse).
    geo_per_refined = tuple(g // f for g, f in zip(geo_per_coarse, factors))

    block = tuple(n * g for n, g in zip(ncells, geo_per_coarse))
    gi, gj, gk = np.indices(block, dtype=np.int32)

    source_ijk = (
        gi // geo_per_coarse[0] + origin[0],
        gj // geo_per_coarse[1] + origin[1],
        gk // geo_per_coarse[2] + origin[2],
    )
    dest_ijk = (
        gi // geo_per_refined[0] + coarse_ncol + 1,
        gj // geo_per_refined[1],
        gk // geo_per_refined[2] + origin[2],
    )
    return source_ijk, dest_ijk


def _modify_upscaling_mapping(
    up: Upscale,
    region: xtgeo.GridProperty,
    target_region_id: int,
    refinement: Refinement,
    offset: BoundingBox,
    lmap: np.ndarray,
) -> Upscale:
    """Rewrite upscaling maps so that they target the merged grid.

    The input maps address the original (coarse) grid.  In the merged grid the
    cells of the target region have been replaced by a refined sub-grid that is
    appended after the coarse columns, and the layers outside the refined
    K-window have been renumbered.  This function rewrites each geogrid cell's
    mapping accordingly:

    * cells outside the target region only need their layer index remapped
      through *lmap*;
    * cells inside the target region are redirected to the corresponding
      refined cell in the appended sub-grid.

    Args:
        up: Upscaling maps addressing the original grid (1-based, 0 = excluded).
        region: Region property on the original grid.
        target_region_id: The region value that was refined.
        refinement: Refinement factors applied to the target region.
        offset: 1-based bounding box of the refined region.
        lmap: Layer map from original coarse layer to merged-grid layer.

    Returns:
        A new :class:`Upscale` addressing the merged grid.
    """
    imap, jmap, kmap = (prop.copy() for prop in up.as_tuple())
    iv, jv, kv = _zero_based_source_indices(up)

    _validate_source_indices(iv, jv, kv, region)

    flat_index, valid = _map_geogrid_to_input_cells(iv, jv, kv, region)
    in_target = _target_region_mask(region, target_region_id)
    geo_in_target = _geogrid_cells_in_target(flat_index, valid, in_target)

    geo_shape = up.imap.values.shape
    geo_per_coarse = _derive_geo_per_coarse(
        in_target, geo_in_target, geo_shape, refinement
    )
    _logger.info(
        "Upscaling: %d of %d geogrid cells mapped, %d inside the target region; "
        "geogrid cells per input cell: %s",
        int(valid.sum()),
        valid.size,
        int(geo_in_target.sum()),
        geo_per_coarse,
    )

    # Outside the target region only the layer numbering changes.
    unrefined = valid & ~geo_in_target
    kv[unrefined] = lmap[kv[unrefined].astype(np.int32)]

    # Inside the target region, redirect to the appended refined sub-grid.
    source_ijk, dest_ijk = _refined_block_indices(
        offset, refinement, geo_per_coarse, region.ncol
    )
    selected = in_target[source_ijk]

    # The scatter below pairs geogrid cells with block cells positionally: both
    # are enumerated in C order, so the counts must agree. This holds by
    # construction, but a mismatch would otherwise corrupt the maps silently.
    if int(selected.sum()) != int(geo_in_target.sum()):
        raise ValueError(
            "Inconsistent upscaling mapping: "
            f"{int(geo_in_target.sum())} geogrid cells fall in the target region "
            f"but {int(selected.sum())} refined cells were addressed"
        )

    iv[geo_in_target] = dest_ijk[0][selected]
    jv[geo_in_target] = dest_ijk[1][selected]
    kv[geo_in_target] = dest_ijk[2][selected]

    for prop, values in ((imap, iv), (jmap, jv), (kmap, kv)):
        prop.values = values.reshape(prop.values.shape).astype(np.float32) + 1.0

    return Upscale(imap=imap, jmap=jmap, kmap=kmap)


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
        upscaling: tuple[xtgeo.GridProperty, xtgeo.GridProperty, xtgeo.GridProperty]
        | None = None,
    ) -> None:
        """Create a NestedHybridGrid instance.

        Args:
            coarse_grid: The original coarse grid.
            region: A :class:`xtgeo.GridProperty` whose values identify the
                regions (e.g. an integer region parameter).
            refinement: ``(ncol, nrow, nlay)`` refinement factors.
            target_region_id: The region value to refine.
            upscaling: Optional ``(imap, jmap, kmap)`` properties defined on a
                geogrid, holding 1-based indices of the coarse-grid cell each
                geogrid cell upscales to (``0`` excludes the cell).  When
                given, :attr:`upscale_map` returns the same maps rewritten to
                address the merged grid.
        """

        self._validate_inputs(coarse_grid, region, refinement, target_region_id)

        self._nnc_table: pd.DataFrame | None = None
        self._grid: xtgeo.Grid | None = None
        self._upscale: Upscale | None = None
        self._upscaled: Upscale | None = None

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

        if upscaling is not None:
            self._upscale = Upscale.from_tuple(upscaling)

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
        coarse_grid.append_prop(self._original_region)

        region_name = self._original_region.name

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
        if self._grid is None:
            self._grid = self._build_nested_hybrid_grid()
        return self._grid

    @property
    def properties(self) -> xtgeo.Grid:
        """The final nested hybrid grid properties."""
        return self.grid.props

    @property
    def nnc_table(self) -> pd.DataFrame:
        """Non-Neighbour Connection (NNC) mapping table."""
        if self._nnc_table is None:
            self._nnc_table = self._compute_nnc_table()
        return self._nnc_table

    @property
    def upscale_map(
        self,
    ) -> tuple[xtgeo.GridProperty, xtgeo.GridProperty, xtgeo.GridProperty]:
        """Upscaling maps rewritten from the geogrid to the merged grid.

        The returned ``(imap, jmap, kmap)`` properties are defined on the same
        geogrid as the ``upscaling`` argument passed to the constructor, and
        hold **1-based** indices into the merged grid.  A value of ``0`` means
        the geogrid cell is excluded from upscaling.

        The result is computed on first access and cached.

        Raises:
            ValueError: if the instance was created without ``upscaling``.
        """
        if self._upscaled is None:
            self._upscaled = self._update_upscaling()
        return self._upscaled.as_tuple()

    def _compute_nnc_table(self) -> pd.DataFrame:
        """Compute the NNC mapping table."""
        return _compute_nnc_table(
            refined_area=self._refined_area,
            refinement=self._refinement,
            coarse_ncol=self._original_dimensions.ncol,
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

    def _update_upscaling(self) -> Upscale:
        """Rewrite the input upscaling maps to address the merged grid."""
        if self._upscale is None:
            raise ValueError("No input data given for upscaling.")
        return _modify_upscaling_mapping(
            self._upscale,
            self._original_region,
            self._target_region_id,
            self._refinement,
            self._refined_bbox,
            self._layer_map_coarse,
        )

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
