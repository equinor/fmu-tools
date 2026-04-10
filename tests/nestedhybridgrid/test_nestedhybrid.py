"""Tests for fmu.tools.nestedhybridgrid.nestedhybrid."""

import numpy as np
import pandas as pd
import pytest
import xtgeo

from fmu.tools.nestedhybridgrid import create_nested_hybrid_grid


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


# ---------------------------------------------------------------------------
# Tests for create_nested_hybrid_grid
# ---------------------------------------------------------------------------


class TestCreateNestedHybridGrid:
    """Tests for the create_nested_hybrid_grid function."""

    def test_returns_grid(self):
        """Function must return an xtgeo.Grid."""
        grid, region, rid = _make_box_grid_with_region(dimension=(6, 6, 2))
        merged = create_nested_hybrid_grid(grid, region, rid, refinement=(1, 1, 1))
        assert isinstance(merged, xtgeo.Grid)

    def test_basic_merge_dimensions(self):
        """Merged grid should have expected dimensions."""
        grid, region, rid = _make_box_grid_with_region(dimension=(6, 6, 2))
        merged = create_nested_hybrid_grid(grid, region, rid, refinement=(1, 1, 1))

        # grid_merge places grid2 with a 1-column gap:
        # ncol = grid1.ncol + 1 + grid2.ncol
        assert merged.ncol > grid.ncol
        assert merged.nrow >= grid.nrow
        assert merged.nlay >= grid.nlay

    def test_nest_id_property_attached(self):
        """The merged grid must have a NEST_ID property."""
        grid, region, rid = _make_box_grid_with_region(dimension=(6, 6, 2))
        merged = create_nested_hybrid_grid(grid, region, rid, refinement=(1, 1, 1))

        nest_id = merged.get_prop_by_name("NEST_ID")
        assert nest_id is not None
        unique_vals = set(np.unique(np.ma.filled(nest_id.values, fill_value=0)))
        # Must contain at least mother (1) and refined (2) cells
        assert 1 in unique_vals
        assert 2 in unique_vals

    def test_nest_id_values_consistent(self):
        """Active cells should only have NEST_ID in {1, 2}."""
        grid, region, rid = _make_box_grid_with_region(dimension=(6, 6, 2))
        merged = create_nested_hybrid_grid(grid, region, rid, refinement=(1, 1, 1))

        nest_id = merged.get_prop_by_name("NEST_ID")
        actnum = merged.get_actnum()

        active_mask = actnum.values == 1
        nest_active = np.ma.filled(nest_id.values, fill_value=0)[active_mask]
        assert set(np.unique(nest_active)).issubset({1, 2})

    def test_refinement_increases_cells(self):
        """Refinement > 1 should produce a merged grid with more total cells."""
        grid, region, rid = _make_box_grid_with_region(dimension=(6, 6, 2))
        merged_1x = create_nested_hybrid_grid(grid, region, rid, refinement=(1, 1, 1))
        merged_2x = create_nested_hybrid_grid(grid, region, rid, refinement=(2, 2, 2))
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

        create_nested_hybrid_grid(grid, region, rid, refinement=(2, 2, 1))

        assert grid.ncol == orig_ncol
        assert grid.nactive == orig_nactive
        assert int(np.ma.filled(region.values, 0).sum()) == orig_region_sum


# ---------------------------------------------------------------------------
# Tests for get_transmissibilities with nested hybrid NNCs
# ---------------------------------------------------------------------------


class TestTransmissibilitiesOnMergedGrid:
    """Test calling get_transmissibilities on the merged grid with NEST_ID."""

    @staticmethod
    def _build_merged_with_props(dimension=(6, 6, 2), refinement=(1, 1, 1)):
        """Helper: build merged grid and attach constant perm/ntg properties."""
        grid, region, rid = _make_box_grid_with_region(dimension=dimension)
        merged = create_nested_hybrid_grid(grid, region, rid, refinement=refinement)

        permx = _make_constant_property(merged, "PERMX", 100.0)
        permy = _make_constant_property(merged, "PERMY", 100.0)
        permz = _make_constant_property(merged, "PERMZ", 10.0)
        ntg = _make_constant_property(merged, "NTG", 1.0)
        return merged, permx, permy, permz, ntg

    def test_transmissibilities_return_types(self):
        """get_transmissibilities should return the expected types."""
        merged, permx, permy, permz, ntg = self._build_merged_with_props()
        nest_id = merged.get_prop_by_name("NEST_ID")

        tranx, trany, tranz, nnc, nnc_nh, rbnd = merged.get_transmissibilities(
            permx=permx, permy=permy, permz=permz, ntg=ntg,
            nested_id_property=nest_id,
        )
        assert isinstance(tranx, xtgeo.GridProperty)
        assert isinstance(trany, xtgeo.GridProperty)
        assert isinstance(tranz, xtgeo.GridProperty)
        assert isinstance(nnc, pd.DataFrame)
        assert nnc_nh is None or isinstance(nnc_nh, pd.DataFrame)
        assert rbnd is None or isinstance(rbnd, xtgeo.GridProperty)

    def test_transmissibilities_positive(self):
        """Transmissibility values should be non-negative for a uniform grid."""
        merged, permx, permy, permz, ntg = self._build_merged_with_props()
        nest_id = merged.get_prop_by_name("NEST_ID")

        tranx, trany, tranz, *_ = merged.get_transmissibilities(
            permx=permx, permy=permy, permz=permz, ntg=ntg,
            nested_id_property=nest_id,
        )
        for tprop in (tranx, trany, tranz):
            vals = np.ma.filled(tprop.values, fill_value=0.0)
            assert np.all(vals >= 0.0)

    def test_nnc_dataframe_has_expected_columns(self):
        """The NNC DataFrame should have the standard columns."""
        merged, permx, permy, permz, ntg = self._build_merged_with_props()
        nest_id = merged.get_prop_by_name("NEST_ID")

        _, _, _, nnc, *_ = merged.get_transmissibilities(
            permx=permx, permy=permy, permz=permz, ntg=ntg,
            nested_id_property=nest_id,
        )
        expected = {"I1", "J1", "K1", "I2", "J2", "K2", "T", "TYPE"}
        assert expected.issubset(set(nnc.columns))

    def test_without_nested_id(self):
        """get_transmissibilities without nested_id_property should still work."""
        merged, permx, permy, permz, ntg = self._build_merged_with_props()

        tranx, trany, tranz, nnc, nnc_nh, rbnd = merged.get_transmissibilities(
            permx=permx, permy=permy, permz=permz, ntg=ntg,
        )
        assert isinstance(tranx, xtgeo.GridProperty)
        assert nnc_nh is None
        assert rbnd is None
