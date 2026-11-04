"""Tests for transferring RMS grid faults to the nested hybrid grid."""

from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pytest
import xtgeo

from fmu.tools.nestedhybridgrid import NestedHybridGrid
from fmu.tools.nestedhybridgrid._faults import (
    GridFault,
    map_fault_to_nested_grid,
    read_grid_faults,
)

WEST, EAST, SOUTH, NORTH = 0, 1, 2, 3
PARENT_DIMS = (4, 2, 1)
REFINEMENT = (2, 2, 1)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_grid_and_region() -> tuple[xtgeo.Grid, xtgeo.GridProperty]:
    grid = xtgeo.create_box_grid(PARENT_DIMS, increment=(50.0, 50.0, 10.0))
    values = np.zeros(PARENT_DIMS, dtype=np.int32)
    values[2:, :, :] = 1
    region = xtgeo.GridProperty(grid, name="REGION", discrete=True, values=values)
    return grid, region


def _make_nested_grid() -> NestedHybridGrid:
    grid, region = _make_grid_and_region()
    return NestedHybridGrid(coarse_grid=grid, region=region, refinement=REFINEMENT)


def _flat(parent_ijk) -> int:
    """Flat index (and RMS cell number) of a parent cell; all cells are active."""
    return int(np.ravel_multi_index(parent_ijk, PARENT_DIMS))


def _rms_values(*rows) -> np.ma.MaskedArray:
    """RMS fault table from (fw_cell, fw_face, hw_cell, hw_face) rows."""
    return np.ma.array(
        [(_flat(fw), _flat(hw), fw_face, hw_face) for fw, fw_face, hw, hw_face in rows]
    )


def _parent_fault(*rows) -> GridFault:
    """Fault in the parent grid from (fw_cell, fw_face, hw_cell, hw_face) rows."""
    fw, fw_face, hw, hw_face = zip(*rows)
    return GridFault(
        name="Fault",
        fw_indices=np.ma.array([_flat(cell) for cell in fw]),
        hw_indices=np.ma.array([_flat(cell) for cell in hw]),
        fw_face=np.ma.array(fw_face),
        hw_face=np.ma.array(hw_face),
    )


def _mapped(values: np.ma.MaskedArray, cell_number_to_ijk) -> set:
    """Fault rows as a set of (side, nested cell ijk, face)."""
    mapped = set()
    for fw_cell, hw_cell, fw_face, hw_face in values:
        for side, cell, face in (("fw", fw_cell, fw_face), ("hw", hw_cell, hw_face)):
            if cell is not np.ma.masked:
                ijk = tuple(int(i) for i in cell_number_to_ijk(int(cell)))
                mapped.add((side, ijk, int(face)))
    return mapped


# Parent cells (2, 0, 0) and (3, 0, 0), both refined, meet along the I+ / I- faces
PILLAR_ROWS = [((2, 0, 0), EAST, (3, 0, 0), WEST)]
PILLAR_MAPPED = {
    ("fw", (6, 0, 0), EAST),  # highest nested i of parent (2, 0, 0)
    ("fw", (6, 1, 0), EAST),
    ("hw", (7, 0, 0), WEST),  # lowest nested i of parent (3, 0, 0)
    ("hw", (7, 1, 0), WEST),
}


# ---------------------------------------------------------------------------
# Mapping a parent fault to the nested grid
# ---------------------------------------------------------------------------


