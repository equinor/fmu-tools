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


def test_no_selectors():
    data = {
        "path": PATH,
        "grid": GRID,
        "properties": PROPERTIES,
        "verbosity": 1,
    }

    stat = qcp.get_grid_statistics(data, reuse=True)

    assert stat.property_dataframe["PORO"].mean() == pytest.approx(0.1677, abs=0.001)
    assert set(stat.property_dataframe.columns) == set(["PORO", "PERM"])
    assert set(stat.dataframe.columns) == set(
        ["Avg", "Stddev", "ID", "P90", "Min", "PROPERTY", "SOURCE", "Max", "P10"]
    )


def test_full_dataframe():
    data = {
        "path": PATH,
        "grid": GRID,
        "properties": PROPERTIES,
        "selectors": SELECTORS,
        "verbosity": 1,
    }

    stat = qcp.get_grid_statistics(data, reuse=True)

    assert stat.property_dataframe["PORO"].mean() == pytest.approx(0.1677, abs=0.001)
    assert stat.property_dataframe["PORO"].max() == pytest.approx(0.3613, abs=0.001)
    assert set(stat.property_dataframe.columns) == set(
        ["PORO", "PERM", "ZONE", "FACIES"]
    )


def multiple_filters():
    data = {
        "path": PATH,
        "grid": GRID,
        "properties": PROPERTIES,
        "multiple_filters": {
            "test1": {
                "reek_sim_facies2.roff": {
                    "include": ["SHALE"],
                }
            },
            "test2": {
                "reek_sim_facies2.roff": {
                    "exclude": ["SHALE"],
                }
            },
        },
        "verbosity": 1,
    }

    qcp.get_grid_statistics(data, reuse=True)

    assert qcp.dataframe[
        (qcp.dataframe["PROPERTY"] == "PORO") & (qcp.dataframe["ID"] == "test1")
    ].values == pytest.approx(0.1155, abs=0.001)


def test_statistics():
    data = {
        "path": PATH,
        "grid": GRID,
        "properties": PROPERTIES,
        "selectors": SELECTORS,
        "name": "Test_case",
        "verbosity": 1,
    }

    stat = qcp.get_grid_statistics(data, reuse=True)

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


def test_statistics_no_combos():
    data = {
        "verbosity": 1,
        "path": PATH,
        "grid": GRID,
        "properties": PROPERTIES,
        "selectors": SELECTORS,
        "selector_combos": False,
    }

    stat = qcp.get_grid_statistics(data, reuse=True)

    assert ["Total"] == list(
        stat.dataframe[stat.dataframe["ZONE"] == "Total"]["FACIES"].unique()
    )


def test_codenames():
    data_without_codes = {
        "verbosity": 1,
        "path": PATH,
        "grid": GRID,
        "properties": PROPERTIES,
        "selectors": SELECTORS,
    }

    stat_no_code = qcp.get_grid_statistics(data_without_codes, reuse=True)

    data_with_codes = {
        "verbosity": 1,
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

    stat = qcp.get_grid_statistics(data_with_codes, reuse=True)

    assert set(["TOP", "MID", "Below_Low_reek"]) == {
        x for x in list(stat.property_dataframe["ZONE"].unique()) if x is not None
    }

    assert set(["Below_Top_reek", "Below_Mid_reek", "Below_Low_reek"]) == {
        x
        for x in list(stat_no_code.property_dataframe["ZONE"].unique())
        if x is not None
    }
