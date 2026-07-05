"""Tests for fmu.tools.nestedhybridgrid.nestedhybrid."""

import numpy as np
import pandas as pd
import pytest
import xtgeo

from fmu.tools.nestedhybridgrid import (
    NestedHybridGrid,
    create_nested_hybrid_grid,
    nnc_to_flowsimulator_input,
    nnc_to_gridproperty,
)
from fmu.tools.nestedhybridgrid.nestedhybrid import BoundingBox, _set_actnum_in_grid

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_box_grid_with_region(
    dimension=(6, 6, 3),
    increment=(50.0, 50.0, 10.0),
    target_region_id=2,
):
    """Create a simple box grid with a region property.

    The grid is split into two regions along the I-axis:
      - region 1: columns 0 .. ncol//2 - 1
      - region 2: columns ncol//2 .. ncol - 1

    Returns (grid, region, target_region_id).
    """
    grid = xtgeo.create_box_grid(dimension, increment=increment)
    ncol, nrow, nlay = dimension

    region_values = np.ones((ncol, nrow, nlay), dtype=np.int32)
    half = ncol // 2
    region_values[half:, :, :] = target_region_id

    region = xtgeo.GridProperty(
        grid, name="REGION", discrete=True, values=region_values
    )
    return grid, region, target_region_id


def _make_constant_property(grid, name, value):
    """Create a continuous GridProperty with a constant value."""
    vals = np.full(grid.dimensions, value, dtype=np.float64)
    return xtgeo.GridProperty(grid, name=name, values=vals)


def test_set_actnum_in_grid_deactivates_cells_where_mask_is_false():
    """Cells with active_mask=False should have actnum set to 0."""
    grid = xtgeo.create_box_grid((3, 3, 2))

    active_mask = np.ones(grid.dimensions, dtype=bool)
    active_mask[1, 1, 0] = False  # deactivate one cell

    _set_actnum_in_grid(grid, active_mask)

    actnum = grid.get_actnum()
    assert actnum.values[1, 1, 0] == 0


def test_set_actnum_in_grid_active_cells_remain_unchanged():
    """Cells with active_mask=True should keep their actnum value."""
    grid = xtgeo.create_box_grid((3, 3, 2))

    active_mask = np.ones(grid.dimensions, dtype=bool)
    active_mask[0, 0, 0] = False

    _set_actnum_in_grid(grid, active_mask)

    actnum = grid.get_actnum()
    # All other cells should still be active
    assert actnum.values[1, 1, 0] == 1
    assert actnum.values[2, 2, 1] == 1


def test_set_actnum_in_grid_all_cells_deactivated():
    """A fully False mask should deactivate every cell."""
    grid = xtgeo.create_box_grid((2, 2, 2))

    active_mask = np.zeros(grid.dimensions, dtype=bool)

    _set_actnum_in_grid(grid, active_mask)

    assert grid.nactive == 0


def test_set_actnum_in_grid_all_cells_activated():
    """A fully True mask should leave all cells active."""
    grid = xtgeo.create_box_grid((2, 2, 2))
    nactive_before = grid.nactive

    active_mask = np.ones(grid.dimensions, dtype=bool)

    _set_actnum_in_grid(grid, active_mask)

    assert grid.nactive == nactive_before


# ---------------------------------------------------------------------------
# Tests for create_nested_hybrid_grid
# ---------------------------------------------------------------------------


class TestBoundingBox:
    """Tests for BoundingBox.from_condition."""

    def test_from_condition_returns_expected_bounds(self):
        """Bounding box should be 1-based and span all True cells."""
        i_ids = np.array([1, 2])
        j_ids = np.array([0, 1])
        k_ids = np.array([2, 3])

        condition = np.ma.masked_all((4, 4, 4))
        condition[i_ids, j_ids, k_ids] = True

        bbox = BoundingBox.from_condition(condition)

        assert bbox.imin == i_ids.min() + 1
        assert bbox.imax == i_ids.max() + 1
        assert bbox.jmin == j_ids.min() + 1
        assert bbox.jmax == j_ids.max() + 1
        assert bbox.kmin == k_ids.min() + 1
        assert bbox.kmax == k_ids.max() + 1

    def test_from_condition_on_region_values(self):
        """Bounding box should match the region property values."""

        target_region_id = 2

        region = xtgeo.GridProperty(ncol=10, nrow=10, nlay=10, discrete=True, values=1)
        region.values[0:5, 0:5, :] = target_region_id

        bbox = BoundingBox.from_condition(region.values == target_region_id)

        assert bbox.imin == 1
        assert bbox.imax == 5
        assert bbox.jmin == 1
        assert bbox.jmax == 5
        assert bbox.kmin == 1
        assert bbox.kmax == 10


