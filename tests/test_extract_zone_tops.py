from os.path import abspath

import pytest

from fmu.tools import extract_grid_zone_tops

GRID_PATH = "3dgrids/reek/reek_sim_grid.roff"
GRIDPROP_PATH = "3dgrids/reek/reek_sim_zone.roff"
WELLS = [abspath("tests/data/zone_tops_from_grid/OP_1.w")]


def test_extract_no_md_log(testdata_path):
    grid_path = abspath(testdata_path / GRID_PATH)
    gridprop_path = abspath(testdata_path / GRIDPROP_PATH)
    dframe = extract_grid_zone_tops(
        well_list=WELLS, grid=grid_path, zone_param=gridprop_path
    )
    assert set(dframe["ZONE"].unique()) == {
        "Below_Top_reek",
        "Below_Mid_reek",
        "Below_Low_reek",
    }
    assert dframe["TOP_TVD"].min() == pytest.approx(1595.02, abs=0.1)
    assert dframe["BASE_TVD"].max() == pytest.approx(1644.67, abs=0.1)
    assert dframe["TOP_MD"].min() == pytest.approx(2378.33, abs=0.1)
    assert dframe["BASE_MD"].max() == pytest.approx(2427.98, abs=0.1)


def test_extract_with_dummy_md_log(testdata_path):
    grid_path = abspath(testdata_path / GRID_PATH)
    gridprop_path = abspath(testdata_path / GRIDPROP_PATH)
    dframe = extract_grid_zone_tops(
        well_list=WELLS, grid=grid_path, zone_param=gridprop_path, mdlogname="MDLog"
    )
    assert set(dframe["ZONE"].unique()) == {
        "Below_Top_reek",
        "Below_Mid_reek",
        "Below_Low_reek",
    }
    assert dframe["TOP_TVD"].min() == pytest.approx(1595.02, abs=0.1)
    assert dframe["BASE_TVD"].max() == pytest.approx(1644.67, abs=0.1)
    assert dframe["TOP_MD"].min() == pytest.approx(2388.33, abs=0.1)
    assert dframe["BASE_MD"].max() == pytest.approx(2437.98, abs=0.1)


def test_extract_grid_zone_log():
    dframe = extract_grid_zone_tops(well_list=WELLS, gridzonelog="grid_zones")
    assert set(dframe["ZONE"].unique()) == {
        "Below_Top_reek",
        "Below_Mid_reek",
        "Below_Low_reek",
    }
    assert dframe["TOP_TVD"].min() == pytest.approx(1595.74, abs=0.1)
    assert dframe["BASE_TVD"].max() == pytest.approx(1644.67, abs=0.1)
    assert dframe["TOP_MD"].min() == pytest.approx(2379.06, abs=0.1)
    assert dframe["BASE_MD"].max() == pytest.approx(2427.98, abs=0.1)
