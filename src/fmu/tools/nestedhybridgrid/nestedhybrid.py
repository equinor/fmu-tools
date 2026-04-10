"""Nested hybrid grid creation.

Create a merged grid where one region is refined (subdivided) and stitched
back into the original grid via Non-Neighbour Connections (NNCs).

Public API
----------
create_nested_hybrid_grid : function
    Build a nested hybrid grid from a coarse grid, a region property,
    and a refinement specification.
"""

from __future__ import annotations

import logging

import numpy as np
import xtgeo

_logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _crop_for_region(
    grid: xtgeo.Grid,
    region: xtgeo.GridProperty,
    region_id: int,
) -> tuple[xtgeo.Grid, tuple[int, int, int]]:
    """Crop *grid* to the bounding box of *region_id*.

    Returns (cropped_grid, crop_origin) where *crop_origin* is the 0-based
    (i, j, k) offset of the crop start inside the original grid.
    """
    region_values = region.values
    region_indices = np.where(region_values == region_id)

    imin = int(region_indices[0].min() + 1)
    imax = int(region_indices[0].max() + 1)
    jmin = int(region_indices[1].min() + 1)
    jmax = int(region_indices[1].max() + 1)
    kmin = int(region_indices[2].min() + 1)
    kmax = int(region_indices[2].max() + 1)

    _logger.info(
        "Region %d bounding box (1-based): i=%d-%d, j=%d-%d, k=%d-%d",
        region_id, imin, imax, jmin, jmax, kmin, kmax,
    )

    cropped_grid = grid.copy()
    cropped_grid.crop((imin, imax), (jmin, jmax), (kmin, kmax), props="all")
    _logger.info("Cropped grid dimensions: %s", cropped_grid.dimensions)

    return cropped_grid, (imin - 1, jmin - 1, kmin - 1)


def _find_boundary_faces(
    region_prop: xtgeo.GridProperty,
    target_region: int,
) -> list[tuple[tuple[int, int, int], tuple[int, int, int], str]]:
    """Find cell faces on the boundary between *target_region* and other active regions.

    Returns a list of ``(outside_ijk, inside_ijk, face_dir)`` where indices
    are 0-based and *face_dir* is one of ``'i+', 'i-', 'j+', 'j-', 'k+', 'k-'``.
    """
    filled = np.ma.filled(region_prop.values, fill_value=-1).astype(int)
    ni, nj, nk = filled.shape

    in_target = filled == target_region
    outside_active = (filled != target_region) & (filled != -1)

    faces: list[tuple[tuple[int, int, int], tuple[int, int, int], str]] = []

    # i+
    mask = in_target[: ni - 1, :, :] & outside_active[1:ni, :, :]
    for i, j, k in np.argwhere(mask):
        faces.append(((int(i + 1), int(j), int(k)), (int(i), int(j), int(k)), "i+"))

    # i-
    mask = in_target[1:ni, :, :] & outside_active[: ni - 1, :, :]
    for idx, j, k in np.argwhere(mask):
        faces.append(
            ((int(idx), int(j), int(k)), (int(idx + 1), int(j), int(k)), "i-")
        )

    # j+
    mask = in_target[:, : nj - 1, :] & outside_active[:, 1:nj, :]
    for i, j, k in np.argwhere(mask):
        faces.append(((int(i), int(j + 1), int(k)), (int(i), int(j), int(k)), "j+"))

    # j-
    mask = in_target[:, 1:nj, :] & outside_active[:, : nj - 1, :]
    for i, jdx, k in np.argwhere(mask):
        faces.append(
            ((int(i), int(jdx), int(k)), (int(i), int(jdx + 1), int(k)), "j-")
        )

    # k+
    mask = in_target[:, :, : nk - 1] & outside_active[:, :, 1:nk]
    for i, j, k in np.argwhere(mask):
        faces.append(((int(i), int(j), int(k + 1)), (int(i), int(j), int(k)), "k+"))

    # k-
    mask = in_target[:, :, 1:nk] & outside_active[:, :, : nk - 1]
    for i, j, kdx in np.argwhere(mask):
        faces.append(
            ((int(i), int(j), int(kdx)), (int(i), int(j), int(kdx + 1)), "k-")
        )

    _logger.info("Found %d boundary faces for region %d", len(faces), target_region)
    return faces