class TestCreateNestedHybridGrid:
    """Tests for the create_nested_hybrid_grid function."""

    def test_returns_grid(self):
        """Function must return an xtgeo.Grid."""
        grid, region, rid = _make_box_grid_with_region(dimension=(6, 6, 2))
        merged, nnc_table = create_nested_hybrid_grid(
            grid, region, rid, refinement=(1, 1, 1)
        )
        assert isinstance(merged, xtgeo.Grid)
        assert isinstance(nnc_table, pd.DataFrame)

    def test_basic_merge_dimensions(self):
        """Merged grid should have expected dimensions."""
        grid, region, rid = _make_box_grid_with_region(dimension=(6, 6, 2))
        merged, _ = create_nested_hybrid_grid(grid, region, rid, refinement=(1, 1, 1))

        # grid_merge places grid2 with a 1-column gap:
        # ncol = grid1.ncol + 1 + grid2.ncol
        assert merged.ncol > grid.ncol
        assert merged.nrow >= grid.nrow
        assert merged.nlay >= grid.nlay

    def test_nest_id_property_attached(self):
        """The merged grid must have a refinement region property."""
        grid, region, rid = _make_box_grid_with_region(dimension=(6, 6, 2))
        merged, _ = create_nested_hybrid_grid(grid, region, rid, refinement=(1, 1, 1))

        nest_id = merged.get_prop_by_name(region.name)
        assert nest_id is not None
        unique_vals = set(np.unique(np.ma.filled(nest_id.values, fill_value=0)))
        # Must contain at least coarse (1) and refined (2) cells
        assert 1 in unique_vals
        assert 2 in unique_vals

    def test_nest_id_values_consistent(self):
        """Active cells should only have refinement region in {1, 2}."""
        grid, region, rid = _make_box_grid_with_region(dimension=(6, 6, 2))
        merged, _ = create_nested_hybrid_grid(grid, region, rid, refinement=(1, 1, 1))

        nest_id = merged.get_prop_by_name(region.name)
        actnum = merged.get_actnum()

        active_mask = actnum.values == 1
        nest_active = np.ma.filled(nest_id.values, fill_value=0)[active_mask]
        assert set(np.unique(nest_active)).issubset({1, 2})

    def test_refinement_increases_cells(self):
        """Refinement > 1 should produce a merged grid with more total cells."""
        grid, region, rid = _make_box_grid_with_region(dimension=(6, 6, 2))
        merged_1x, _ = create_nested_hybrid_grid(
            grid, region, rid, refinement=(1, 1, 1)
        )
        merged_2x, _ = create_nested_hybrid_grid(
            grid, region, rid, refinement=(2, 2, 2)
        )
        assert merged_2x.ntotal > merged_1x.ntotal

    def test_invalid_refinement_raises(self):
        """Refinement factors < 1 should raise ValueError."""
        grid, region, rid = _make_box_grid_with_region(dimension=(6, 6, 2))
        with pytest.raises(ValueError, match="Refinement factors must be >= 1"):
            create_nested_hybrid_grid(grid, region, rid, refinement=(0, 1, 1))

    def test_original_grid_not_mutated(self):
        """The caller's grid and region should not be modified."""
        grid, region, rid = _make_box_grid_with_region(dimension=(6, 6, 2))

        orig_ncol = grid.ncol
        orig_nactive = grid.nactive
        orig_region_sum = int(np.ma.filled(region.values, 0).sum())

        _, _ = create_nested_hybrid_grid(grid, region, rid, refinement=(2, 2, 1))

        assert grid.ncol == orig_ncol
        assert grid.nactive == orig_nactive
        assert int(np.ma.filled(region.values, 0).sum()) == orig_region_sum

    def test_lmap_via_nnc(self):
        """Test correct lmaps generated indirectly via nnc_table.
        Cells in nnc_table for layer number completely controlled by lmap.
        """
        grid, region, rid = _make_box_grid_with_region(dimension=(3, 3, 3))

        region.values = np.ones(region.values.shape)
        region.values[1, 1, 1] = rid

        _, nnc_table = create_nested_hybrid_grid(
            grid, region, rid, refinement=(2, 2, 2)
        )
        nnc_table1 = nnc_table[
            (nnc_table["I1"] == 2)
            & (nnc_table["J1"] == 1)
            & (nnc_table["I2"] == 5)
            & (nnc_table["J2"] == 1)
        ]

        assert nnc_table1[(nnc_table1["K1"] == 2) & (nnc_table1["K2"] == 2)].shape == (
            1,
            7,
        )
        assert nnc_table1[(nnc_table1["K1"] == 2) & (nnc_table1["K2"] == 3)].shape == (
            1,
            7,
        )
        assert nnc_table1[(nnc_table1["K1"] == 3) & (nnc_table1["K2"] == 2)].shape == (
            0,
            7,
        )

    def test_zonation(self):
        """Input grid with zonation returns a valid zonation"""
        grid, region, rid = _make_box_grid_with_region(dimension=(6, 6, 2))
        grid.subgrids = {"ZONE1": [1], "ZONE2": [2]}
        merged, nnc_table = create_nested_hybrid_grid(
            grid, region, rid, refinement=(2, 2, 2)
        )
        subgrids_nlay = merged.get_subgrids()
        assert subgrids_nlay["ZONE1"] == 2
        assert subgrids_nlay["ZONE2"] == 2

        assert merged.subgrids["ZONE1"] == range(1, 3)
        assert merged.subgrids["ZONE2"] == range(3, 5)

    def test_zonation_with_layer_offset(self):
        """Input grid with zonation returns a valid zonation with offset"""
        grid, region, rid = _make_box_grid_with_region(dimension=(6, 6, 3))
        grid.subgrids = {"ZONE1": [1], "ZONE2": [2, 3]}

        region.values[:, :, 0] = 1  # set value in first layer to not be rid

        merged, nnc_table = create_nested_hybrid_grid(
            grid, region, rid, refinement=(2, 2, 2)
        )
        subgrids_nlay = merged.get_subgrids()
        assert subgrids_nlay["ZONE1"] == 1
        assert subgrids_nlay["ZONE2"] == 4

        assert merged.subgrids["ZONE1"] == range(1, 2)
        assert merged.subgrids["ZONE2"] == range(2, 6)


