"""Tests for fmu.tools.nestedhybridgrid.nestedhybrid."""

import numpy as np
import pandas as pd
import pytest
import xtgeo

from fmu.tools.nestedhybridgrid import (
    create_nested_hybrid_grid,
    nnc_to_flowsimulator_input,
    nnc_to_gridproperty,
)
from fmu.tools.nestedhybridgrid.nestedhybrid import (
    _generate_layer_mappings,
)

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


def _upscale_test_setup():
    """Create grids and properties to test upscaling."""

    grid = xtgeo.create_box_grid((3, 3, 3), increment=(100.0, 100.0, 20.0))
    geogrid = xtgeo.create_box_grid((6, 6, 6), increment=(50.0, 50.0, 10.0))

    region = _make_constant_property(grid, "REGION", 1)
    region.values[1][1][1] = 2

    rid = 2

    il2 = (np.repeat(np.arange(3, dtype=np.float32), 3 * 3)).reshape((3, 3, 3)) + 1
    il2 = np.repeat(il2, 2, axis=0)
    il2 = np.repeat(il2, 2, axis=1)
    il2 = np.repeat(il2, 2, axis=2)
    ui = xtgeo.GridProperty(geogrid, name="UI", values=il2.astype(np.float32))

    jl2 = (
        np.swapaxes(
            (np.repeat(np.arange(3, dtype=np.float32), 3 * 3)).reshape((3, 3, 3)),
            0,
            1,
        )
        + 1
    )
    jl2 = np.repeat(jl2, 2, axis=0)
    jl2 = np.repeat(jl2, 2, axis=1)
    jl2 = np.repeat(jl2, 2, axis=2)
    uj = xtgeo.GridProperty(geogrid, name="UJ", values=jl2.astype(np.float32))

    kl2 = (
        np.swapaxes(
            (np.repeat(np.arange(3, dtype=np.float32), 3 * 3)).reshape((3, 3, 3)),
            0,
            2,
        )
        + 1
    )
    kl2 = np.repeat(kl2, 2, axis=0)
    kl2 = np.repeat(kl2, 2, axis=1)
    kl2 = np.repeat(kl2, 2, axis=2)
    uk = xtgeo.GridProperty(geogrid, name="UK", values=kl2.astype(np.float32))

    return (grid, region, rid, geogrid, ui, uj, uk)


# ---------------------------------------------------------------------------
# Tests for create_nested_hybrid_grid
# ---------------------------------------------------------------------------


