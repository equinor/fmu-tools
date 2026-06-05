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
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd
import xtgeo

if TYPE_CHECKING:
    import os
    from collections.abc import Iterable

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
        region_id,
        imin,
        imax,
        jmin,
        jmax,
        kmin,
        kmax,
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

    _logger.info("Found %d boundary faces for region %d", len(faces), target_region)
    return faces


def _compute_nnc_table(
    region_prop: xtgeo.GridProperty,
    target_region_id: int,
    crop_origin: tuple[int, int, int],
    refinement: tuple[int, int, int],
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
        region_prop: Region property on the original (unmodified) grid.
        target_region_id: Region value that was refined.
        crop_origin: 0-based ``(i0, j0, k0)`` origin of the crop box.
        refinement: ``(rcol, rrow, rlay)`` refinement factors.
        coarse_ncol: Number of columns in the coarse grid (grid1 in the merge).
        lmap1: Numpy array with layer_mapping (input k -> output k) for grid1
        lmap2: Numpy array with layer_mapping (input k -> output k) for grid2


    Returns:
        A DataFrame with columns ``I1, J1, K1, I2, J2, K2, DIRECTION``.
    """
    faces = _find_boundary_faces(region_prop, target_region_id)

    rcol, rrow, rlay = refinement
    i0, j0, k0 = crop_origin

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

    mask = region_values != target_region if invert else region_values == target_region

    _logger.info(
        "Deactivating %d cells (region %s %d)",
        np.sum(mask),
        "!=" if invert else "==",
        target_region,
    )
    actnum.values[mask] = 0
    grid.set_actnum(actnum)


def _generate_layer_mappings(
    coarse_nlay: int,
    refined_nlay: int,
    refinement: tuple[int, int, int],
    crop_origin: tuple[int, int, int],
) -> tuple[np.ndarray, np.ndarray]:
    """Generate mappings from old to new layer number.
    Args:
        coarse_nlay: Number of layers in the coarse grid (grid1 in the merge).
        refined_nlay: Number of layers in the refined grid (grid2 in the merge).
        crop_origin: 0-based ``(i0, j0, k0)`` origin of the crop box.
        refinement: ``(rcol, rrow, rlay)`` refinement factors.

    Returns:
        lmap1: Numpy array with layer_mapping (input k -> output k) for grid1
        lmap2: Numpy array with layer_mapping (input k -> output k) for grid2
    """

    _, _, rlay = refinement
    _, _, k0 = crop_origin

    lmap1 = np.arange(coarse_nlay, dtype=np.int32)
    lmap1 = lmap1 + np.where(
        lmap1 < k0,
        0,
        (rlay - 1) * np.minimum(int(refined_nlay / rlay), lmap1 - k0),
    )
    lmap2 = np.arange(refined_nlay, dtype=np.int32) + k0

    return (lmap1, lmap2)


def _modify_upscaling_mapping(
    up: tuple[xtgeo.GridProperty, xtgeo.GridProperty, xtgeo.GridProperty],
    region: xtgeo.GridProperty,
    target_region_id: int,
    refinement: tuple[int, int, int],
    offset: tuple[int, int, int],
    grid2_dims: tuple[int, int, int],
    lmap: np.ndarray,
) -> tuple[xtgeo.GridProperty, xtgeo.GridProperty, xtgeo.GridProperty] | None:
    """Update a cell mapping for upscaling
    Args:
        up: (
            I_property - xtgeo.GridProperty on geogrid mapping cells to input grid I
            J_property - xtgeo.GridProperty on geogrid mapping cells to input grid J
            K_property - xtgeo.GridProperty on geogrid mapping cells to input grid K
            )
        region: input region (before merging)
        target_region_id: region to be refined
        refinement: refinement (i,j,k) to be applied per cell in target region
        offset: start cell of the refinement region
        grid2_dims: (columns, rows, layers) in refined grid
        lmap: layer mapping for grid1 (not refined)

    Returns:
        (
        I_property - xtgeo.GridProperty on geogrid mapping cells to updated grid I
        J_property - xtgeo.GridProperty on geogrid mapping cells to updated grid J
        K_property - xtgeo.GridProperty on geogrid mapping cells to updated grid K
        )

    """
    imap, jmap, kmap = up
    oi, oj, ok = offset
    ri, rj, rk = refinement
    di, dj, dk = grid2_dims

    ivm = region.ncol
    jvm = region.nrow
    kvm = region.nlay

    iv = imap.values.copy().reshape(-1) - 1
    jv = jmap.values.copy().reshape(-1) - 1
    kv = kmap.values.copy().reshape(-1) - 1

    if (
        iv.min() < -1
        or jv.min() < -1
        or kv.min() < -1
        or iv.max() >= region.ncol
        or jv.max() >= region.nrow
        or kv.max() >= region.nlay
    ):
        raise ValueError("Invalid input upscaling relationships")

    exclude_mask = (iv == -1) | (jv == -1) | (kv == -1)

    # map region from input grid to geogrid
    # excluding any enteries for cells in geogrid that are excluded
    cn = np.ma.masked_where(exclude_mask, iv * jvm * kvm + jv * kvm + kv)
    # mask any inactive cells in the input grid that are mapped by geogrid
    iv[~cn.mask][region.values.mask.reshape(-1)[cn[~cn.mask].astype(np.int32)]] = -1
    jv[~cn.mask][region.values.mask.reshape(-1)[cn[~cn.mask].astype(np.int32)]] = -1
    kv[~cn.mask][region.values.mask.reshape(-1)[cn[~cn.mask].astype(np.int32)]] = -1
    exclude_mask = (iv == -1) | (jv == -1) | (kv == -1)
    cn = np.ma.masked_where(exclude_mask, cn)

    region2 = np.ma.masked_array(np.zeros(len(cn)), mask=cn.mask)
    region2[~cn.mask] = region.values.reshape(-1)[cn[~cn.mask].astype(np.int32)]

    # for cells that aren't refined only layer numbering updates
    kv[(~cn.mask) & (region2 != target_region_id)] = lmap[
        kv[(~cn.mask) & (region2 != target_region_id)].astype(np.int32)
    ]

    # for cells that are refined find the levels of refinement
    cijk = np.argwhere(region.values == target_region_id)
    cijk2 = np.argwhere(region2.reshape(imap.values.shape) == target_region_id)
    cnr = cijk[:, 0] * jvm * kvm + cijk[:, 1] * kvm + cijk[:, 2]

    # find number of cells in refined region on geogrid and normal grid
    ccnt = [len(np.unique(cijk[:, x])) for x in range(3)]
    ccnt2 = [len(np.unique(cijk2[:, x])) for x in range(3)]

    if any(ccnt2[x] % ccnt[x] > 0 for x in range(3)):
        warnings.warn(
            "Unable to find a valid correspondence upscaling between geogrid and input"
            " grid"
        )
        return None

    uri = int(ccnt2[0] / ccnt[0])
    urj = int(ccnt2[1] / ccnt[1])
    urk = int(ccnt2[2] / ccnt[2])

    # original index map of refined cells
    il2 = (
        np.repeat(np.arange(int(di / ri), dtype=np.int32) + oi, ri * dj * dk)
    ).reshape((di, dj, dk))
    jl2 = np.swapaxes(
        (np.repeat(np.arange(int(dj / rj), dtype=np.int32) + oj, rj * di * dk)).reshape(
            (dj, di, dk)
        ),
        0,
        1,
    )
    kl2 = np.swapaxes(
        (np.repeat(np.arange(int(dk / rk), dtype=np.int32) + ok, rk * di * dj)).reshape(
            (dk, dj, di)
        ),
        0,
        2,
    )
    # map the updated refined grid cells to geogrid
    cmap2 = np.arange(di, dtype=np.float32) + ivm + 1
    cmap2 = np.repeat(cmap2, dj * dk).reshape((di, dj, dk))
    rmap2 = np.arange(dj, dtype=np.float32)
    rmap2 = np.swapaxes(np.repeat(rmap2, di * dk).reshape((dj, di, dk)), 0, 1)
    lmap2 = np.arange(dk, dtype=np.float32) + ok
    lmap2 = np.tile(lmap2, di * dj).reshape((di, dj, dk))

    if uri > ri:
        il2 = np.repeat(il2, int(uri / ri), axis=0)
        jl2 = np.repeat(jl2, int(uri / ri), axis=0)
        kl2 = np.repeat(kl2, int(uri / ri), axis=0)
        cmap2 = np.repeat(cmap2, int(uri / ri), axis=0)
        rmap2 = np.repeat(rmap2, int(uri / ri), axis=0)
        lmap2 = np.repeat(lmap2, int(uri / ri), axis=0)
    if urj > rj:
        il2 = np.repeat(il2, int(urj / rj), axis=1)
        jl2 = np.repeat(jl2, int(urj / rj), axis=1)
        kl2 = np.repeat(kl2, int(urj / rj), axis=1)
        cmap2 = np.repeat(cmap2, int(urj / rj), axis=1)
        rmap2 = np.repeat(rmap2, int(urj / rj), axis=1)
        lmap2 = np.repeat(lmap2, int(urj / rj), axis=1)
    if urk > rk:
        il2 = np.repeat(il2, int(urk / rk), axis=2)
        jl2 = np.repeat(jl2, int(urk / rk), axis=2)
        kl2 = np.repeat(kl2, int(urk / rk), axis=2)
        cmap2 = np.repeat(cmap2, int(urk / rk), axis=2)
        rmap2 = np.repeat(rmap2, int(urk / rk), axis=2)
        lmap2 = np.repeat(lmap2, int(urk / rk), axis=2)

    cl2 = il2.reshape(-1) * jvm * kvm + jl2.reshape(-1) * kvm + kl2.reshape(-1)

    # ensure only correct cells are updated
    geomask = region2 == target_region_id
    refmask = np.isin(cl2, cnr)
    iv[geomask] = cmap2.reshape(-1)[refmask]
    jv[geomask] = rmap2.reshape(-1)[refmask]
    kv[geomask] = lmap2.reshape(-1)[refmask]

    imap.values = iv.reshape(imap.values.shape).astype(np.float32) + 1.0
    jmap.values = jv.reshape(imap.values.shape).astype(np.float32) + 1.0
    kmap.values = kv.reshape(imap.values.shape).astype(np.float32) + 1.0

    return (imap, jmap, kmap)


def _set_zonation(subgrid: dict, lmap: np.ndarray, nlay: int) -> dict:
    """Create an updated subgrid dictionary for the merged grid.
    Args:
        subgrid: subgrid dictionary from input grid
        lmap: layer mapping for grid1 - unrefined input grid
        nlay: total number of layers in merged grid
    """

    updated_subgrid = {}

    # sorted list of zones to add
    zl = sorted(subgrid, key=lambda x: subgrid[x][0])

    for zi in range(len(zl)):
        zn = zl[zi]
        zmin = lmap[subgrid[zn][0] - 1] + 1
        zmax = nlay + 1 if zi == len(zl) - 1 else lmap[subgrid[zl[zi + 1]][0] - 1] + 1
        updated_subgrid[zn] = range(zmin, zmax)

    return updated_subgrid


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def create_nested_hybrid_grid(
    grid: xtgeo.Grid,
    region: xtgeo.GridProperty,
    target_region_id: int,
    refinement: tuple[int, int, int],
    upscaling: tuple[xtgeo.GridProperty, xtgeo.GridProperty, xtgeo.GridProperty]
    | None = None,
) -> tuple[
    xtgeo.Grid,
    pd.DataFrame,
    tuple[xtgeo.GridProperty, xtgeo.GridProperty, xtgeo.GridProperty] | None,
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
        upscaling: Optional tuple of `xtgeo.GridProperty` for (I,J,K)
            Geogrid properties. These map from geogrid cell to input grid
            The input values must be a valid mapping for upscaling from
            the geogrid to the input grid give. A value of 0 can be used
            to exclude the geogrid cell from upscaling

    Returns:
        A tuple ``(merged_grid, nnc_table)`` where *merged_grid*
        is a new :class:`xtgeo.Grid` with the refined region stitched back into
        the coarse grid and *nnc_table* is a :class:`pandas.DataFrame` mapping
        mother cells to their connected refined cells. Upscaling tuple is a tuple
        with 3 :class:`xtgeo.GridProperty` (I, J, K) with the updated mapping
        from geogrid to merged grid for upscaling.
    """
    if any(r < 1 for r in refinement):
        raise ValueError(f"Refinement factors must be >= 1, got {refinement}")

    if region.dimensions != grid.dimensions:
        raise ValueError(
            f"Region property dimensions {region.dimensions} do not match "
            f"grid dimensions {grid.dimensions}"
        )

    # Make working copies so the caller's objects are not mutated.
    grid = grid.copy()
    region = region.copy()

    # Save input zonation
    subgrid = grid.subgrids

    # Attach the region property to the grid.
    grid.append_prop(region)

    # 1. Crop to the bounding box of the target region.
    cropped, crop_origin = _crop_for_region(grid, region, target_region_id)

    # 2. Refine the cropped grid.
    refined = cropped.copy()
    rcol, rrow, rlay = refinement
    _, _, olay = crop_origin
    refined.refine(refine_col=rcol, refine_row=rrow, refine_layer=rlay)
    _logger.info("Refined cropped grid dimensions: %s", refined.dimensions)

    # 3. Generate layer mappings
    lmap1, lmap2 = _generate_layer_mappings(
        coarse_nlay=grid.nlay,
        refined_nlay=refined.nlay,
        crop_origin=crop_origin,
        refinement=refinement,
    )

    # 4. Compute the NNC mapping table *before* deactivation mutates anything.
    #    This uses the original region property to find boundary faces and
    #    maps them through the crop → refine → merge index chain.
    nnc_table = _compute_nnc_table(
        region_prop=region,
        target_region_id=target_region_id,
        crop_origin=crop_origin,
        refinement=refinement,
        coarse_ncol=grid.ncol,
        lmap1=lmap1,
        lmap2=lmap2,
    )

    # 5. Deactivate the target region in the coarse grid (will be replaced).
    coarse_region = grid.get_prop_by_name(region.name)
    _set_actnum_by_region(grid, coarse_region, target_region_id, invert=False)

    # 6. In the refined grid keep only target-region cells active.
    refined_region = refined.get_prop_by_name(region.name)
    _set_actnum_by_region(refined, refined_region, target_region_id, invert=True)

    # 7. Merge the two grids.
    merged = xtgeo.grid_merge(grid, refined, lmap1, lmap2)
    _logger.info("Merged grid dimensions: %s", merged.dimensions)
    if subgrid is not None:
        merged.subgrids = _set_zonation(subgrid=subgrid, lmap=lmap1, nlay=merged.nlay)

    # 8. Update upscaling map if needed
    if upscaling is not None:
        updated_upscaling = _modify_upscaling_mapping(
            upscaling,
            region,
            target_region_id,
            refinement,
            crop_origin,
            (refined.dimensions.ncol, refined.dimensions.nrow, refined.dimensions.nlay),
            lmap1,
        )
    else:
        updated_upscaling = None

    return merged, nnc_table, updated_upscaling


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
