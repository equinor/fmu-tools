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

data_orig = {
    "path": PATH,
    "grid": GRID,
    "properties": PROPERTIES,
    "selectors": SELECTORS,
    "verbosity": 1,
}


def test_full_dataframe():
    data = data_orig.copy()

    qcp = QCProperties()
    stat = qcp.get_grid_statistics(data)

    assert stat.property_dataframe["PORO"].mean() == pytest.approx(0.1677, abs=0.001)
    assert stat.property_dataframe["PORO"].max() == pytest.approx(0.3613, abs=0.001)
    assert set(stat.property_dataframe.columns) == set(
        ["PORO", "PERM", "ZONE", "FACIES"]
    )


def test_no_selectors():
    data = data_orig.copy()
    data.pop("selectors", None)

    qcp = QCProperties()
    stat = qcp.get_grid_statistics(data)
    assert set(stat.property_dataframe.columns) == set(["PORO", "PERM"])


def test_statistics():
    data = data_orig.copy()
    data["name"] = "Test_case"

    qcp = QCProperties()
    stat = qcp.get_grid_statistics(data)

    assert set(stat.dataframe.columns) == set(
        [
            "Avg_Weighted",
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
    data = data_orig.copy()
    data["selector_combos"] = False

    qcp = QCProperties()
    stat = qcp.get_grid_statistics(data)

    assert ["Total"] == list(
        stat.dataframe[stat.dataframe["ZONE"] == "Total"]["FACIES"].unique()
    )


def test_codenames():
    data = data_orig.copy()

    qcp = QCProperties()
    stat_no_code = qcp.get_grid_statistics(data)

    data["selectors"] = {
        "ZONE": {"name": "reek_sim_zone.roff", "codes": {1: "TOP", 2: "MID"}},
        "FACIES": {
            "name": "reek_sim_facies2.roff",
        },
    }

    stat = qcp.get_grid_statistics(data, reuse=True)

    assert set(["TOP", "MID", "Below_Low_reek", "Total"]) == {
        x for x in list(stat.dataframe["ZONE"].unique()) if x is not None
    }
    assert set(["Below_Top_reek", "Below_Mid_reek", "Below_Low_reek", "Total"]) == {
        x for x in list(stat_no_code.dataframe["ZONE"].unique()) if x is not None
    }


def test_extract_statistics_update_filter_parameter():
    """Test changing filters after initialization"""
    data = data_orig.copy()
    data["selectors"] = ["reek_sim_zone.roff"]

    qcp = QCProperties()
    stat = qcp.get_grid_statistics(data)

    assert stat.property_dataframe["PORO"].mean() == pytest.approx(0.1677, abs=0.001)
    assert set(stat.property_dataframe.columns) == set(
        [
            "PORO",
            "PERM",
            "reek_sim_zone.roff",
        ]
    )
    stat.extract_statistics(
        filters={
            "reek_sim_facies2.roff": {
                "include": ["FINESAND", "COARSESAND"],
            }
        },
    )

    assert set(stat.property_dataframe.columns) == set(
        [
            "PORO",
            "PERM",
            "reek_sim_facies2.roff",
            "reek_sim_zone.roff",
        ]
    )
    assert ["FINESAND", "COARSESAND"] == list(
        stat.property_dataframe["reek_sim_facies2.roff"].unique()
    )
    assert stat.property_dataframe["PORO"].mean() == pytest.approx(0.2374, abs=0.001)


def test_extract_statistics_update_filter_values():
    """Test changing filters after initialization"""
    data = data_orig.copy()
    data["selectors"] = {
        "ZONE": {"name": "reek_sim_zone.roff", "exclude": ["Below_Top_reek"]},
        "FACIES": {
            "name": "reek_sim_facies2.roff",
            "include": ["FINESAND", "COARSESAND"],
        },
    }
    data["filters"] = {
        "reek_sim_facies2.roff": {
            "include": ["FINESAND", "COARSESAND"],
        }
    }

    qcp = QCProperties()
    stat = qcp.get_grid_statistics(data)

    assert "Below_Top_reek" not in list(stat.property_dataframe["ZONE"].unique())
    assert ["FINESAND", "COARSESAND"] == list(
        stat.property_dataframe["FACIES"].unique()
    )
    assert stat.property_dataframe["PORO"].mean() == pytest.approx(0.2390, abs=0.001)

    stat.extract_statistics(
        filters={
            "reek_sim_facies2.roff": {
                "include": ["SHALE"],
            }
        }
    )
    assert "Below_Top_reek" not in list(stat.property_dataframe["ZONE"].unique())
    assert ["SHALE"] == list(stat.property_dataframe["FACIES"].unique())
    assert stat.property_dataframe["PORO"].mean() == pytest.approx(0.1155, abs=0.001)


def test_get_value():
    data = data_orig.copy()

    qcp = QCProperties()
    stat = qcp.get_grid_statistics(data)

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


def test_multiple_filters():
    data = data_orig.copy()
    data.pop("selectors", None)
    data["multiple_filters"] = {
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
    }
    qcp = QCProperties()
    qcp.get_grid_statistics(data)

    assert set(["test1", "test2"]) == set(qcp.dataframe["ID"].unique())
    assert qcp.dataframe[
        (qcp.dataframe["PROPERTY"] == "PORO") & (qcp.dataframe["ID"] == "test1")
    ]["Avg"].values == pytest.approx(0.1183, abs=0.001)


def test_read_eclipse():
    data = data_orig.copy()
    data["grid"] = "REEK.EGRID"
    data["properties"] = {
        "PORO": {"name": "PORO", "pfile": "REEK.INIT"},
        "PERM": {"name": "PERMX", "pfile": "REEK.INIT"},
    }
    data["selectors"] = {
        "REGION": {"name": "FIPNUM", "pfile": "REEK.INIT"},
    }

    qcp = QCProperties()
    qcp.get_grid_statistics(data)

    assert set(["REEK"]) == set(qcp.dataframe["ID"].unique())
    assert qcp.dataframe[
        (qcp.dataframe["PROPERTY"] == "PORO") & (qcp.dataframe["REGION"] == "2")
    ]["Avg"].values == pytest.approx(0.1661, abs=0.001)
