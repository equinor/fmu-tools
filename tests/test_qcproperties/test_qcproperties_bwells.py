# -*- coding: utf-8 -*-
"""Test code for RMS volumetrics parsing"""
from os.path import abspath
import pytest
from fmu.tools.qcproperties.qcproperties import QCProperties

PATH = abspath("../xtgeo-testdata/wells/reek/1/")
WELLS = ["OP_1.bw"]
PROPERTIES = {
    "PORO": {"name": "Poro"},
}
SELECTORS = {
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

    stat = qcp.get_bwell_statistics(data, reuse=True)

    assert set(stat.property_dataframe.columns) == set(["PORO", "FACIES"])
    assert stat.property_dataframe["PORO"].mean() == pytest.approx(0.1709, abs=0.001)


def test_filters():
    data = {
        "verbosity": 1,
        "path": PATH,
        "wells": WELLS,
        "properties": PROPERTIES,
        "selectors": {
            "FACIES": {"name": "Facies", "include": "Channel"},
        },
    }

    stat = qcp.get_bwell_statistics(data, reuse=True)

    assert set(["Channel", "Total"]) == set(stat.dataframe["FACIES"].unique())


def test_statistics():

    data = {
        "verbosity": 1,
        "path": PATH,
        "wells": WELLS,
        "properties": PROPERTIES,
        "selectors": SELECTORS,
        "name": "Blocked_Logs",
    }
    stat = qcp.get_bwell_statistics(data, reuse=True)

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
