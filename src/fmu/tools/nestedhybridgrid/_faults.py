"""Transfer of RMS grid faults from the parent grid to the nested hybrid grid.

Faults are read from the parent RMS grid as pairs of footwall (FW) and hanging wall
(HW) cells with a face on each side. Each parent cell is replaced by the nested
cells it contains, and only the nested cells on the faulted face keep the fault.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import numpy as np

from ._cell_indexing import CellsByParent, ijk_to_flat_index

if TYPE_CHECKING:
    from xtgeo.common.types import Dimensions

# RMS fault face code -> (axis, sign). This holds for right-handed grids only.
# RMS FaceDirection codes are: west=0, east=1, south=2, north=3, top=4, bottom=5.
_RMS_FAULT_FACES = np.array([(0, -1), (0, 1), (1, 1), (1, -1), (2, -1), (2, 1)])


@dataclass(frozen=True)
class GridFault:
    name: str
    fw_indices: np.ma.MaskedArray
    hw_indices: np.ma.MaskedArray
    fw_face: np.ma.MaskedArray
    hw_face: np.ma.MaskedArray


def _flat_to_rms_cell_number_mapping(grid_indexer: Any) -> np.ma.MaskedArray:
    """Map C-order flat grid indices to RMS cell numbers."""
    ncol, nrow, nlay = grid_indexer.dimensions

    cell_numbers = grid_indexer.get_cell_numbers_in_range((0, 0, 0), (ncol, nrow, nlay))
    i, j, k = grid_indexer.get_indices(cell_numbers).T

    flat_indices = ijk_to_flat_index(i=i, j=j, k=k, jdim=nrow, kdim=nlay)

    flat_to_rms_cell_number = np.ma.masked_all(ncol * nrow * nlay, dtype=np.int64)
    flat_to_rms_cell_number[flat_indices] = cell_numbers
    return flat_to_rms_cell_number


def _rms_cell_numbers_to_flat_indices(
    cell_numbers: np.ma.MaskedArray, grid_indexer: Any
) -> np.ma.MaskedArray:
    """Convert RMS active-cell numbers to parent-grid flat indices."""

    mask = np.ma.getmaskarray(cell_numbers)

    active_cell_numbers = cell_numbers[~mask].astype(np.uint64)
    i, j, k = grid_indexer.get_indices(active_cell_numbers).T  # 0-based
    _, nrow, nlay = grid_indexer.dimensions

    flat_indices = np.ma.masked_all(cell_numbers.shape, dtype=np.int64)
    flat_indices[~mask] = ijk_to_flat_index(i=i, j=j, k=k, jdim=nrow, kdim=nlay)
    return flat_indices


def _on_parent_face(
    nested_ijk: tuple[np.ndarray, ...],
    parent_group: np.ndarray,
    fault_face: np.ndarray,
) -> np.ndarray:
    """Return a mask of cells lying on the specified face of their parent"""
    axis, sign = fault_face.T

    # Multiply the coordinates for low-index faces so the target face
    # is always found by taking the maximum coordinate.
    coord = np.choose(axis, nested_ijk) * sign

    _, starts, groups = np.unique(parent_group, return_index=True, return_inverse=True)
    group_max = np.maximum.reduceat(coord, starts)

    return coord == group_max[groups]


def read_grid_faults(project: Any, grid_name: str) -> list[GridFault] | None:
    """Read RMS faults and keep FW/HW parent-cell indices as masked IJK arrays.

    Faults are only supported for right-handed grids, see _RMS_FAULT_FACES.
    """
    rms_grid = project.grid_models[grid_name].get_grid()
    indexer = rms_grid.grid_indexer

    if str(indexer.ijk_handedness) != "right":
        warnings.warn(
            f"Grid '{grid_name}' is not right-handed: faults are not supported and "
            "will not be restored in the nested grid.",
            UserWarning,
            stacklevel=2,
        )
        return None

    faults = []
    for rms_fault in rms_grid.grid_faults:
        values = rms_fault.get_values()
        fw_cells, hw_cells, fw_face, hw_face = values.T

        faults.append(
            GridFault(
                name=rms_fault.name,
                fw_indices=_rms_cell_numbers_to_flat_indices(fw_cells, indexer),
                hw_indices=_rms_cell_numbers_to_flat_indices(hw_cells, indexer),
                fw_face=fw_face,
                hw_face=hw_face,
            )
        )

    return faults


def write_grid_faults(
    project: Any,
    grid_name: str,
    parent_faults: list[GridFault],
    nested_dimensions: Dimensions,
    nested_cells_by_parent: CellsByParent,
) -> None:
    """Write nested-grid faults to RMS, mapped through the parent-cell groups."""
    rms_grid = project.grid_models[grid_name].get_grid()
    indexer = rms_grid.grid_indexer

    # RMS fault cell numbers refer to active-cell IDs.
    flat_to_rms_cell_number = _flat_to_rms_cell_number_mapping(indexer)

    for fault in parent_faults:
        values = map_fault_to_nested_grid(
            parent_fault=fault,
            nested_cells_by_parent=nested_cells_by_parent,
            flat_to_rms_cell_number=flat_to_rms_cell_number,
            nested_dimensions=nested_dimensions,
        )

        rms_fault = rms_grid.grid_faults.create(fault.name)
        rms_fault.set_values(values)


def _map_fault_side(
    parent_indices: np.ma.MaskedArray,
    faces: np.ma.MaskedArray,
    *,
    cell_column: int,
    face_column: int,
    nested_cells_by_parent: CellsByParent,
    flat_to_rms_cell_number: np.ma.MaskedArray,
    nested_dimensions: Dimensions,
) -> np.ma.MaskedArray:
    """Map one side of a parent-grid fault onto the nested grid.

    Each parent cell expands to the nested cells lying on its faulted face. A
    non-refined parent cell has a single nested cell, which is on every face.
    Parents without nested cells contribute no rows.
    """
    valid = ~np.ma.getmaskarray(parent_indices)

    nested_cells, parent_group = nested_cells_by_parent.expand(parent_indices[valid])
    nested_faces = faces[valid][parent_group]

    nested_ijk = np.unravel_index(nested_cells, nested_dimensions)
    on_face = _on_parent_face(nested_ijk, parent_group, _RMS_FAULT_FACES[nested_faces])

    rms_cells = flat_to_rms_cell_number[nested_cells[on_face]]

    rows = np.ma.masked_all((rms_cells.size, 4), dtype=np.uint64)
    rows[:, cell_column] = rms_cells
    rows[:, face_column] = nested_faces[on_face]
    return rows


def map_fault_to_nested_grid(
    parent_fault: GridFault,
    nested_cells_by_parent: CellsByParent,
    flat_to_rms_cell_number: np.ma.MaskedArray,
    nested_dimensions: Dimensions,
) -> np.ma.MaskedArray:
    """Map a parent-grid fault onto nested-grid fault faces."""
    sides = (
        (parent_fault.fw_indices, parent_fault.fw_face, 0, 2),
        (parent_fault.hw_indices, parent_fault.hw_face, 1, 3),
    )
    return np.ma.vstack(
        [
            _map_fault_side(
                parent_indices=parent_indices,
                faces=faces,
                cell_column=cell_column,
                face_column=face_column,
                nested_cells_by_parent=nested_cells_by_parent,
                flat_to_rms_cell_number=flat_to_rms_cell_number,
                nested_dimensions=nested_dimensions,
            )
            for parent_indices, faces, cell_column, face_column in sides
        ]
    )