class TestNestedHybridGridClass:
    """Tests for class-specific behavior on NestedHybridGrid."""

    def test_nestedhybridgrid_grid_as_expected(self):
        """Test NestedHybridGrid produces a grid as expected."""

        grid = xtgeo.create_box_grid((6, 5, 2))

        region = xtgeo.GridProperty(grid, name="REGION", discrete=True, values=0)
        region.values[4:, 2:4, :] = 1

        nhg = NestedHybridGrid(coarse_grid=grid, region=region, refinement=(2, 2, 2))

        assert isinstance(nhg.grid, xtgeo.Grid)

        assert nhg.grid.ncol == 11
        assert nhg.grid.nrow == 5
        assert nhg.grid.nlay == 4

        assert nhg.grid.nactive == 116

        # subgrids did not exist in the original grid, so should be None
        assert nhg.grid.subgrids is None

        # Check that the refined bounding box is set correct from input region
        assert nhg._refined_bbox == BoundingBox.from_condition(region.values == 1)
        assert nhg._refined_bbox == BoundingBox(
            imin=5, imax=6, jmin=3, jmax=4, kmin=1, kmax=2
        )
        assert nhg._refined_nlay == 4

        # check that the two regions have expected indices in the merged grid
        region_prop = nhg.grid.get_prop_by_name("REGION")

        bbox_refined_area = BoundingBox.from_condition(region_prop.values == 1)
        assert bbox_refined_area == BoundingBox(
            imin=8, imax=11, jmin=1, jmax=4, kmin=1, kmax=4
        )
        bbox_coarse_area = BoundingBox.from_condition(region_prop.values == 0)
        assert bbox_coarse_area == BoundingBox(
            imin=1, imax=6, jmin=1, jmax=5, kmin=1, kmax=3
        )

    def test_nestedhybridgrid_properties_as_expected(self):
        """Test NestedHybridGrid preserves appended gridproperties."""

        grid = xtgeo.create_box_grid((6, 5, 2))

        region = xtgeo.GridProperty(grid, name="REGION", discrete=True, values=0)
        region.values[4:, 2:4, :] = 1

        custom_prop = xtgeo.GridProperty(grid, name="CUSTOM", discrete=True, values=0)
        grid.append_prop(custom_prop)

        nhg = NestedHybridGrid(coarse_grid=grid, region=region, refinement=(2, 2, 2))

        # check that the region property is attached to the merged grid
        assert len(nhg.properties) == 2

        prop_names = [prop.name for prop in nhg.properties]
        assert set(prop_names) == {"CUSTOM", "REGION"}

        region_prop = nhg.properties[0]

        assert isinstance(region_prop, xtgeo.GridProperty)
        assert region_prop.name == "REGION"
        assert region_prop.values.shape == nhg.grid.dimensions

    def test_nestedhybridgrid_nnc_table_as_expected(self):
        """Test NNC table contains one row per coarse-to-refined cell face."""

        grid = xtgeo.create_box_grid((3, 3, 1))

        region = xtgeo.GridProperty(grid, name="REGION", discrete=True, values=0)
        region.values[1, 1, 0] = 1

        nhg = NestedHybridGrid(coarse_grid=grid, region=region, refinement=(2, 2, 2))
        nnc_table = nhg.nnc_table

        assert isinstance(nnc_table, pd.DataFrame)

        assert set(nnc_table.columns) == {
            "I1",
            "J1",
            "K1",
            "I2",
            "J2",
            "K2",
            "DIRECTION",
        }

        assert len(nnc_table) == 16

        direction_counts = nnc_table["DIRECTION"].value_counts().to_dict()
        assert direction_counts == {"I+": 4, "J+": 4, "J-": 4, "I-": 4}

        def _has_single_row(i1, j1, k1, i2, j2, k2, direction):
            """Return True if the NNC table contains the specified row."""
            return (
                nnc_table[
                    (nnc_table["I1"] == i1)
                    & (nnc_table["J1"] == j1)
                    & (nnc_table["K1"] == k1)
                    & (nnc_table["I2"] == i2)
                    & (nnc_table["J2"] == j2)
                    & (nnc_table["K2"] == k2)
                    & (nnc_table["DIRECTION"] == direction)
                ].shape[0]
                == 1
            )

        # left neighbor of refined cell → connects to I- face of refined patch
        assert _has_single_row(i1=1, j1=2, k1=1, i2=5, j2=1, k2=1, direction="I+")
        # bottom neighbor → connects to J- face of refined patch
        assert _has_single_row(i1=2, j1=1, k1=1, i2=6, j2=1, k2=1, direction="J+")
        # top neighbor → connects to J+ face of refined patch
        assert _has_single_row(i1=2, j1=3, k1=1, i2=5, j2=2, k2=1, direction="J-")
        # right neighbor → connects to I+ face of refined patch
        assert _has_single_row(i1=3, j1=2, k1=1, i2=6, j2=2, k2=1, direction="I-")

    def test_inactive_neighbor_excluded_from_nnc(self):
        """Inactive coarse neighbor cells should not appear in the NNC table.

        Deactivating one of the four neighbors of the refinement cell removes
        all NNC connections through that face. With (2,2,2) refinement each
        I-face contributes 4 rows (2 J x 2 K), so deactivating the left
        coarse neighbor drops 4 I+ rows from the expected total of 16.
        """
        grid = xtgeo.create_box_grid((3, 3, 1))

        # Deactivate the left coarse neighbor of the refinement cell
        actnum = grid.get_actnum()
        actnum.values[0, 1, 0] = 0
        grid.set_actnum(actnum)

        region = xtgeo.GridProperty(grid, name="REGION", discrete=True, values=0)
        region.values[1, 1, 0] = 1

        nhg = NestedHybridGrid(coarse_grid=grid, region=region, refinement=(2, 2, 2))
        nnc_table = nhg.nnc_table

        # I+ connections (from the deactivated left neighbor) must be absent
        assert "I+" not in nnc_table["DIRECTION"].values
        assert len(nnc_table) == 12  # 16 total − 4 I+ connections

        direction_counts = nnc_table["DIRECTION"].value_counts().to_dict()
        assert direction_counts == {"J+": 4, "J-": 4, "I-": 4}

    def test_region_dimension_mismatch_raises(self):
        """Region dimensions must match the input grid dimensions."""
        grid = xtgeo.create_box_grid((1, 1, 1))
        region = xtgeo.GridProperty(ncol=2, nrow=2, nlay=2, discrete=True, values=1)

        with pytest.raises(ValueError, match="Region property dimensions"):
            NestedHybridGrid(coarse_grid=grid, region=region, refinement=(2, 2, 1))

    def test_invalid_refinement_tuple_shape_raises(self):
        """Refinement must be a 3-tuple."""
        grid, region, _rid = _make_box_grid_with_region(dimension=(4, 4, 2))

        with pytest.raises(ValueError, match="Refinement must be a tuple"):
            NestedHybridGrid(coarse_grid=grid, region=region, refinement=(2, 2))

    def test_missing_target_region_raises(self):
        """Missing target region id should raise a clear error."""
        grid, region, _rid = _make_box_grid_with_region(dimension=(4, 4, 2))

        with pytest.raises(ValueError, match="No cells found for target_region_id"):
            NestedHybridGrid(
                coarse_grid=grid,
                region=region,
                refinement=(2, 2, 1),
                target_region_id=999,
            )

    def test_zonation_preserved(self):
        """Merged grid should have expected updated zonation."""

        grid = xtgeo.create_box_grid((3, 3, 3))

        original_subgrids = {"ZONE_A": [1], "ZONE_B": [2], "ZONE_C": [3]}
        grid.subgrids = original_subgrids

        region = xtgeo.GridProperty(grid, discrete=True, values=0)
        region.values[:, :, 1] = 1  # refinement in ZONE_B

        nhg = NestedHybridGrid(coarse_grid=grid, region=region, refinement=(2, 2, 10))

        # Same zone names should exist in merged zonation.
        assert set(nhg.grid.subgrids) == set(original_subgrids)

        # Merged ranges should be contiguous, ordered, and cover all layers.
        assert nhg.grid.subgrids["ZONE_A"] == range(1, 2)
        assert nhg.grid.subgrids["ZONE_B"] == range(2, 12)  # refinement in ZONE_B
        assert nhg.grid.subgrids["ZONE_C"] == range(12, 13)

    def test_lmap_generation_simple(self):
        """Tests that the correct layer mappings are generated"""
        dimension = (4, 4, 3)
        target_layer_ids = [1]

        grid = xtgeo.create_box_grid(dimension)

        region = xtgeo.GridProperty(grid, discrete=True, values=0)
        region.values[:, :, target_layer_ids] = 1

        nhg = NestedHybridGrid(coarse_grid=grid, region=region, refinement=(2, 2, 2))

        lmap1 = nhg._layer_map_coarse
        lmap2 = nhg._layer_map_refined

        assert np.array_equal(lmap1, np.array([0, 1, 3]))
        assert np.array_equal(lmap2, np.array([1, 2]))

    def test_lmap_generation_no_offset(self):
        """Tests that the correct layer mappings are generated"""

        dimension = (3, 3, 3)
        target_layer_ids = [0, 1]

        grid = xtgeo.create_box_grid(dimension)

        region = xtgeo.GridProperty(grid, discrete=True, values=0)
        region.values[:, :, target_layer_ids] = 1

        nhg = NestedHybridGrid(coarse_grid=grid, region=region, refinement=(2, 2, 2))

        lmap1 = nhg._layer_map_coarse
        lmap2 = nhg._layer_map_refined

        assert np.array_equal(lmap1, np.array([0, 2, 4]))
        assert np.array_equal(lmap2, np.array([0, 1, 2, 3]))

    def test_lmap_generation_full_offset(self):
        """Tests a fully offset refinement window near the last coarse layer."""
        dimension = (3, 3, 3)
        target_layer_ids = [2]

        grid = xtgeo.create_box_grid(dimension)

        region = xtgeo.GridProperty(grid, discrete=True, values=0)
        region.values[:, :, target_layer_ids] = 1

        nhg = NestedHybridGrid(coarse_grid=grid, region=region, refinement=(2, 2, 4))

        lmap1 = nhg._layer_map_coarse
        lmap2 = nhg._layer_map_refined

        assert np.array_equal(lmap1, np.array([0, 1, 2]))
        assert np.array_equal(lmap2, np.array([2, 3, 4, 5]))

    def test_lmap_generation_ref10(self):
        """Tests that the correct layer mappings are generated"""
        dimension = (3, 3, 3)
        target_layer_ids = [1, 2]

        grid = xtgeo.create_box_grid(dimension)

        region = xtgeo.GridProperty(grid, discrete=True, values=0)
        region.values[0, :, target_layer_ids] = 1

        nhg = NestedHybridGrid(coarse_grid=grid, region=region, refinement=(1, 1, 10))

        lmap1 = nhg._layer_map_coarse
        lmap2 = nhg._layer_map_refined

        assert np.array_equal(lmap1, np.array([0, 1, 11]))
        assert np.array_equal(lmap2, np.arange(20) + 1)


