import os

import pytest

from fmu.tools.qcforward.extract_grid_zone_tops import extract_grid_zone_tops


if "__file__" in globals():
    # Easen up copying test code into interactive sessions
    testdir = os.path.dirname(os.path.abspath(__file__))
else:
    testdir = os.path.abspath(".")


GRID = os.path.join(testdir, "data/reek_sim_grid.roff")
GRIDPROP = os.path.join(testdir, "data/reek_sim_zone.roff")
WELLS = [os.path.join(testdir, "data/OP_1.w")]


def test_extract_no_md_log():
    df = extract_grid_zone_tops(well_list=WELLS, grid=GRID, zone_param=GRIDPROP)
    assert set(df["ZONE"].unique()) == set(
        ["Below_Top_reek", "Below_Mid_reek", "Below_Low_reek"]
    )
    print(df)
    assert df["TOP_TVD"].min() == pytest.approx(1595.02, abs=0.1)
    assert df["BASE_TVD"].max() == pytest.approx(1644.67, abs=0.1)
    assert df["TOP_MD"].min() == pytest.approx(2378.33, abs=0.1)
    assert df["BASE_MD"].max() == pytest.approx(2427.98, abs=0.1)


def test_extract_with_dummy_md_log():
    df = extract_grid_zone_tops(
        well_list=WELLS, grid=GRID, zone_param=GRIDPROP, mdlogname="MDLog"
    )
    assert set(df["ZONE"].unique()) == set(
        ["Below_Top_reek", "Below_Mid_reek", "Below_Low_reek"]
    )
    assert df["TOP_TVD"].min() == pytest.approx(1595.02, abs=0.1)
    assert df["BASE_TVD"].max() == pytest.approx(1644.67, abs=0.1)
    assert df["TOP_MD"].min() == pytest.approx(2388.33, abs=0.1)
    assert df["BASE_MD"].max() == pytest.approx(2437.98, abs=0.1)


def test_extract_grid_zone_log():
    df = extract_grid_zone_tops(well_list=WELLS, gridzonelog="grid_zones")
    print(df)
    assert set(df["ZONE"].unique()) == set(
        ["Below_Top_reek", "Below_Mid_reek", "Below_Low_reek"]
    )
    assert df["TOP_TVD"].min() == pytest.approx(1595.74, abs=0.1)
    assert df["BASE_TVD"].max() == pytest.approx(1644.67, abs=0.1)
    assert df["TOP_MD"].min() == pytest.approx(2379.06, abs=0.1)
    assert df["BASE_MD"].max() == pytest.approx(2427.98, abs=0.1)
