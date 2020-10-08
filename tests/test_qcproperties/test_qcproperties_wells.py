# -*- coding: utf-8 -*-
"""Test code for RMS volumetrics parsing"""

from os.path import abspath
import pytest

from fmu.tools.qcproperties.qcproperties import QCProperties

PATH = abspath("../xtgeo-testdata/wells/reek/1/")
WELLS = ["OP_*.w"]
BWELLS = ["OP_1.bw"]
PROPERTIES = {
    "PORO": {"name": "Poro"},
    "PERM": {"name": "Perm"},
}
SELECTORS = {
    "ZONE": {"name": "Zonelog"},
    "FACIES": {"name": "Facies"},
}

data_orig_wells = {
    "verbosity": 1,
    "path": PATH,
    "wells": WELLS,
    "properties": PROPERTIES,
    "selectors": SELECTORS,
}

data_orig_bwells = {
    "verbosity": 1,
    "path": PATH,
    "wells": BWELLS,
    "properties": {
        "PORO": {"name": "Poro"},
    },
    "selectors": {
        "FACIES": {"name": "Facies"},
    },
}


def test_full_dataframe_wells():
    data = data_orig_wells.copy()

    qcp = QCProperties()
    stat = qcp.get_well_statistics(data)

    assert set(stat.property_dataframe.columns) == set(
        ["ZONE", "PERM", "PORO", "FACIES"]
    )
    assert stat.property_dataframe["PORO"].mean() == pytest.approx(0.1534, abs=0.001)


def test_filters_wells():
    data = data_orig_wells.copy()
    data["selectors"] = {
        "ZONE": {
            "name": "Zonelog",
            "exclude": [
                "Below_TopMidReek",
                "Below_TopLowerReek",
                "Below_BaseLowerReek",
            ],
        },
        "FACIES": {"name": "Facies", "include": ["Crevasse", "Channel"]},
    }
    qcp = QCProperties()
    stat = qcp.get_well_statistics(data)

    assert set(["Crevasse", "Channel", "Total"]) == set(
        stat.dataframe["FACIES"].unique()
    )
    assert set(stat.dataframe["ZONE"].unique()) == set(
        ["Above_TopUpperReek", "Below_TopUpperReek", "Total"]
    )


def test_statistics_wells():
    data = data_orig_wells.copy()
    data["name"] = "Raw_Logs"

    qcp = QCProperties()
    stat = qcp.get_well_statistics(data)
    stat = qcp.get_well_statistics(data)
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
    assert list(stat.dataframe["ID"].unique())[0] == "Raw_Logs"
    assert set(stat.dataframe["PROPERTY"].unique()) == set(["PORO", "PERM"])
    assert stat.dataframe[stat.dataframe["PROPERTY"] == "PORO"][
        "Avg"
    ].max() == pytest.approx(0.3059, abs=0.001)
    assert set(stat.dataframe["ZONE"].unique()) == set(
        [
            "Above_TopUpperReek",
            "Below_TopLowerReek",
            "Below_TopMidReek",
            "Below_TopUpperReek",
            "Below_BaseLowerReek",
            "Total",
        ]
    )

    row = stat.dataframe[
        (stat.dataframe["ZONE"] == "Total")
        & (stat.dataframe["FACIES"] == "Total")
        & (stat.dataframe["PROPERTY"] == "PORO")
    ]
    assert row["Avg"].values == pytest.approx(0.1539, abs=0.001)


def test_full_dataframe_bwells():
    data = data_orig_bwells.copy()
    data["wells"] = BWELLS

    qcp = QCProperties()
    stat = qcp.get_bwell_statistics(data, reuse=True)

    assert set(stat.property_dataframe.columns) == set(["PORO", "FACIES"])
    assert stat.property_dataframe["PORO"].mean() == pytest.approx(0.1709, abs=0.001)


def test_filters_bwells():
    data = data_orig_bwells.copy()
    data["wells"] = BWELLS
    data["selectors"] = {
        "FACIES": {"name": "Facies", "include": "Channel"},
    }
    qcp = QCProperties()
    stat = qcp.get_bwell_statistics(data, reuse=True)

    assert set(["Channel", "Total"]) == set(stat.dataframe["FACIES"].unique())


def test_statistics_bwells():
    data = data_orig_bwells.copy()
    data["wells"] = BWELLS
    data["name"] = "Blocked_Logs"

    qcp = QCProperties()
    stat = qcp.get_bwell_statistics(data, reuse=True)

    assert set(stat.dataframe.columns) == set(
        [
            "Avg",
            "Avg_Weighted",
            "FACIES",
            "Max",
            "Min",
            "P10",
            "P90",
            "PROPERTY",
            "Stddev",
            "SOURCE",
            "ID",
        ]
    )
    assert list(stat.dataframe["ID"].unique())[0] == "Blocked_Logs"
    assert set(stat.dataframe["PROPERTY"].unique()) == set(["PORO"])
    assert stat.dataframe[stat.dataframe["PROPERTY"] == "PORO"][
        "Avg"
    ].max() == pytest.approx(0.2678, abs=0.001)

    row = stat.dataframe[
        (stat.dataframe["FACIES"] == "Total") & (stat.dataframe["PROPERTY"] == "PORO")
    ]
    assert row["Avg"].values == pytest.approx(0.1709, abs=0.001)