# ---------------------------------------------------------------------------
# Tests for get_transmissibilities with nested hybrid NNCs
# ---------------------------------------------------------------------------


class TestTransmissibilitiesOnMergedGrid:
    """Test calling get_transmissibilities on the merged grid"""

    @staticmethod
    def _build_merged_with_props(dimension=(6, 6, 2), refinement=(1, 1, 1)):
        """Helper: build merged grid and attach constant perm/ntg properties."""
        grid, region, rid = _make_box_grid_with_region(dimension=dimension)
        merged, nnc_table = create_nested_hybrid_grid(
            grid, region, rid, refinement=refinement
        )

        permx = _make_constant_property(merged, "PERMX", 100.0)
        permy = _make_constant_property(merged, "PERMY", 100.0)
        permz = _make_constant_property(merged, "PERMZ", 10.0)
        ntg = _make_constant_property(merged, "NTG", 1.0)
        return merged, nnc_table, permx, permy, permz, ntg

    def test_transmissibilities_return_types(self):
        """get_transmissibilities should return the expected types."""
        merged, nnc_table, permx, permy, permz, ntg = self._build_merged_with_props()

        tranx, trany, tranz, nnc, nnc_nh, rbnd = merged.get_transmissibilities(
            permx=permx,
            permy=permy,
            permz=permz,
            ntg=ntg,
            nnc_table=nnc_table,
        )
        assert isinstance(tranx, xtgeo.GridProperty)
        assert isinstance(trany, xtgeo.GridProperty)
        assert isinstance(tranz, xtgeo.GridProperty)
        assert isinstance(nnc, pd.DataFrame)
        assert nnc_nh is None or isinstance(nnc_nh, pd.DataFrame)
        assert rbnd is None or isinstance(rbnd, xtgeo.GridProperty)

    def test_transmissibilities_positive(self):
        """Transmissibility values should be non-negative for a uniform grid."""
        merged, nnc_table, permx, permy, permz, ntg = self._build_merged_with_props()

        tranx, trany, tranz, *_ = merged.get_transmissibilities(
            permx=permx,
            permy=permy,
            permz=permz,
            ntg=ntg,
            nnc_table=nnc_table,
        )
        for tprop in (tranx, trany, tranz):
            vals = np.ma.filled(tprop.values, fill_value=0.0)
            assert np.all(vals >= 0.0)

    def test_nnc_dataframe_has_expected_columns(self):
        """The NNC DataFrame should have the standard columns."""
        merged, nnc_table, permx, permy, permz, ntg = self._build_merged_with_props()

        _, _, _, nnc, *_ = merged.get_transmissibilities(
            permx=permx,
            permy=permy,
            permz=permz,
            ntg=ntg,
            nnc_table=nnc_table,
        )
        expected = {"I1", "J1", "K1", "I2", "J2", "K2", "T", "TYPE"}
        assert expected.issubset(set(nnc.columns))

    def test_without_nnc_table(self):
        """get_transmissibilities without nnc_table should still work."""
        merged, _, permx, permy, permz, ntg = self._build_merged_with_props()

        tranx, trany, tranz, nnc, nnc_nh, rbnd = merged.get_transmissibilities(
            permx=permx,
            permy=permy,
            permz=permz,
            ntg=ntg,
        )
        assert isinstance(tranx, xtgeo.GridProperty)
        assert nnc_nh is None
        assert rbnd is None


