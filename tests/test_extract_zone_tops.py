from os.path import abspath
import pytest

from fmu.tools import extract_grid_zone_tops


GRID = abspath("../xtgeo-testdata/3dgrids/reek/reek_sim_grid.roff")
GRIDPROP = abspath("../xtgeo-testdata/3dgrids/reek/reek_sim_zone.roff")
WELLS = [abspath("tests/data/zone_tops_from_grid/OP_1.w")]


def test_extract_no_md_log():
    dframe = extract_grid_zone_tops(well_list=WELLS, grid=GRID, zone_param=GRIDPROP)
    assert set(dframe["ZONE"].unique()) == set(
        ["Below_Top_reek", "Below_Mid_reek", "Below_Low_reek"]
    )
    print(dframe)
    assert dframe["TOP_TVD"].min() == pytest.approx(1595.02, abs=0.1)
    assert dframe["BASE_TVD"].max() == pytest.approx(1644.67, abs=0.1)
    assert dframe["TOP_MD"].min() == pytest.approx(2378.33, abs=0.1)
    assert dframe["BASE_MD"].max() == pytest.approx(2427.98, abs=0.1)


def test_extract_with_dummy_md_log():
    dframe = extract_grid_zone_tops(
        well_list=WELLS, grid=GRID, zone_param=GRIDPROP, mdlogname="MDLog"
    )
    assert set(dframe["ZONE"].unique()) == set(
        ["Below_Top_reek", "Below_Mid_reek", "Below_Low_reek"]
    )
    assert dframe["TOP_TVD"].min() == pytest.approx(1595.02, abs=0.1)
    assert dframe["BASE_TVD"].max() == pytest.approx(1644.67, abs=0.1)
    assert dframe["TOP_MD"].min() == pytest.approx(2388.33, abs=0.1)
    assert dframe["BASE_MD"].max() == pytest.approx(2437.98, abs=0.1)


def test_extract_grid_zone_log():
    dframe = extract_grid_zone_tops(well_list=WELLS, gridzonelog="grid_zones")
    print(dframe)
    assert set(dframe["ZONE"].unique()) == set(
        ["Below_Top_reek", "Below_Mid_reek", "Below_Low_reek"]
    )
    assert dframe["TOP_TVD"].min() == pytest.approx(1595.74, abs=0.1)
    assert dframe["BASE_TVD"].max() == pytest.approx(1644.67, abs=0.1)
    assert dframe["TOP_MD"].min() == pytest.approx(2379.06, abs=0.1)
    assert dframe["BASE_MD"].max() == pytest.approx(2427.98, abs=0.1)
