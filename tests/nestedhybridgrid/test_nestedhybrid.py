"""Tests for fmu.tools.nestedhybridgrid.nestedhybrid."""

from unittest.mock import patch

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
from fmu.tools.nestedhybridgrid.nestedhybrid import (
    ORIGINAL_IJK_PROPERTY_NAMES,
    BoundingBox,
    CellsByParent,
    _create_upscaling_mappings_arrays,
    _ijk_to_flat_index,
    _set_actnum_in_grid,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_box_grid_with_region(
    dimension=(6, 6, 3),
    increment=(50.0, 50.0, 10.0),
    target_region_id=1,
    target_layer_ids: list[int] | None = None,
):
    """Create a simple box grid with a region property.

    The grid is split into two regions along the I-axis:
      - region 1: columns 0 .. ncol//2 - 1
      - region 2: columns ncol//2 .. ncol - 1

    Returns (grid, region, target_region_id).
    """
    grid = xtgeo.create_box_grid(dimension, increment=increment)
    ncol, nrow, nlay = dimension

    region_values = np.zeros((ncol, nrow, nlay), dtype=np.int32)
    half = ncol // 2
    region_values[half:, :, target_layer_ids or range(nlay)] = target_region_id

    region = xtgeo.GridProperty(
        grid, name="REGION", discrete=True, values=region_values
    )
    return grid, region, target_region_id


def _make_constant_property(grid, name, value):
    """Create a continuous GridProperty with a constant value."""
    vals = np.full(grid.dimensions, value, dtype=np.float64)
    return xtgeo.GridProperty(grid, name=name, values=vals)


def _build_geogrid_parent_ijk_maps_and_region(
    grid: xtgeo.Grid,
    region: xtgeo.GridProperty,
    refinement: tuple[int, int, int],
) -> tuple[
    xtgeo.GridProperty, xtgeo.GridProperty, xtgeo.GridProperty, xtgeo.GridProperty
]:
    """Refine a grid and return preserved parent I/J/K properties."""
    geogrid = grid.copy()

    geogrid.append_prop(region)

    for prop in geogrid.get_ijk(names=ORIGINAL_IJK_PROPERTY_NAMES):
        geogrid.append_prop(prop)

    geogrid.refine(*refinement)

    return (
        geogrid.get_prop_by_name("parent_I"),
        geogrid.get_prop_by_name("parent_J"),
        geogrid.get_prop_by_name("parent_K"),
        geogrid.get_prop_by_name(region.name),
    )


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


def test_ijk_to_flat_index_matches_c_order_formula():
    """Flat index mapping should match NumPy's C-order ravel mapping."""
    grid = xtgeo.create_box_grid((3, 4, 5))

    i, j, k = grid.get_ijk()
    i0 = i.values - 1
    j0 = j.values - 1
    k0 = k.values - 1

    got = _ijk_to_flat_index(i=i0, j=j0, k=k0, jdim=4, kdim=5)
    expected = np.ravel_multi_index((i0, j0, k0), dims=(3, 4, 5))
    np.testing.assert_array_equal(got, expected)


def test_cell_by_parent_groups_selected_positions():
    """Selected indices should be grouped by parent cell in sorted key order."""
    parent_indices = np.array([3, 7, 3, 5, 7, 5, 3])
    selected_mask = np.array([True, False, True, True, False, True, False])

    grouped = CellsByParent.from_parent_indices(
        parent_indices=parent_indices,
        selected_mask=selected_mask,
        parent_cell_count=8,
    )
    np.testing.assert_array_equal(grouped.mapped_parent_indices, [3, 5])
    np.testing.assert_array_equal(grouped.cell_indices, np.array([0, 2, 3, 5]))
    np.testing.assert_array_equal(grouped.counts, np.array([0, 0, 0, 2, 0, 2, 0, 0]))

    expected_active_mask = [False, False, False, True, False, True, False, False]
    np.testing.assert_array_equal(grouped.counts > 0, expected_active_mask)

    np.testing.assert_array_equal(grouped.get_indices(3), np.array([0, 2]))
    np.testing.assert_array_equal(grouped.get_indices(5), np.array([3, 5]))

    with pytest.raises(ValueError, match="No cells found for parent index 0"):
        grouped.get_indices(0)
    with pytest.raises(ValueError, match="No cells found for parent index 7"):
        grouped.get_indices(7)


def test_cell_by_parent_raises_when_nothing_selected():
    """No selected entries should raise ValueError."""
    parent_indices = np.array([2, 2, 5])
    selected_mask = np.array([False, False, False])

    with pytest.raises(ValueError, match="No selected parent indices found"):
        CellsByParent.from_parent_indices(
            parent_indices=parent_indices,
            selected_mask=selected_mask,
            parent_cell_count=6,
        )


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
        # Must contain at least coarse (0) and refined (1) cells
        assert 0 in unique_vals
        assert 1 in unique_vals

    def test_nest_id_values_consistent(self):
        """Active cells should only have refinement region in {0, 1}."""
        grid, region, rid = _make_box_grid_with_region(dimension=(6, 6, 2))
        merged, _ = create_nested_hybrid_grid(grid, region, rid, refinement=(1, 1, 1))

        nest_id = merged.get_prop_by_name(region.name)
        actnum = merged.get_actnum()

        active_mask = actnum.values == 1
        nest_active = np.ma.filled(nest_id.values, fill_value=0)[active_mask]
        assert set(np.unique(nest_active)).issubset({0, 1})

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

        region.values = np.zeros(region.values.shape)
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

        region.values[:, :, 0] = 0  # set value in first layer to not be rid

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

    def test_nestedhybridgrid_with_target_region_id_2_builds_expected_grid(self):
        """Non-default target_region_id should drive which cells are refined."""
        grid = xtgeo.create_box_grid((6, 5, 2))

        region = xtgeo.GridProperty(grid, name="REGION", discrete=True, values=0)

        rid = 2
        region.values[4:, 2:4, :] = rid

        nhg = NestedHybridGrid(
            coarse_grid=grid,
            region=region,
            refinement=(2, 2, 2),
            target_region_id=rid,
        )

        merged = nhg.grid
        assert isinstance(merged, xtgeo.Grid)
        assert nhg.grid.dimensions == (11, 5, 4)

        assert nhg._refined_bbox == BoundingBox.from_condition(region.values == rid)
        assert nhg._refined_bbox == BoundingBox(
            imin=5, imax=6, jmin=3, jmax=4, kmin=1, kmax=2
        )

        region_merged = merged.get_prop_by_name("REGION")
        assert region_merged is not None

        bbox_refined_area = BoundingBox.from_condition(region_merged.values == rid)
        assert bbox_refined_area == BoundingBox(
            imin=8, imax=11, jmin=1, jmax=4, kmin=1, kmax=4
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
        assert len(nhg.properties) == 5

        prop_names = [prop.name for prop in nhg.properties]
        assert set(prop_names) == {"CUSTOM", "REGION", *ORIGINAL_IJK_PROPERTY_NAMES}

        region_prop = nhg.grid.get_prop_by_name("REGION")

        assert isinstance(region_prop, xtgeo.GridProperty)
        assert region_prop.name == "REGION"
        assert region_prop.values.shape == nhg.grid.dimensions

        parent_i, parent_j, parent_k = (
            nhg.grid.get_prop_by_name(name) for name in ORIGINAL_IJK_PROPERTY_NAMES
        )

        assert parent_i.values.shape == nhg.grid.dimensions
        assert parent_j.values.shape == nhg.grid.dimensions
        assert parent_k.values.shape == nhg.grid.dimensions

        assert parent_i.values[0, 0, 0] == 1
        assert parent_j.values[0, 0, 0] == 1
        assert parent_k.values[0, 0, 0] == 1

        assert set(np.unique(parent_i.values[7:11, 0:4, 0:4])) == {5, 6}
        assert set(np.unique(parent_j.values[7:11, 0:4, 0:4])) == {3, 4}
        assert set(np.unique(parent_k.values[7:11, 0:4, 0:4])) == {1, 2}

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

    def test_create_upscaling_mappings_with_even_refinement(self):
        """create_upscaling_mappings behave as expected with even refinement."""
        grid, region, target_region_id = _make_box_grid_with_region(dimension=(6, 6, 3))
        refinement = (2, 2, 2)
        nhg = NestedHybridGrid(coarse_grid=grid, region=region, refinement=refinement)

        i_map, j_map, k_map, gg_region = _build_geogrid_parent_ijk_maps_and_region(
            grid, region=region, refinement=(4, 2, 2)
        )

        i_out, j_out, k_out = nhg.create_upscaling_mappings(i_map, j_map, k_map)

        assert isinstance(i_out, xtgeo.GridProperty)
        assert isinstance(j_out, xtgeo.GridProperty)
        assert isinstance(k_out, xtgeo.GridProperty)
        assert i_out.name == "nested_I"
        assert j_out.name == "nested_J"
        assert k_out.name == "nested_K"

        # output mappings have the same dimensions as the geogrid
        assert i_out.dimensions == i_map.dimensions == (24, 12, 6)
        assert j_out.dimensions == j_map.dimensions == (24, 12, 6)
        assert k_out.dimensions == k_map.dimensions == (24, 12, 6)

        in_refined = gg_region.values == target_region_id
        outside_refined = ~in_refined

        # Outside refinement: I/J unchanged, K uses coarse layer mapping.
        np.testing.assert_array_equal(
            i_out.values[outside_refined],
            i_map.values[outside_refined],
        )
        np.testing.assert_array_equal(
            j_out.values[outside_refined],
            j_map.values[outside_refined],
        )
        expected_k_outside = (
            nhg._layer_map_coarse[k_map.values[outside_refined].astype(int) - 1] + 1
        )
        np.testing.assert_array_equal(k_out.values[outside_refined], expected_k_outside)

        # Inside refinement: I/J/K should follow the refined mapping.
        i_parent = i_map.values[in_refined]
        j_parent = j_map.values[in_refined]
        k_parent = k_map.values[in_refined]

        i_refined = i_out.values[in_refined]
        j_refined = j_out.values[in_refined]
        k_refined = k_out.values[in_refined]

        # Each mapped cell should land in the expected 2-cell span per parent index
        # There is a one column offset in the nested grid hence the shift in I.
        assert np.all((i_refined == 2 * i_parent) | (i_refined == 2 * i_parent + 1))
        assert np.all((j_refined == 2 * j_parent - 1) | (j_refined == 2 * j_parent))
        assert np.all((k_refined == 2 * k_parent - 1) | (k_refined == 2 * k_parent))

    @pytest.mark.parametrize("inactive_parent", [False, True])
    def test_create_upscaling_mappings_accepts_integer_valued_floats(
        self, inactive_parent
    ):
        """Continuous IJK properties should map like discrete IJK properties."""
        grid, region, _ = _make_box_grid_with_region(dimension=(6, 6, 3))
        if inactive_parent:
            actnum = grid.get_actnum()
            actnum.values[0, 0, 0] = 0
            grid.set_actnum(actnum)

        nhg = NestedHybridGrid(grid, region, refinement=(2, 2, 2))
        i_map, j_map, k_map, _ = _build_geogrid_parent_ijk_maps_and_region(
            grid, region, refinement=(4, 2, 2)
        )
        expected = nhg.create_upscaling_mappings(i_map, j_map, k_map)
        for prop in (i_map, j_map, k_map):
            prop.isdiscrete = False
            assert np.issubdtype(prop.values.dtype, np.floating)
            prop.values.data[np.ma.getmaskarray(prop.values)] = np.nan

        with np.errstate(invalid="raise"):
            actual = nhg.create_upscaling_mappings(i_map, j_map, k_map)

        for actual_prop, expected_prop in zip(actual, expected):
            np.testing.assert_array_equal(
                actual_prop.values.compressed(), expected_prop.values.compressed()
            )
            np.testing.assert_array_equal(
                np.ma.getmaskarray(actual_prop.values),
                np.ma.getmaskarray(expected_prop.values),
            )

    def test_create_upscaling_mappings_with_uneven_refinement(self):
        """create_upscaling_mappings behave as expected with uneven refinement."""
        grid, region, target_region_id = _make_box_grid_with_region(dimension=(6, 6, 2))

        refinement = (3, 2, 4)
        nhg = NestedHybridGrid(coarse_grid=grid, region=region, refinement=refinement)

        # refinement for the geogrid must be divisible by nhg refinement
        i_map, j_map, k_map, gg_region = _build_geogrid_parent_ijk_maps_and_region(
            grid, region=region, refinement=(6, 2, 8)
        )

        i_out, j_out, k_out = nhg.create_upscaling_mappings(i_map, j_map, k_map)

        in_refined = gg_region.values == target_region_id
        outside_refined = ~in_refined

        # Outside refinement: I/J unchanged, K uses coarse layer mapping.
        np.testing.assert_array_equal(
            i_out.values[outside_refined],
            i_map.values[outside_refined],
        )
        np.testing.assert_array_equal(
            j_out.values[outside_refined],
            j_map.values[outside_refined],
        )
        expected_k_outside = (
            nhg._layer_map_coarse[k_map.values[outside_refined].astype(int) - 1] + 1
        )
        np.testing.assert_array_equal(k_out.values[outside_refined], expected_k_outside)

        # Inside refinement: I/J/K should follow the refined mapping.
        i_parent = i_map.values[in_refined]
        j_parent = j_map.values[in_refined]
        k_parent = k_map.values[in_refined]

        i_refined = i_out.values[in_refined]
        j_refined = j_out.values[in_refined]
        k_refined = k_out.values[in_refined]

        # Each parent index should map to a block with size equal to
        # the configured refinement factor on that axis.
        for p_i in np.unique(i_parent):
            u_i_out = np.unique(i_refined[i_parent == p_i])
            assert u_i_out.size == refinement[0] == 3
            assert np.array_equal(u_i_out, np.arange(u_i_out.min(), u_i_out.min() + 3))

        for p_j in np.unique(j_parent):
            u_j_out = np.unique(j_refined[j_parent == p_j])
            assert u_j_out.size == refinement[1] == 2
            assert np.array_equal(u_j_out, np.arange(u_j_out.min(), u_j_out.min() + 2))

        for p_k in np.unique(k_parent):
            u_k_out = np.unique(k_refined[k_parent == p_k])
            assert u_k_out.size == refinement[2] == 4
            assert np.array_equal(u_k_out, np.arange(u_k_out.min(), u_k_out.min() + 4))

    def test_create_upscaling_mappings_raises_on_out_of_range_parent_values(self):
        """Out-of-range values in input parent maps should raise ValueError."""
        grid, region, _ = _make_box_grid_with_region(dimension=(6, 6, 2))
        nhg = NestedHybridGrid(coarse_grid=grid, region=region, refinement=(2, 2, 2))

        i_map, j_map, k_map = grid.get_ijk(names=("GI", "GJ", "GK"))
        i_bad = i_map.copy()

        # Test with an out-of-range I index (too low).
        i_bad.values[0, 0, 0] = -1
        with pytest.raises(ValueError, match="outside the valid range"):
            nhg.create_upscaling_mappings(i_bad, j_map, k_map)

        # Test with an out-of-range I index (too high).
        i_bad.values[0, 0, 0] = grid.ncol + 1
        with pytest.raises(ValueError, match="outside the valid range"):
            nhg.create_upscaling_mappings(i_bad, j_map, k_map)

    def test_create_upscaling_mappings_raises_on_different_input_dimensions(self):
        """Input parent maps with different dimensions should raise ValueError."""
        grid, region, _ = _make_box_grid_with_region(dimension=(6, 6, 2))
        nhg = NestedHybridGrid(coarse_grid=grid, region=region, refinement=(2, 2, 2))

        i_map, _, k_map, _ = _build_geogrid_parent_ijk_maps_and_region(
            grid, region, refinement=(4, 2, 2)
        )
        # make a property with different dimensions than i_map
        j_map = xtgeo.GridProperty(ncol=10, nrow=10, nlay=10)

        with pytest.raises(ValueError, match="same dimensions"):
            nhg.create_upscaling_mappings(i_map, j_map, k_map)

    def test_create_upscaling_mappings_excludes_all_zero_input_values(self):
        """All-zero input coordinates produce zeroes in all three output axes."""
        grid, region, _ = _make_box_grid_with_region(dimension=(6, 6, 2))
        nhg = NestedHybridGrid(grid, region, refinement=(2, 2, 2))

        i_map, j_map, k_map, _ = _build_geogrid_parent_ijk_maps_and_region(
            grid, region, refinement=(4, 2, 2)
        )
        for mapping in (i_map, j_map, k_map):
            mapping.values[1, 2, 3] = 0

        i_out, j_out, k_out = nhg.create_upscaling_mappings(i_map, j_map, k_map)

        assert i_out.values[1, 2, 3] == 0
        assert j_out.values[1, 2, 3] == 0
        assert k_out.values[1, 2, 3] == 0

    @pytest.mark.parametrize("zero_axis", [0, 1, 2])
    def test_create_upscaling_mappings_raises_on_partial_zero_input_values(
        self, zero_axis
    ):
        """A zero on one input axis requires zeroes on the other two axes."""
        grid, region, _ = _make_box_grid_with_region(dimension=(6, 6, 2))
        nhg = NestedHybridGrid(grid, region, refinement=(2, 2, 2))

        i_map, j_map, k_map, _ = _build_geogrid_parent_ijk_maps_and_region(
            grid, region, refinement=(4, 2, 2)
        )
        ijk_maps = [i_map, j_map, k_map]
        ijk_maps[zero_axis].values[1, 2, 3] = 0

        with pytest.raises(ValueError, match="all must be zero"):
            nhg.create_upscaling_mappings(*ijk_maps)

    def test_create_upscaling_mappings_excludes_layers_with_zero(self):
        """Test excluding whole layers while keeping deeper cells mapped."""
        grid, region, _ = _make_box_grid_with_region(
            dimension=(6, 6, 4), target_layer_ids=[2, 3]
        )
        nhg = NestedHybridGrid(grid, region, refinement=(2, 2, 2))

        i_map, j_map, k_map, _ = _build_geogrid_parent_ijk_maps_and_region(
            grid, region, refinement=(4, 2, 2)
        )

        # create baseline mapping before zeroing out layers
        i_baseline, j_baseline, k_baseline = nhg.create_upscaling_mappings(
            i_map, j_map, k_map
        )

        # Two parent layers correspond to four geogrid layers.
        i_map.values[:, :, :4] = 0
        j_map.values[:, :, :4] = 0
        k_map.values[:, :, :4] = 0

        i_out, j_out, k_out = nhg.create_upscaling_mappings(i_map, j_map, k_map)

        assert (i_out.values[:, :, :4] == 0).all()
        assert (i_out.values[:, :, 4:] == i_baseline.values[:, :, 4:]).all()
        assert (j_out.values[:, :, :4] == 0).all()
        assert (j_out.values[:, :, 4:] == j_baseline.values[:, :, 4:]).all()
        assert (k_out.values[:, :, :4] == 0).all()
        assert (k_out.values[:, :, 4:] == k_baseline.values[:, :, 4:]).all()

    def test_create_upscaling_mappings_raises_on_invalid_refined_block(self):
        """Non-divisible geogrid spans per parent cell should raise ValueError."""
        grid, region, _ = _make_box_grid_with_region(dimension=(6, 6, 2))
        nhg = NestedHybridGrid(coarse_grid=grid, region=region, refinement=(2, 2, 2))

        # Build geogrid mappings with 3x2x2 refinement, which is incompatible
        # with nhg refinement=(2,2,2)
        i_map, j_map, k_map, _ = _build_geogrid_parent_ijk_maps_and_region(
            grid, region=region, refinement=(3, 2, 2)
        )

        with pytest.raises(ValueError, match="Invalid input mapping for cells"):
            nhg.create_upscaling_mappings(i_map, j_map, k_map)

    def test_create_upscaling_mappings_raises_on_non_gridproperty_input(self):
        """Input mapping objects must be xtgeo.GridProperty instances."""
        grid, region, _ = _make_box_grid_with_region(dimension=(6, 6, 2))
        nhg = NestedHybridGrid(coarse_grid=grid, region=region, refinement=(2, 2, 2))

        _, j_map, k_map = grid.get_ijk(names=("GI", "GJ", "GK"))

        with pytest.raises(ValueError, match="must be xtgeo.GridProperty"):
            nhg.create_upscaling_mappings("invalid", j_map, k_map)

    def test_create_upscaling_mappings_raises_on_non_integer_parent_values(self):
        """Fractional parent-IJK values should fail input validation."""
        grid, region, _ = _make_box_grid_with_region(dimension=(6, 6, 2))
        nhg = NestedHybridGrid(coarse_grid=grid, region=region, refinement=(2, 2, 2))

        i_map, j_map, k_map = grid.get_ijk(names=("GI", "GJ", "GK"))
        i_bad = i_map.copy()
        i_bad.discrete_to_continuous()
        i_bad.values[0, 0, 0] = 1.5

        with pytest.raises(ValueError, match="must contain integer values"):
            nhg.create_upscaling_mappings(i_bad, j_map, k_map)

    def test_create_upscaling_mappings_preserves_masked_cells(self):
        """Masked geogrid cells should remain masked in mapped outputs."""
        grid, region, _ = _make_box_grid_with_region(dimension=(6, 6, 2))
        nhg = NestedHybridGrid(coarse_grid=grid, region=region, refinement=(2, 2, 2))

        i_map, j_map, k_map, _ = _build_geogrid_parent_ijk_maps_and_region(
            grid, region=region, refinement=(4, 2, 2)
        )
        i_map.values[0, 0, 0] = np.ma.masked
        j_map.values[0, 0, 0] = np.ma.masked
        k_map.values[0, 0, 0] = np.ma.masked

        i_out, j_out, k_out = nhg.create_upscaling_mappings(i_map, j_map, k_map)

        assert i_out.values.mask[0, 0, 0]
        assert j_out.values.mask[0, 0, 0]
        assert k_out.values.mask[0, 0, 0]

        assert (i_out.values.mask == i_map.values.mask).all()
        assert (j_out.values.mask == j_map.values.mask).all()
        assert (k_out.values.mask == k_map.values.mask).all()

    def test_create_upscaling_mappings_arrays_raises_on_parent_coverage_mismatch(self):
        """Array core should reject mismatched parent-cell coverage."""
        grid, region, _ = _make_box_grid_with_region(dimension=(6, 6, 2))
        nhg = NestedHybridGrid(coarse_grid=grid, region=region, refinement=(2, 2, 2))

        i_map, j_map, k_map = grid.get_ijk(names=("GI", "GJ", "GK"))

        mapping = nhg.nested_cells_by_parent
        missing_parent = mapping.mapped_parent_indices[0]
        mapping.group_start[missing_parent] = mapping.group_stop[missing_parent] = -1

        bad_parent_mapping = CellsByParent(
            cell_indices=mapping.cell_indices,
            group_start=mapping.group_start,
            group_stop=mapping.group_stop,
        )

        with pytest.raises(ValueError, match="do not match"):
            _create_upscaling_mappings_arrays(
                geo_parent_i_values=i_map.values,
                geo_parent_j_values=j_map.values,
                geo_parent_k_values=k_map.values,
                nested_cells_by_parent=bad_parent_mapping,
                nested_dimensions=nhg.grid.dimensions,
                parent_dimensions=nhg._parent_dimensions,
                layer_map_coarse=nhg._layer_map_coarse,
                refinement=nhg._refinement,
            )

    def test_write_nnc_table_writes_csv_without_index(self, tmp_path):
        """NNC table can be written to CSV without the pandas index."""
        grid, region, _ = _make_box_grid_with_region(dimension=(3, 3, 1))
        nhg = NestedHybridGrid(coarse_grid=grid, region=region, refinement=(2, 2, 2))
        outfile = tmp_path / "nnc_table.csv"

        nhg.write_nnc_table(outfile)

        written = pd.read_csv(outfile)
        assert "Unnamed: 0" not in written.columns
        pd.testing.assert_frame_equal(written, nhg.nnc_table, check_dtype=False)

    def test_write_nnc_table_creates_output_directories(self, tmp_path):
        """Missing parent directories are created before writing the table."""
        grid, region, _ = _make_box_grid_with_region(dimension=(3, 3, 1))
        nhg = NestedHybridGrid(coarse_grid=grid, region=region, refinement=(2, 2, 2))
        outfile = tmp_path / "nested" / "output" / "nnc_table.csv"

        nhg.write_nnc_table(outfile)

        assert outfile.is_file()

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

    def test_nnc_table_exact_rows(self):
        """Test exact NNC rows for a 3x3x1 case."""
        grid = xtgeo.create_box_grid((3, 3, 1))

        region = xtgeo.GridProperty(grid, name="REGION", discrete=True, values=0)
        region.values[1, 1, 0] = 1

        nhg = NestedHybridGrid(coarse_grid=grid, region=region, refinement=(2, 2, 2))
        actual = nhg.nnc_table.sort_values(
            by=["I1", "J1", "K1", "I2", "J2", "K2", "DIRECTION"]
        ).reset_index(drop=True)

        expected_rows = [
            {"I1": 1, "J1": 2, "K1": 1, "I2": 5, "J2": 1, "K2": 1, "DIRECTION": "I+"},
            {"I1": 1, "J1": 2, "K1": 1, "I2": 5, "J2": 1, "K2": 2, "DIRECTION": "I+"},
            {"I1": 1, "J1": 2, "K1": 1, "I2": 5, "J2": 2, "K2": 1, "DIRECTION": "I+"},
            {"I1": 1, "J1": 2, "K1": 1, "I2": 5, "J2": 2, "K2": 2, "DIRECTION": "I+"},
            {"I1": 2, "J1": 1, "K1": 1, "I2": 5, "J2": 1, "K2": 1, "DIRECTION": "J+"},
            {"I1": 2, "J1": 1, "K1": 1, "I2": 5, "J2": 1, "K2": 2, "DIRECTION": "J+"},
            {"I1": 2, "J1": 1, "K1": 1, "I2": 6, "J2": 1, "K2": 1, "DIRECTION": "J+"},
            {"I1": 2, "J1": 1, "K1": 1, "I2": 6, "J2": 1, "K2": 2, "DIRECTION": "J+"},
            {"I1": 2, "J1": 3, "K1": 1, "I2": 5, "J2": 2, "K2": 1, "DIRECTION": "J-"},
            {"I1": 2, "J1": 3, "K1": 1, "I2": 5, "J2": 2, "K2": 2, "DIRECTION": "J-"},
            {"I1": 2, "J1": 3, "K1": 1, "I2": 6, "J2": 2, "K2": 1, "DIRECTION": "J-"},
            {"I1": 2, "J1": 3, "K1": 1, "I2": 6, "J2": 2, "K2": 2, "DIRECTION": "J-"},
            {"I1": 3, "J1": 2, "K1": 1, "I2": 6, "J2": 1, "K2": 1, "DIRECTION": "I-"},
            {"I1": 3, "J1": 2, "K1": 1, "I2": 6, "J2": 1, "K2": 2, "DIRECTION": "I-"},
            {"I1": 3, "J1": 2, "K1": 1, "I2": 6, "J2": 2, "K2": 1, "DIRECTION": "I-"},
            {"I1": 3, "J1": 2, "K1": 1, "I2": 6, "J2": 2, "K2": 2, "DIRECTION": "I-"},
        ]
        expected = (
            pd.DataFrame.from_records(expected_rows)
            .sort_values(by=["I1", "J1", "K1", "I2", "J2", "K2", "DIRECTION"])
            .reset_index(drop=True)
        )

        pd.testing.assert_frame_equal(actual, expected, check_dtype=False)

    def test_all_outside_neighbors_inactive_produces_no_nnc(self):
        """No active outside neighbors means no boundary NNC rows."""
        grid = xtgeo.create_box_grid((3, 3, 1))

        # Deactivate the four lateral neighbors around the refined cell.
        actnum = grid.get_actnum()
        actnum.values[0, 1, 0] = 0
        actnum.values[2, 1, 0] = 0
        actnum.values[1, 0, 0] = 0
        actnum.values[1, 2, 0] = 0
        grid.set_actnum(actnum)

        region = xtgeo.GridProperty(grid, name="REGION", discrete=True, values=0)
        region.values[1, 1, 0] = 1

        nhg = NestedHybridGrid(coarse_grid=grid, region=region, refinement=(2, 2, 2))
        assert nhg.nnc_table.empty

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

    def test_fully_inactive_target_region_raises(self):
        """A target region with no active cells should raise a clear error."""
        grid = xtgeo.create_box_grid((3, 3, 1))

        region = xtgeo.GridProperty(grid, name="REGION", discrete=True, values=0)
        region.values[1, 1, 0] = 1
        region.values = np.ma.masked_array(region.values, mask=(region.values == 1))

        with pytest.raises(ValueError, match="No cells found for target_region_id=1"):
            NestedHybridGrid(coarse_grid=grid, region=region, refinement=(2, 2, 2))

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


# ---------------------------------------------------------------------------
# Tests for NestedHybridGrid.from_rms and .to_rms
# ---------------------------------------------------------------------------


class TestNestedHybridGridRmsIO:
    """Tests for from_rms and to_rms."""

    def test_from_rms_returns_nestedhybridgrid(self):
        """from_rms should return a NestedHybridGrid instance."""
        grid, region, _ = _make_box_grid_with_region(
            dimension=(6, 6, 2), target_layer_ids=[1], target_region_id=1
        )

        with (
            patch("xtgeo.grid_from_roxar", return_value=grid) as mock_grid,
            patch("xtgeo.gridproperty_from_roxar", return_value=region) as mock_prop,
        ):
            nhg = NestedHybridGrid.from_rms(
                project="mock_project",
                grid_name="Grid",
                region_name="REGION",
                refinement=(2, 2, 2),
            )

        assert isinstance(nhg, NestedHybridGrid)
        assert isinstance(nhg.grid, xtgeo.Grid)
        mock_grid.assert_called_once_with("mock_project", "Grid")
        mock_prop.assert_called_once_with("mock_project", "Grid", "REGION")

    def test_from_rms_refines_region_1_by_default(self):
        """from_rms currently uses default target_region_id=1."""
        grid, region, _ = _make_box_grid_with_region(
            dimension=(6, 6, 4), target_layer_ids=[0, 1], target_region_id=1
        )

        with (
            patch("xtgeo.grid_from_roxar", return_value=grid),
            patch("xtgeo.gridproperty_from_roxar", return_value=region),
        ):
            nhg = NestedHybridGrid.from_rms(
                project="mock_project",
                grid_name="Grid",
                region_name="REGION",
                refinement=(2, 2, 2),
            )

        # check that the refined bounding box is set correct from input region
        assert nhg._refined_bbox == BoundingBox.from_condition(region.values == 1)
        assert nhg._refined_bbox == BoundingBox(
            imin=4, imax=6, jmin=1, jmax=6, kmin=1, kmax=2
        )

        # check that bounding box for the refined region in the merged grid is correct
        output_region = nhg.grid.get_prop_by_name("REGION")
        assert BoundingBox.from_condition(output_region.values == 1) == BoundingBox(
            imin=8, imax=13, jmin=1, jmax=12, kmin=1, kmax=4
        )

    def test_from_rms_fails_if_no_region_1(self):
        """from_rms fails when no cells in the region have value 1."""
        grid, region, _ = _make_box_grid_with_region(
            dimension=(6, 6, 4), target_region_id=2
        )

        with (
            patch("xtgeo.grid_from_roxar", return_value=grid),
            patch("xtgeo.gridproperty_from_roxar", return_value=region),
            pytest.raises(ValueError, match="No cells found for target_region_id"),
        ):
            NestedHybridGrid.from_rms(
                project="mock_project",
                grid_name="Grid",
                region_name="REGION",
                refinement=(2, 2, 2),
            )

    def test_from_rms_no_properties_does_not_load_extras(self):
        """from_rms with properties=None should only load the region property."""
        grid, region, _ = _make_box_grid_with_region(
            dimension=(6, 6, 2), target_region_id=1
        )

        with (
            patch("xtgeo.grid_from_roxar", return_value=grid),
            patch("xtgeo.gridproperty_from_roxar", return_value=region) as mock_prop,
        ):
            NestedHybridGrid.from_rms(
                project="mock_project",
                grid_name="Grid",
                region_name="REGION",
                refinement=(2, 2, 2),
            )

        mock_prop.assert_called_once_with("mock_project", "Grid", "REGION")

    def test_from_rms_loads_optional_properties(self):
        """from_rms should load and append extra properties when provided."""
        grid, region, _ = _make_box_grid_with_region(
            dimension=(6, 6, 2), target_region_id=1
        )
        poro = _make_constant_property(grid, "PORO", 0.3)
        sw = _make_constant_property(grid, "SW", 0.8)

        with (
            patch("xtgeo.grid_from_roxar", return_value=grid),
            patch(
                "xtgeo.gridproperty_from_roxar", side_effect=[region, poro, sw]
            ) as mock_prop,
        ):
            nhg = NestedHybridGrid.from_rms(
                project="mock_project",
                grid_name="Grid",
                region_name="REGION",
                refinement=(2, 2, 2),
                properties=["PORO", "SW"],
            )

        assert mock_prop.call_count == 3
        mock_prop.assert_any_call("mock_project", "Grid", "REGION")
        mock_prop.assert_any_call("mock_project", "Grid", "PORO")
        mock_prop.assert_any_call("mock_project", "Grid", "SW")

        assert isinstance(nhg.grid, xtgeo.Grid)

        prop_names = {p.name for p in nhg.properties}
        assert prop_names == {
            "REGION",
            "PORO",
            "SW",
            *ORIGINAL_IJK_PROPERTY_NAMES,
        }

        for prop in nhg.properties:
            assert isinstance(prop, xtgeo.GridProperty)
            assert prop.dimensions == nhg.grid.dimensions

    def test_from_rms_accepts_properties_positionally(self):
        """properties must remain a positional argument (not keyword-only)."""
        grid, region, _ = _make_box_grid_with_region(dimension=(6, 6, 2))
        poro = _make_constant_property(grid, "PORO", 0.3)

        with (
            patch("xtgeo.grid_from_roxar", return_value=grid),
            patch("xtgeo.gridproperty_from_roxar", side_effect=[region, poro]),
        ):
            nhg = NestedHybridGrid.from_rms(
                "mock_project", "Grid", "REGION", (2, 2, 2), ["PORO"]
            )

        prop_names = {p.name for p in nhg.properties}
        assert prop_names == {"REGION", "PORO", *ORIGINAL_IJK_PROPERTY_NAMES}

    def test_from_rms_accepts_non_default_target_region_id(self):
        """from_rms should accept target_region_id as keyword argument."""
        grid, region, _ = _make_box_grid_with_region(
            dimension=(6, 6, 4), target_region_id=2
        )

        with (
            patch("xtgeo.grid_from_roxar", return_value=grid),
            patch("xtgeo.gridproperty_from_roxar", return_value=region),
        ):
            nhg = NestedHybridGrid.from_rms(
                project="mock_project",
                grid_name="Grid",
                region_name="REGION",
                refinement=(2, 2, 2),
                target_region_id=2,
            )

        # check that the refined bounding box is set correct from input region
        assert nhg._target_region_id == 2
        assert nhg._refined_bbox == BoundingBox.from_condition(region.values == 2)

    def test_to_rms_writes_grid_and_region_by_default(self):
        """to_rms should write the grid and region, but not parent indices."""

        grid, region, _ = _make_box_grid_with_region(dimension=(6, 6, 2))
        nhg = NestedHybridGrid(coarse_grid=grid, region=region, refinement=(2, 2, 2))

        with (
            patch.object(xtgeo.Grid, "to_roxar") as mock_grid_write,
            patch.object(xtgeo.GridProperty, "to_roxar") as mock_prop_write,
        ):
            nhg.to_rms("mock_project", "NestedGrid")

        mock_grid_write.assert_called_once_with("mock_project", "NestedGrid")
        mock_prop_write.assert_called_once_with("mock_project", "NestedGrid", "REGION")

    def test_to_rms_writes_each_property(self):
        """to_rms should export each non-parent-index property."""
        grid, region, _ = _make_box_grid_with_region(
            dimension=(6, 6, 2), target_region_id=1
        )
        poro = _make_constant_property(grid, "PORO", 0.3)
        grid.append_prop(poro)

        nhg = NestedHybridGrid(coarse_grid=grid, region=region, refinement=(2, 2, 2))

        with (
            patch.object(xtgeo.Grid, "to_roxar"),
            patch.object(xtgeo.GridProperty, "to_roxar") as mock_prop_write,
        ):
            nhg.to_rms("mock_project", "NestedGrid")

        exported_property_names = {
            mock_call.args[2] for mock_call in mock_prop_write.call_args_list
        }
        assert exported_property_names == {"REGION", "PORO"}
