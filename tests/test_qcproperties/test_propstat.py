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


def test_extract_statistics_update_filter_parameter():
    """Test changing filters after initialization"""

    data = {
        "verbosity": 1,
        "path": PATH,
        "grid": GRID,
        "properties": PROPERTIES,
        "selectors": ["reek_sim_zone.roff"],
    }

    stat = qcp.get_grid_statistics(data, reuse=True)

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

    data = {
        "verbosity": 1,
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
        "filters": {
            "reek_sim_facies2.roff": {
                "include": ["FINESAND", "COARSESAND"],
            }
        },
    }

    stat = qcp.get_grid_statistics(data, reuse=True)

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
    data = {
        "verbosity": 1,
        "path": PATH,
        "grid": GRID,
        "properties": PROPERTIES,
        "selectors": SELECTORS,
    }

    stat = qcp.get_grid_statistics(data, reuse=True)

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