# ---------------------------------------------------------------------------
# Tests for nnc_to_gridproperty
# ---------------------------------------------------------------------------


def _sample_nnc_df():
    """A small NNC DataFrame for testing utility functions."""
    return pd.DataFrame(
        {
            "I1": [1, 1, 1],
            "J1": [1, 1, 1],
            "K1": [1, 1, 1],
            "I2": [3, 3, 3],
            "J2": [1, 1, 1],
            "K2": [1, 1, 1],
            "T": [5.0, 7.0, 2.0],
            "TYPE": ["NestedHybrid", "NestedHybrid", "NestedHybrid"],
            "DIRECTION": ["I+", "J-", "K+"],
        }
    )


class TestNncToGridproperty:
    """Tests for nnc_to_gridproperty."""

    def test_returns_three_gridproperties(self):
        grid = xtgeo.create_box_grid((4, 4, 2))
        tx, ty, tz = nnc_to_gridproperty(grid, _sample_nnc_df())
        assert isinstance(tx, xtgeo.GridProperty)
        assert isinstance(ty, xtgeo.GridProperty)
        assert isinstance(tz, xtgeo.GridProperty)

    def test_property_names(self):
        grid = xtgeo.create_box_grid((4, 4, 2))
        tx, ty, tz = nnc_to_gridproperty(grid, _sample_nnc_df())
        assert tx.name == "TRANX_NNC"
        assert ty.name == "TRANY_NNC"
        assert tz.name == "TRANZ_NNC"

    def test_plus_direction_maps_to_i1j1k1(self):
        """I+ row should place T at cell (I1, J1, K1) in TRANX_NNC."""
        grid = xtgeo.create_box_grid((4, 4, 2))
        df = pd.DataFrame(
            {
                "I1": [2],
                "J1": [1],
                "K1": [1],
                "I2": [4],
                "J2": [1],
                "K2": [1],
                "T": [10.0],
                "DIRECTION": ["I+"],
            }
        )
        tx, _, _ = nnc_to_gridproperty(grid, df)
        # 1-based (2,1,1) -> 0-based (1,0,0)
        assert tx.values[1, 0, 0] == pytest.approx(10.0)

    def test_minus_direction_maps_to_i2j2k2(self):
        """J- row should place T at cell (I2, J2, K2) in TRANY_NNC."""
        grid = xtgeo.create_box_grid((4, 4, 2))
        df = pd.DataFrame(
            {
                "I1": [1],
                "J1": [1],
                "K1": [1],
                "I2": [3],
                "J2": [2],
                "K2": [1],
                "T": [8.0],
                "DIRECTION": ["J-"],
            }
        )
        _, ty, _ = nnc_to_gridproperty(grid, df)
        # 1-based (3,2,1) -> 0-based (2,1,0)
        assert ty.values[2, 1, 0] == pytest.approx(8.0)

    def test_untouched_cells_are_fill(self):
        """Cells without an NNC should have value -1."""
        grid = xtgeo.create_box_grid((4, 4, 2))
        df = pd.DataFrame(
            {
                "I1": [1],
                "J1": [1],
                "K1": [1],
                "I2": [3],
                "J2": [1],
                "K2": [1],
                "T": [5.0],
                "DIRECTION": ["I+"],
            }
        )
        tx, _, _ = nnc_to_gridproperty(grid, df)
        # cell (0,0,0) has value 5.0; cell (0,0,1) should be -1
        assert tx.values[0, 0, 1] == pytest.approx(-1.0)

    def test_summing_parallel_paths(self):
        """Two rows mapping to the same cell should sum."""
        grid = xtgeo.create_box_grid((4, 4, 2))
        df = pd.DataFrame(
            {
                "I1": [2, 2],
                "J1": [1, 1],
                "K1": [1, 1],
                "I2": [4, 4],
                "J2": [1, 1],
                "K2": [1, 1],
                "T": [3.0, 7.0],
                "DIRECTION": ["I+", "I+"],
            }
        )
        tx, _, _ = nnc_to_gridproperty(grid, df)
        assert tx.values[1, 0, 0] == pytest.approx(10.0)

    def test_missing_columns_raises(self):
        grid = xtgeo.create_box_grid((4, 4, 2))
        bad_df = pd.DataFrame({"I1": [1], "J1": [1]})
        with pytest.raises(ValueError, match="Missing required columns"):
            nnc_to_gridproperty(grid, bad_df)

    def test_empty_dataframe(self):
        """Empty nnc_df should return properties filled with -1."""
        grid = xtgeo.create_box_grid((4, 4, 2))
        df = pd.DataFrame(
            columns=["I1", "J1", "K1", "I2", "J2", "K2", "T", "DIRECTION"]
        )
        tx, ty, tz = nnc_to_gridproperty(grid, df)
        assert np.all(tx.values == pytest.approx(-1.0))
        assert np.all(ty.values == pytest.approx(-1.0))
        assert np.all(tz.values == pytest.approx(-1.0))


