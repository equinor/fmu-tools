from os.path import abspath
import pytest

from fmu.tools.qcproperties.qcproperties import QCProperties

PATH = abspath("../xtgeo-testdata/3dgrids/reek/")
GRID = "reek_sim_grid.roff"
PROPERTIES = {
    "PORO": {"name": "reek_sim_poro.roff"},
    "PERM": {"name": "reek_sim_permx.roff"},
}
SELECTORS = {
    "ZONE": {"name": "reek_sim_zone.roff"},
    "FACIES": {"name": "reek_sim_facies2.roff"},
}


qcp = QCProperties()


def test_full_dataframe():
    data = {
        "path": PATH,
        "grid": GRID,
        "properties": PROPERTIES,
        "selectors": SELECTORS,
    }

    stat = qcp.get_grid_statistics(data)

    assert stat.property_dataframe["PORO"].mean() == pytest.approx(0.1677, abs=0.001)
    assert stat.property_dataframe["PORO"].max() == pytest.approx(0.3613, abs=0.001)
    assert set(stat.property_dataframe.columns) == set(
        ["PORO", "PERM", "ZONE", "FACIES"]
    )


def test_statistics():
    data = {
        "path": PATH,
        "grid": GRID,
        "properties": PROPERTIES,
        "selectors": SELECTORS,
        "name": "Test_case",
    }

    stat = qcp.get_grid_statistics(data, reuse=["grid"])

    assert set(stat.dataframe.columns) == set(
        [
            "Avg",
            "FACIES",
            "Max",
            "Min",
            "P10",
            "P90",
            "PROPERTY",
            "Stddev",
            "ZONE",
            "SOURCE",
            "ID",
        ]
    )
    assert list(stat.dataframe["ID"].unique())[0] == data["name"]
    assert set(stat.dataframe["PROPERTY"].unique()) == set(["PORO", "PERM"])
    assert stat.dataframe[stat.dataframe["PROPERTY"] == "PORO"][
        "Avg"
    ].max() == pytest.approx(0.3138, abs=0.001)

    row = stat.dataframe[
        (stat.dataframe["ZONE"] == "Total")
        & (stat.dataframe["FACIES"] == "Total")
        & (stat.dataframe["PROPERTY"] == "PORO")
    ]
    assert row["Avg"].values == pytest.approx(0.1677, abs=0.001)


def test_no_selectors():
    data = {
        "path": PATH,
        "grid": GRID,
        "properties": PROPERTIES,
    }

    stat = qcp.get_grid_statistics(data, reuse=["grid"])

    assert stat.property_dataframe["PORO"].mean() == pytest.approx(0.1677, abs=0.001)
    assert set(stat.property_dataframe.columns) == set(["PORO", "PERM"])
    assert set(stat.dataframe.columns) == set(
        ["Avg", "Stddev", "ID", "P90", "Min", "PROPERTY", "SOURCE", "Max", "P10"]
    )


def test_filters():
    data = {
        "path": PATH,
        "grid": GRID,
        "properties": PROPERTIES,
        "selectors": {
            "ZONE": {"name": "reek_sim_zone.roff", "exclude": ["Below_Top_reek"]},
            "FACIES": {
                "name": "reek_sim_facies2.roff",
                "include": ["FINESAND", "COARSESAND"],
            },
        },
    }

    stat = qcp.get_grid_statistics(data, reuse=["grid"])

    assert "Below_Top_reek" not in list(stat.property_dataframe["ZONE"].unique())
    assert ["FINESAND", "COARSESAND"] == list(
        stat.property_dataframe["FACIES"].unique()
    )
    assert stat.property_dataframe["PORO"].mean() == pytest.approx(0.2390, abs=0.001)

    print(stat.codes)


def test_statistics_no_combos():
    data = {
        "path": PATH,
        "grid": GRID,
        "properties": PROPERTIES,
        "selectors": SELECTORS,
        "selector_combos": False,
    }

    stat = qcp.get_grid_statistics(data, reuse=["grid"])

    assert ["Total"] == list(
        stat.dataframe[stat.dataframe["ZONE"] == "Total"]["FACIES"].unique()
    )


def test_statistics_all_combos():
    data = {
        "path": PATH,
        "grid": GRID,
        "properties": PROPERTIES,
        "selectors": SELECTORS,
        "selector_combos": True,
    }

    stat = qcp.get_grid_statistics(data, reuse=["grid"])

    assert ["COARSESAND", "FINESAND", "SHALE", "Total"] == list(
        stat.dataframe[stat.dataframe["ZONE"] == "Total"]["FACIES"].unique()
    )


def test_codenames():
    data_without_codes = {
        "path": PATH,
        "grid": GRID,
        "properties": PROPERTIES,
        "selectors": SELECTORS,
    }

    stat_no_code = qcp.get_grid_statistics(data_without_codes, reuse=["grid"])

    data_with_codes = {
        "path": PATH,
        "grid": GRID,
        "properties": PROPERTIES,
        "selectors": {
            "ZONE": {"name": "reek_sim_zone.roff", "codes": {1: "TOP", 2: "MID"}},
            "FACIES": {
                "name": "reek_sim_facies2.roff",
            },
        },
    }

    stat = qcp.get_grid_statistics(data_with_codes, reuse=["grid"])

    assert set(["TOP", "MID", "Below_Low_reek"]) == {
        x for x in list(stat.property_dataframe["ZONE"].unique()) if x is not None
    }

    assert set(["Below_Top_reek", "Below_Mid_reek", "Below_Low_reek"]) == {
        x
        for x in list(stat_no_code.property_dataframe["ZONE"].unique())
        if x is not None
    }


def test_get_value():
    data = {
        "path": PATH,
        "grid": GRID,
        "properties": PROPERTIES,
        "selectors": SELECTORS,
    }

    stat = qcp.get_grid_statistics(data, reuse=["grid"])

    assert stat.get_value("PORO") == pytest.approx(0.1677, abs=0.001)
    assert stat.get_value("PORO", calculation="Max") == pytest.approx(0.3613, abs=0.001)

    conditions = {"ZONE": "Below_Top_reek", "FACIES": "COARSESAND"}
    assert stat.get_value("PORO", conditions=conditions) == pytest.approx(
        0.3117, abs=0.001
    )
    conditions = {"ZONE": "Below_Top_reek"}

    assert stat.get_value("PORO", conditions=conditions) == pytest.approx(
        0.1595, abs=0.001
    )