def _set_actnum_by_region(
    grid: xtgeo.Grid,
    region_prop: xtgeo.GridProperty,
    target_region: int,
    *,
    invert: bool = False,
) -> None:
    """Deactivate cells based on region membership."""
    actnum = grid.get_actnum()
    region_values = region_prop.values

    if invert:
        mask = region_values != target_region
    else:
        mask = region_values == target_region

    _logger.info(
        "Deactivating %d cells (region %s %d)",
        np.sum(mask), "!=" if invert else "==", target_region,
    )
    actnum.values[mask] = 0
    grid.set_actnum(actnum)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def create_nested_hybrid_grid(
    grid: xtgeo.Grid,
    region: xtgeo.GridProperty,
    target_region_id: int,
    refinement: tuple[int, int, int],
) -> xtgeo.Grid:
    """Create a nested hybrid grid by refining one region and merging it back.

    The cells belonging to *target_region_id* are replaced by a refined
    (subdivided) version of the same region.  A ``NEST_ID`` discrete property
    is attached to the merged grid, encoding the nested hybrid structure:

    - ``NEST_ID == 1``: coarse (mother) grid cells.
    - ``NEST_ID == 2``: refined grid cells.

    After the merged grid is returned, properties (e.g. permeabilities) can
    be populated on it — for instance by sampling from a finer input grid.
    To then compute transmissibilities including Non-Neighbour Connections
    (NNCs) across the coarse/refined boundary, call
    :meth:`xtgeo.Grid.get_transmissibilities` with the ``nested_id_property``
    argument set to the attached ``NEST_ID`` property.

    Args:
        grid: The original coarse grid.
        region: A :class:`xtgeo.GridProperty` whose values identify the
            regions (e.g. an integer region parameter).
        target_region_id: The region value to refine.
        refinement: ``(ncol, nrow, nlay)`` refinement factors.

    Returns:
        A new :class:`xtgeo.Grid` with the refined region stitched back
        into the coarse grid and a ``NEST_ID`` property attached.
    """
    if any(r < 1 for r in refinement):
        raise ValueError(f"Refinement factors must be >= 1, got {refinement}")

    # Make working copies so the caller's objects are not mutated.
    grid = grid.copy()
    region = region.copy()

    # Attach the region property to the grid.
    grid.append_prop(region)

    # 1. Crop to the bounding box of the target region.
    cropped, _crop_origin = _crop_for_region(grid, region, target_region_id)

    # 2. Refine the cropped grid.
    refined = cropped.copy()
    rcol, rrow, rlay = refinement
    refined.refine(refine_col=rcol, refine_row=rrow, refine_layer=rlay)
    _logger.info("Refined cropped grid dimensions: %s", refined.dimensions)

    # 3. Deactivate the target region in the coarse grid (will be replaced).
    coarse_region = grid.get_prop_by_name(region.name)
    _set_actnum_by_region(grid, coarse_region, target_region_id, invert=False)

    # 4. In the refined grid keep only target-region cells active.
    refined_region = refined.get_prop_by_name(region.name)
    _set_actnum_by_region(refined, refined_region, target_region_id, invert=True)

    # 5. Create NEST_ID properties before merging (1=mother, 2=refined).
    nest_id_coarse = xtgeo.GridProperty(
        grid,
        name="NEST_ID",
        discrete=True,
        values=np.where(grid.get_actnum().values == 1, 1, 0).astype(np.int32),
        codes={0: "inactive", 1: "mother", 2: "refined"},
    )
    grid.append_prop(nest_id_coarse)

    nest_id_refined = xtgeo.GridProperty(
        refined,
        name="NEST_ID",
        discrete=True,
        values=np.where(refined.get_actnum().values == 1, 2, 0).astype(np.int32),
        codes={0: "inactive", 1: "mother", 2: "refined"},
    )
    refined.append_prop(nest_id_refined)

    # 6. Merge the two grids.
    merged = xtgeo.grid_merge(grid, refined)
    _logger.info("Merged grid dimensions: %s", merged.dimensions)

    return merged