# ---------------------------------------------------------------------------
# Tests for nnc_to_flowsimulator_input
# ---------------------------------------------------------------------------


class TestNncToFlowsimulatorInput:
    """Tests for nnc_to_flowsimulator_input."""

    def test_writes_file(self, tmp_path):
        out = tmp_path / "nnc.inc"
        nnc_to_flowsimulator_input(_sample_nnc_df(), out)
        assert out.exists()

    def test_file_starts_with_nnc_keyword(self, tmp_path):
        out = tmp_path / "nnc.inc"
        nnc_to_flowsimulator_input(_sample_nnc_df(), out)
        lines = out.read_text().splitlines()
        assert lines[0] == "NNC"

    def test_file_ends_with_slash(self, tmp_path):
        out = tmp_path / "nnc.inc"
        nnc_to_flowsimulator_input(_sample_nnc_df(), out)
        lines = out.read_text().splitlines()
        assert lines[-1] == "/"

    def test_correct_number_of_data_lines(self, tmp_path):
        """One data line per row between NNC header and closing /."""
        df = _sample_nnc_df()
        out = tmp_path / "nnc.inc"
        nnc_to_flowsimulator_input(df, out)
        lines = out.read_text().splitlines()
        # header + N data lines + closing /
        assert len(lines) == len(df) + 2

    def test_data_line_contains_indices_and_t(self, tmp_path):
        df = pd.DataFrame(
            {
                "I1": [2],
                "J1": [3],
                "K1": [4],
                "I2": [5],
                "J2": [6],
                "K2": [7],
                "T": [1.234567],
                "TYPE": ["NestedHybrid"],
                "DIRECTION": ["I+"],
            }
        )
        out = tmp_path / "nnc.inc"
        nnc_to_flowsimulator_input(df, out)
        content = out.read_text()
        assert "2" in content and "3" in content and "4" in content
        assert "5" in content and "6" in content and "7" in content
        assert "1.234567" in content

    def test_comments_with_type_and_direction(self, tmp_path):
        out = tmp_path / "nnc.inc"
        nnc_to_flowsimulator_input(_sample_nnc_df(), out)
        content = out.read_text()
        assert "-- NestedHybrid I+" in content

    def test_no_comments_without_optional_columns(self, tmp_path):
        df = pd.DataFrame(
            {
                "I1": [1],
                "J1": [1],
                "K1": [1],
                "I2": [2],
                "J2": [1],
                "K2": [1],
                "T": [1.0],
            }
        )
        out = tmp_path / "nnc.inc"
        nnc_to_flowsimulator_input(df, out)
        content = out.read_text()
        assert "--" not in content

    def test_missing_columns_raises(self, tmp_path):
        out = tmp_path / "nnc.inc"
        bad_df = pd.DataFrame({"I1": [1], "T": [1.0]})
        with pytest.raises(ValueError, match="Missing required columns"):
            nnc_to_flowsimulator_input(bad_df, out)

    def test_empty_dataframe_writes_skeleton(self, tmp_path):
        """Empty nnc_df should produce just NNC header and closing /."""
        df = pd.DataFrame(columns=["I1", "J1", "K1", "I2", "J2", "K2", "T"])
        out = tmp_path / "nnc.inc"
        nnc_to_flowsimulator_input(df, out)
        lines = out.read_text().splitlines()
        assert lines == ["NNC", "/"]
