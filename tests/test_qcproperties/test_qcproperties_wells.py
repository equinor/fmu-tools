# -*- coding: utf-8 -*-
"""Test code for RMS volumetrics parsing"""

from os.path import abspath
import pytest

from fmu.tools.qcproperties.qcproperties import QCProperties

PATH = abspath("../xtgeo-testdata/wells/reek/1/")
WELLS = ["OP_*.w"]
PROPERTIES = {
    "PORO": {"name": "Poro"},
    "PERM": {"name": "Perm"},
}
SELECTORS = {
    "ZONE": {"name": "Zonelog"},
    "FACIES": {"name": "Facies"},
}

qcp = QCProperties()


def test_full_dataframe():
    data = {
        "verbosity": 1,
        "path": PATH,
        "wells": WELLS,
        "properties": PROPERTIES,
        "selectors": SELECTORS,
    }

    stat = qcp.get_well_statistics(data, reuse=True)

    assert set(stat.property_dataframe.columns) == set(
        ["ZONE", "PERM", "PORO", "FACIES"]
    )
    assert stat.property_dataframe["PORO"].mean() == pytest.approx(0.1534, abs=0.001)


def test_filters():
    data = {
        "verbosity": 1,
        "path": PATH,
        "wells": WELLS,
        "properties": PROPERTIES,
        "selectors": {
            "ZONE": {
                "name": "Zonelog",
                "exclude": [
                    "Below_TopMidReek",
                    "Below_TopLowerReek",
                    "Below_BaseLowerReek",
                ],
            },
            "FACIES": {"name": "Facies", "include": ["Crevasse", "Channel"]},
        },
    }

    stat = qcp.get_well_statistics(data, reuse=True)

    assert set(["Crevasse", "Channel", "Total"]) == set(
        stat.dataframe["FACIES"].unique()
    )
    assert set(stat.dataframe["ZONE"].unique()) == set(
        ["Above_TopUpperReek", "Below_TopUpperReek", "Total"]
    )


def test_statistics():
    data = {
        "verbosity": 1,
        "path": PATH,
        "wells": WELLS,
        "properties": PROPERTIES,
        "selectors": SELECTORS,
        "name": "Raw_Logs",
    }

    stat = qcp.get_well_statistics(data, reuse=True)

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