class TestCreateNestedHybridGrid:
    """Tests for the create_nested_hybrid_grid function."""

    def test_returns_grid(self):
        """Function must return an xtgeo.Grid."""
        grid, region, rid = _make_box_grid_with_region(dimension=(6, 6, 2))
        merged, nnc_table, _ = create_nested_hybrid_grid(
            grid, region, rid, refinement=(1, 1, 1)
        )
        assert isinstance(merged, xtgeo.Grid)
        assert isinstance(nnc_table, pd.DataFrame)

    def test_basic_merge_dimensions(self):
        """Merged grid should have expected dimensions."""
        grid, region, rid = _make_box_grid_with_region(dimension=(6, 6, 2))
        merged, _, _ = create_nested_hybrid_grid(
            grid, region, rid, refinement=(1, 1, 1)
        )

        # grid_merge places grid2 with a 1-column gap:
        # ncol = grid1.ncol + 1 + grid2.ncol
        assert merged.ncol > grid.ncol
        assert merged.nrow >= grid.nrow
        assert merged.nlay >= grid.nlay

    def test_nest_id_property_attached(self):
        """The merged grid must have a refinement region property."""
        grid, region, rid = _make_box_grid_with_region(dimension=(6, 6, 2))
        merged, _, _ = create_nested_hybrid_grid(
            grid, region, rid, refinement=(1, 1, 1)
        )

        nest_id = merged.get_prop_by_name(region.name)
        assert nest_id is not None
        unique_vals = set(np.unique(np.ma.filled(nest_id.values, fill_value=0)))
        # Must contain at least mother (1) and refined (2) cells
        assert 1 in unique_vals
        assert 2 in unique_vals

    def test_nest_id_values_consistent(self):
        """Active cells should only have refinement region in {1, 2}."""
        grid, region, rid = _make_box_grid_with_region(dimension=(6, 6, 2))
        merged, _, _ = create_nested_hybrid_grid(
            grid, region, rid, refinement=(1, 1, 1)
        )

        nest_id = merged.get_prop_by_name(region.name)
        actnum = merged.get_actnum()

        active_mask = actnum.values == 1
        nest_active = np.ma.filled(nest_id.values, fill_value=0)[active_mask]
        assert set(np.unique(nest_active)).issubset({1, 2})

    def test_refinement_increases_cells(self):
        """Refinement > 1 should produce a merged grid with more total cells."""
        grid, region, rid = _make_box_grid_with_region(dimension=(6, 6, 2))
        merged_1x, _, _ = create_nested_hybrid_grid(
            grid, region, rid, refinement=(1, 1, 1)
        )
        merged_2x, _, _ = create_nested_hybrid_grid(
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

        _, _, _ = create_nested_hybrid_grid(grid, region, rid, refinement=(2, 2, 1))

        assert grid.ncol == orig_ncol
        assert grid.nactive == orig_nactive
        assert int(np.ma.filled(region.values, 0).sum()) == orig_region_sum

    def test_lmap_via_nnc(self):
        """Test correct lmaps generated indirectly via nnc_table.
        Cells in nnc_table for layer number completely controlled by lmap.
        """
        grid, region, rid = _make_box_grid_with_region(dimension=(3, 3, 3))

        region.values = np.ones(region.values.shape)
        region.values[1][1][1] = rid

        _, nnc_table, _ = create_nested_hybrid_grid(
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

    def test_lmap_generation_simple(self):
        """Tests that the correct layer mappings are generated"""

        lmap1, lmap2 = _generate_layer_mappings(3, 2, (2, 2, 2), (1, 1, 1))

        assert np.array_equal(lmap1, np.array([0, 1, 3]))
        assert np.array_equal(lmap2, np.array([1, 2]))

    def test_lmap_generation_no_offset(self):
        """Tests that the correct layer mappings are generated"""

        lmap1, lmap2 = _generate_layer_mappings(3, 4, (2, 2, 2), (1, 1, 0))

        assert np.array_equal(lmap1, np.array([0, 2, 4]))
        assert np.array_equal(lmap2, np.array([0, 1, 2, 3]))

    def test_lmap_generation_full_offset(self):
        """Tests that the correct layer mappings are generated"""

        lmap1, lmap2 = _generate_layer_mappings(3, 4, (2, 2, 2), (1, 1, 3))

        assert np.array_equal(lmap1, np.array([0, 1, 2]))
        assert np.array_equal(lmap2, np.array([3, 4, 5, 6]))

    def test_lmap_generation_ref10(self):
        """Tests that the correct layer mappings are generated"""

        lmap1, lmap2 = _generate_layer_mappings(3, 20, (2, 2, 10), (1, 1, 1))

        assert np.array_equal(lmap1, np.array([0, 1, 11]))
        assert np.array_equal(lmap2, np.arange(20) + 1)

    def test_upscaling_no_input(self):
        """test upscaling output is None for no input"""

        (grid, region, rid, geogrid, ui, uj, uk) = _upscale_test_setup()

        _, _, upscaled = create_nested_hybrid_grid(
            grid, region, rid, refinement=(2, 2, 2)
        )

        assert upscaled is None

    def test_upscaling_output(self):
        """test upscaling output mapping"""

        (grid, region, rid, geogrid, ui, uj, uk) = _upscale_test_setup()

        ui2 = ui.copy()
        uj2 = uj.copy()

        _, _, upscaled = create_nested_hybrid_grid(
            grid, region, rid, refinement=(2, 2, 2), upscaling=(ui, uj, uk)
        )

        upi, upj, upk = upscaled

        # test i,j,k==0 not modified
        assert np.array_equal(upi.values[0, :, :], ui2.values[0, :, :])
        assert np.array_equal(upi.values[:, 0, :], ui2.values[:, 0, :])
        assert np.array_equal(upi.values[:, :, 0], ui2.values[:, :, 0])
        assert np.array_equal(upj.values[0, :, :], uj2.values[0, :, :])
        assert np.array_equal(upj.values[:, 0, :], uj2.values[:, 0, :])
        assert np.array_equal(upj.values[:, :, 0], uj2.values[:, :, 0])
        # test i,j,k==-1 not modified
        assert np.array_equal(upi.values[-1, :, :], ui2.values[-1, :, :])
        assert np.array_equal(upi.values[:, -1, :], ui2.values[:, -1, :])
        assert np.array_equal(upi.values[:, :, -1], ui2.values[:, :, -1])
        assert np.array_equal(upj.values[-1, :, :], uj2.values[-1, :, :])
        assert np.array_equal(upj.values[:, -1, :], uj2.values[:, -1, :])
        assert np.array_equal(upj.values[:, :, -1], uj2.values[:, :, -1])
        # test layer modified in unrefined area
        kt = [1.0, 1.0, 2.0, 2.0, 4.0, 4.0]
        assert np.array_equal(upk.values[0, 0, :], np.array(kt))
        assert np.array_equal(upk.values[-1, -1, :], np.array(kt))
        # test refined area
        ti = [[5.0, 5.0], [5.0, 5.0]], [[6.0, 6.0], [6.0, 6.0]]
        tj = [[1.0, 1.0], [2.0, 2.0]], [[1.0, 1.0], [2.0, 2.0]]
        tk = [[2.0, 3.0], [2.0, 3.0]], [[2.0, 3.0], [2.0, 3.0]]
        assert np.array_equal(upi.values[2:4, 2:4, 2:4], np.array(ti))
        assert np.array_equal(upj.values[2:4, 2:4, 2:4], np.array(tj))
        assert np.array_equal(upk.values[2:4, 2:4, 2:4], np.array(tk))

    def test_upscaling_ranges_i_min(self):
        """test upscaling raises error if ui<0"""

        (grid, region, rid, geogrid, ui, uj, uk) = _upscale_test_setup()

        ui.values = ui.values - 2
        with pytest.raises(ValueError, match="Invalid input upscaling relationships"):
            create_nested_hybrid_grid(
                grid,
                region,
                rid,
                refinement=(2, 2, 2),
                upscaling=(ui, uj, uk),
            )

    def test_upscaling_ranges_i_max(self):
        """test upscaling raises error if ui>grid.ncol"""

        (grid, region, rid, geogrid, ui, uj, uk) = _upscale_test_setup()

        ui.values = ui.values + 2
        with pytest.raises(ValueError, match="Invalid input upscaling relationships"):
            create_nested_hybrid_grid(
                grid,
                region,
                rid,
                refinement=(2, 2, 2),
                upscaling=(ui, uj, uk),
            )

    def test_upscaling_ranges_j_min(self):
        """test upscaling raises error if uj<0"""

        (grid, region, rid, geogrid, ui, uj, uk) = _upscale_test_setup()

        uj.values = uj.values - 2
        with pytest.raises(ValueError, match="Invalid input upscaling relationships"):
            create_nested_hybrid_grid(
                grid,
                region,
                rid,
                refinement=(2, 2, 2),
                upscaling=(ui, uj, uk),
            )

    def test_upscaling_ranges_j_max(self):
        """test upscaling raises error if uj>grid.nrow"""

        (grid, region, rid, geogrid, ui, uj, uk) = _upscale_test_setup()

        uj.values = uj.values + 2
        with pytest.raises(ValueError, match="Invalid input upscaling relationships"):
            create_nested_hybrid_grid(
                grid,
                region,
                rid,
                refinement=(2, 2, 2),
                upscaling=(ui, uj, uk),
            )

    def test_upscaling_ranges_k_min(self):
        """test upscaling raises error if uk<0"""

        (grid, region, rid, geogrid, ui, uj, uk) = _upscale_test_setup()

        uk.values = uk.values - 2
        with pytest.raises(ValueError, match="Invalid input upscaling relationships"):
            create_nested_hybrid_grid(
                grid,
                region,
                rid,
                refinement=(2, 2, 2),
                upscaling=(ui, uj, uk),
            )

    def test_upscaling_ranges_k_max(self):
        """test upscaling raises error if uk>grid.nlay"""

        (grid, region, rid, geogrid, ui, uj, uk) = _upscale_test_setup()

        uk.values = uk.values + 2
        with pytest.raises(ValueError, match="Invalid input upscaling relationships"):
            create_nested_hybrid_grid(
                grid,
                region,
                rid,
                refinement=(2, 2, 2),
                upscaling=(ui, uj, uk),
            )

    def test_upscaling_ratio_i(self):
        """test upscaling for incompatible i ratio of geogrid to input grid"""

        (grid, region, rid, geogrid, ui, uj, uk) = _upscale_test_setup()

        with pytest.raises(
            ValueError,
            match="Invalid correspondence upscaling between geogrid and input grid",
        ):
            create_nested_hybrid_grid(
                grid,
                region,
                rid,
                refinement=(3, 2, 2),
                upscaling=(ui, uj, uk),
            )

    def test_upscaling_ratio_j(self):
        """test upscaling for incompatible j ratio of geogrid to input grid"""

        (grid, region, rid, geogrid, ui, uj, uk) = _upscale_test_setup()

        with pytest.raises(
            ValueError,
            match="Invalid correspondence upscaling between geogrid and input grid",
        ):
            create_nested_hybrid_grid(
                grid,
                region,
                rid,
                refinement=(2, 3, 2),
                upscaling=(ui, uj, uk),
            )

    def test_upscaling_ratio_k(self):
        """test upscaling for incompatible k ratio of geogrid to input grid"""

        (grid, region, rid, geogrid, ui, uj, uk) = _upscale_test_setup()

        with pytest.raises(
            ValueError,
            match="Invalid correspondence upscaling between geogrid and input grid",
        ):
            create_nested_hybrid_grid(
                grid,
                region,
                rid,
                refinement=(2, 2, 3),
                upscaling=(ui, uj, uk),
            )


# ---------------------------------------------------------------------------
# Tests for get_transmissibilities with nested hybrid NNCs
# ---------------------------------------------------------------------------


class TestTransmissibilitiesOnMergedGrid:
    """Test calling get_transmissibilities on the merged grid"""

    @staticmethod
    def _build_merged_with_props(dimension=(6, 6, 2), refinement=(1, 1, 1)):
        """Helper: build merged grid and attach constant perm/ntg properties."""
        grid, region, rid = _make_box_grid_with_region(dimension=dimension)
        merged, nnc_table, _ = create_nested_hybrid_grid(
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