class TestMapFaultToNestedGrid:
    @staticmethod
    def _map(fault: GridFault) -> set:
        nhg = _make_nested_grid()
        nested_dims = nhg.grid.dimensions
        n_cells = int(np.prod(nested_dims))

        identity = np.ma.masked_all(n_cells, dtype=np.int64)
        identity[:] = np.arange(n_cells)

        values = map_fault_to_nested_grid(
            parent_fault=fault,
            nested_cells_by_parent=nhg.nested_cells_by_parent,
            flat_to_rms_cell_number=identity,
            nested_dimensions=nested_dims,
        )
        return _mapped(values, lambda n: np.unravel_index(n, nested_dims))

    def test_pillar_fault_between_refined_cells(self):
        """Each refined side keeps the nested cells on its own faulted face."""
        assert self._map(_parent_fault(*PILLAR_ROWS)) == PILLAR_MAPPED

    def test_pillar_fault_along_j(self):
        """The J+ face of (3, 0, 0) is its highest nested j, J- of (3, 1, 0) lowest."""
        fault = _parent_fault(((3, 0, 0), SOUTH, (3, 1, 0), NORTH))

        assert self._map(fault) == {
            ("fw", (7, 1, 0), SOUTH),
            ("fw", (8, 1, 0), SOUTH),
            ("hw", (7, 2, 0), NORTH),
            ("hw", (8, 2, 0), NORTH),
        }

    def test_unrefined_cell_maps_to_its_single_nested_cell(self):
        fault = _parent_fault(((1, 0, 0), EAST, (2, 0, 0), WEST))

        assert self._map(fault) == {
            ("fw", (1, 0, 0), EAST),
            ("hw", (5, 0, 0), WEST),
            ("hw", (5, 1, 0), WEST),
        }

    def test_stairstepped_fault(self):
        """A step is a J face between two I faces; each row maps independently."""
        fault = _parent_fault(
            ((2, 0, 0), EAST, (3, 0, 0), WEST),  # I plane 2|3 at j = 0
            ((2, 0, 0), SOUTH, (2, 1, 0), NORTH),  # step towards j = 1
            ((1, 1, 0), EAST, (2, 1, 0), WEST),  # I plane 1|2 at j = 1
        )

        assert self._map(fault) == {
            ("fw", (6, 0, 0), EAST),
            ("fw", (6, 1, 0), EAST),
            ("hw", (7, 0, 0), WEST),
            ("hw", (7, 1, 0), WEST),
            ("fw", (5, 1, 0), SOUTH),
            ("fw", (6, 1, 0), SOUTH),
            ("hw", (5, 2, 0), NORTH),
            ("hw", (6, 2, 0), NORTH),
            ("fw", (1, 1, 0), EAST),
            ("hw", (5, 2, 0), WEST),
            ("hw", (5, 3, 0), WEST),
        }

    def test_masked_side_is_skipped(self):
        fault = _parent_fault(*PILLAR_ROWS)
        fault.hw_indices[0] = np.ma.masked

        assert self._map(fault) == {
            ("fw", (6, 0, 0), EAST),
            ("fw", (6, 1, 0), EAST),
        }


# ---------------------------------------------------------------------------
# Fake RMS project
# ---------------------------------------------------------------------------


class _FakeIndexer:
    """RMS grid indexer; the cell number is the position among active cells."""

    def __init__(self, active: np.ndarray, handedness: str = "right"):
        self.dimensions = active.shape
        self.ijk_handedness = handedness
        self.ijk = np.argwhere(active)

    def get_indices(self, cell_numbers):
        return self.ijk[np.asarray(cell_numbers, dtype=np.int64)]

    def get_cell_numbers_in_range(self, start, stop):
        return np.arange(len(self.ijk), dtype=np.uint64)


class _FakeFault:
    def __init__(self, name, values=None):
        self.name = name
        self.values = values

    def get_values(self):
        return self.values

    def set_values(self, values):
        self.values = values


class _FakeFaults(list):
    def create(self, name):
        fault = _FakeFault(name)
        self.append(fault)
        return fault


def _fake_project(indexer, faults=()):
    """Return a fake RMS project with a grid "Grid", and its fault list."""
    grid_faults = _FakeFaults(faults)
    rms_grid = SimpleNamespace(grid_indexer=indexer, grid_faults=grid_faults)
    grid_model = SimpleNamespace(get_grid=lambda: rms_grid)
    return SimpleNamespace(grid_models={"Grid": grid_model}), grid_faults


def _parent_project(**faults):
    """Fake RMS project with the parent grid and faults given as name=values."""
    indexer = _FakeIndexer(np.ones(PARENT_DIMS, dtype=bool))
    return _fake_project(indexer, [_FakeFault(n, v) for n, v in faults.items()])[0]


