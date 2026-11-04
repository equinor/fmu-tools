"""Helpers for mapping between cells and flat indices in the nested hybrid grid."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Self, TypeVar

import numpy as np

IndexLike = TypeVar("IndexLike", int, np.ndarray)


def ijk_to_flat_index(
    i: IndexLike, j: IndexLike, k: IndexLike, jdim: int, kdim: int
) -> IndexLike:
    """Convert 0-based (i, j, k) indices to positions in a 1D flattened array.
    This follows NumPy C-order (row-major) indexing.
    """
    return i * jdim * kdim + j * kdim + k


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

    def expand(self, parent_indices: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Return nested cells for each parent and their parent group.

        The parent group gives the position in ``parent_indices`` corresponding
        to each returned nested cell.
        """
        counts = self.counts[parent_indices]
        starts = self.group_start[parent_indices]

        parent_group = np.repeat(np.arange(parent_indices.size), counts)

        first_of_group = np.cumsum(counts) - counts
        offsets = np.arange(parent_group.size) - first_of_group[parent_group]

        positions = starts[parent_group] + offsets
        return self.cell_indices[positions], parent_group

    def get_indices(self, parent_idx: int | np.intp) -> np.ndarray:
        start = self.group_start[parent_idx]

        if start == -1:
            raise ValueError(f"No cells found for parent index {parent_idx}.")

        return self.cell_indices[start : self.group_stop[parent_idx]]