# ---------------------------------------------------------------------------
# Reading faults from RMS
# ---------------------------------------------------------------------------


class TestReadGridFaults:
    def test_reads_parent_cells_and_faces(self):
        project = _parent_project(Pillar=_rms_values(*PILLAR_ROWS))

        (fault,) = read_grid_faults(project, "Grid")

        assert fault.name == "Pillar"
        assert fault.fw_indices.tolist() == [_flat((2, 0, 0))]
        assert fault.hw_indices.tolist() == [_flat((3, 0, 0))]
        assert fault.fw_face.tolist() == [EAST]
        assert fault.hw_face.tolist() == [WEST]

    def test_masked_cell_stays_masked(self):
        values = _rms_values(*PILLAR_ROWS)
        values[0, 1] = np.ma.masked  # no HW cell

        (fault,) = read_grid_faults(_parent_project(Pillar=values), "Grid")

        assert not np.ma.getmaskarray(fault.fw_indices)[0]
        assert np.ma.getmaskarray(fault.hw_indices)[0]

    def test_left_handed_grid_is_not_supported(self):
        indexer = _FakeIndexer(np.ones(PARENT_DIMS, dtype=bool), handedness="left")
        faults = [_FakeFault("Pillar", _rms_values(*PILLAR_ROWS))]
        project, _ = _fake_project(indexer, faults)

        with pytest.warns(UserWarning, match="not right-handed"):
            assert read_grid_faults(project, "Grid") is None


# ---------------------------------------------------------------------------
# from_rms -> to_rms
# ---------------------------------------------------------------------------


def _from_rms(project) -> NestedHybridGrid:
    grid, region = _make_grid_and_region()
    with (
        patch("xtgeo.grid_from_roxar", return_value=grid),
        patch("xtgeo.gridproperty_from_roxar", return_value=region),
    ):
        return NestedHybridGrid.from_rms(
            project=project,
            grid_name="Grid",
            region_name="REGION",
            refinement=REFINEMENT,
        )


def _to_rms(nhg: NestedHybridGrid):
    """Write the nested grid to a fake project.

    Returns the output grid indexer and the faults written to the output grid.
    """
    indexer = _FakeIndexer(nhg.grid.get_actnum().values.astype(bool))
    project, written_faults = _fake_project(indexer)

    with (
        patch.object(xtgeo.Grid, "to_roxar"),
        patch.object(xtgeo.GridProperty, "to_roxar"),
    ):
        nhg.to_rms(project, "Grid")

    return indexer, written_faults


class TestFaultsFromRmsToRms:
    def test_fault_is_written_with_mapped_cells(self):
        nhg = _from_rms(_parent_project(Pillar=_rms_values(*PILLAR_ROWS)))

        indexer, written = _to_rms(nhg)

        (fault,) = written
        assert fault.name == "Pillar"
        assert _mapped(fault.values, lambda n: indexer.ijk[n]) == PILLAR_MAPPED

    def test_faults_are_read_by_from_rms(self):
        """Faults are a snapshot from from_rms, later changes are not picked up."""
        project, faults = _fake_project(_FakeIndexer(np.ones(PARENT_DIMS, dtype=bool)))
        faults.append(_FakeFault("Early", _rms_values(*PILLAR_ROWS)))
        nhg = _from_rms(project)

        faults.append(_FakeFault("Late", _rms_values(*PILLAR_ROWS)))  # after from_rms
        _, written = _to_rms(nhg)

        assert [fault.name for fault in written] == ["Early"]

    def test_left_handed_grid_writes_no_faults_and_warns(self):
        indexer = _FakeIndexer(np.ones(PARENT_DIMS, dtype=bool), handedness="left")
        faults = [_FakeFault("Pillar", _rms_values(*PILLAR_ROWS))]

        with pytest.warns(UserWarning, match="not right-handed"):
            nhg = _from_rms(_fake_project(indexer, faults)[0])
        _, written = _to_rms(nhg)

        assert len(written) == 0

    def test_grid_not_from_rms_has_no_faults_to_write(self):
        _, written = _to_rms(_make_nested_grid())

        assert len(written) == 0
