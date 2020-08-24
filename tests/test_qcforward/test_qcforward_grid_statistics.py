import pathlib
from os.path import abspath
import pytest
import pandas as pd

from fmu.tools import qcforward as qcf

PATH = abspath("../xtgeo-testdata/3dgrids/reek/")
GRID = "reek_sim_grid.roff"

REPORT = abspath("/tmp/somefile.csv")
SOMEYAML = abspath("/tmp/somefile.yml")


def test_simple_action():

    actions = [
        {
            "property": "reek_sim_poro.roff",
            "warn_outside": [0.18, 0.25],
            "stop_outside": [0, 1],
        },
    ]

    data = {
        "nametag": "MYDATA1",
        "path": PATH,
        "grid": GRID,
        "report": REPORT,
        "actions": actions,
    }

    qcf.grid_statistics(data)

    dfr = pd.read_csv(REPORT)

    assert dfr.loc[dfr["CALCULATION"] == "Avg"].iloc[0]["STATUS"] == "WARN"
    assert dfr.loc[dfr["CALCULATION"] == "Avg"].iloc[0]["VALUE"] == pytest.approx(
        0.1677, 0.001
    )

    pathlib.Path(REPORT).unlink()


def test_gridstatistics_instance():

    zones_stop = [
        ["Below_Top_reek", [0.1, 0.3]],
        ["Below_Mid_reek", [0.1, 0.3]],
        ["Below_Low_reek", [0.1, 0.3]],
    ]

    data = {
        "nametag": "MYDATA1",
        "path": PATH,
        "grid": GRID,
        "report": REPORT,
    }

    qcjob = qcf.GridStatistics()

    for zs in zones_stop:
        usedata = data.copy()

        actions = [
            {
                "property": "reek_sim_poro.roff",
                "selectors": {"reek_sim_zone.roff": zs[0]},
                "stop_outside": zs[1],
            },
        ]

        usedata["actions"] = actions
        qcjob.run(usedata, reuse=True)

    dfr = pd.read_csv(REPORT)
    print(dfr)


def test_action_with_selectors():

    actions = [
        {
            "property": "reek_sim_poro.roff",
            "selectors": {"reek_sim_zone.roff": "Below_Mid_reek"},
            "warn_outside": [0.17, 0.25],
            "stop_outside": [0, 1],
        },
    ]

    data = {
        "nametag": "MYDATA1",
        "path": PATH,
        "grid": GRID,
        "report": REPORT,
        "actions": actions,
    }

    qcf.grid_statistics(data)

    dfr = pd.read_csv(REPORT)

    assert dfr.loc[dfr["CALCULATION"] == "Avg"].iloc[0]["STATUS"] == "WARN"
    assert dfr.loc[dfr["CALCULATION"] == "Avg"].iloc[0]["VALUE"] == pytest.approx(
        0.1606, 0.001
    )

    pathlib.Path(REPORT).unlink()


def test_action_with_filters():

    actions = [
        {
            "property": "reek_sim_poro.roff",
            "filters": {
                "reek_sim_zone.roff": {"exclude": ["Below_Top_reek", "Below_Low_reek"]},
                "reek_sim_facies2.roff": {
                    "include": ["FINESAND", "COARSESAND"],
                },
            },
            "warn_outside": [0.17, 0.25],
            "stop_outside": [0, 1],
        },
    ]

    data = {
        "nametag": "MYDATA1",
        "path": PATH,
        "grid": GRID,
        "report": REPORT,
        "actions": actions,
    }

    qcf.grid_statistics(data)

    dfr = pd.read_csv(REPORT)

    assert dfr.loc[dfr["CALCULATION"] == "Avg"].iloc[0]["STATUS"] == "OK"
    assert dfr.loc[dfr["CALCULATION"] == "Avg"].iloc[0]["VALUE"] == pytest.approx(
        0.2384, 0.001
    )

    pathlib.Path(REPORT).unlink()


def test_action_with_filters_and_selectors():

    actions = [
        {
            "property": "reek_sim_poro.roff",
            "selectors": {"reek_sim_zone.roff": "Below_Mid_reek"},
            "filters": {
                "reek_sim_facies2.roff": {
                    "include": ["FINESAND", "COARSESAND"],
                },
            },
            "warn_outside": [0.17, 0.25],
            "stop_outside": [0, 1],
        },
    ]

    data = {
        "nametag": "MYDATA1",
        "path": PATH,
        "grid": GRID,
        "report": REPORT,
        "actions": actions,
    }

    qcf.grid_statistics(data)

    dfr = pd.read_csv(REPORT)

    assert dfr.loc[dfr["CALCULATION"] == "Avg"].iloc[0]["STATUS"] == "OK"
    assert dfr.loc[dfr["CALCULATION"] == "Avg"].iloc[0]["VALUE"] == pytest.approx(
        0.2384, 0.001
    )

    pathlib.Path(REPORT).unlink()


def test_actions_shall_stop():

    actions = [
        {
            "property": "reek_sim_poro.roff",
            "warn_outside": [0.17, 0.4],
            "stop_outside": [0.20, 1],
        }
    ]

    data = {
        "nametag": "MYDATA1",
        "path": PATH,
        "grid": GRID,
        "actions": actions,
    }

    with pytest.raises(SystemExit):
        qcf.grid_statistics(data)


def test_actions_shall_stop_no_warnlimits():

    actions = [
        {
            "property": "reek_sim_poro.roff",
            "stop_outside": [0.20, 1],
        }
    ]

    data = {
        "nametag": "MYDATA1",
        "path": PATH,
        "grid": GRID,
        "actions": actions,
    }

    with pytest.raises(SystemExit):
        qcf.grid_statistics(data)


def test_actions_with_selectors():

    actions = [
        {
            "property": "reek_sim_poro.roff",
            "selectors": {
                "reek_sim_zone.roff": "Below_Top_reek",
                "reek_sim_facies2.roff": "COARSESAND",
            },
            "warn_outside": [0.17, 0.25],
            "stop_outside": [0, 1],
            "calculation": "Avg",
        },
    ]
    data = {
        "nametag": "MYDATA1",
        "path": PATH,
        "grid": GRID,
        "report": REPORT,
        "actions": actions,
    }
    qcf.grid_statistics(data)

    dfr = pd.read_csv(REPORT)

    assert dfr.loc[dfr["CALCULATION"] == "Avg"].iloc[0]["STATUS"] == "WARN"
    assert dfr.loc[dfr["CALCULATION"] == "Avg"].iloc[0]["VALUE"] == pytest.approx(
        0.3117, 0.001
    )

    pathlib.Path(REPORT).unlink()


def test_multiple_actions():
    actions = [
        {
            "property": "reek_sim_poro.roff",
            "selectors": {
                "reek_sim_zone.roff": "Below_Top_reek",
                "reek_sim_facies2.roff": "COARSESAND",
            },
            "warn_outside": [0.17, 0.25],
            "stop_outside": [0, 1],
            "calculation": "Avg",
        },
        {
            "property": "reek_sim_poro.roff",
            "selectors": {
                "reek_sim_facies2.roff": "FINESAND",
            },
            "warn_outside": [0.17, 0.4],
            "stop_outside": [0, 1],
            "calculation": "Avg",
        },
        {
            "property": "reek_sim_poro.roff",
            "warn_outside": [0, 0.4],
            "stop_outside": [0, 1],
            "calculation": "Max",
        },
    ]

    data = {
        "nametag": "MYDATA1",
        "path": PATH,
        "grid": GRID,
        "report": REPORT,
        "actions": actions,
    }

    qcf.grid_statistics(data)

    dfr = pd.read_csv(REPORT)

    assert dfr.loc[dfr["CALCULATION"] == "Avg"].iloc[0]["STATUS"] == "WARN"
    assert dfr.loc[dfr["CALCULATION"] == "Max"].iloc[0]["STATUS"] == "OK"

    pathlib.Path(REPORT).unlink()


def test_yaml_dump():

    actions = [
        {
            "property": "reek_sim_poro.roff",
            "warn_outside": [0.18, 0.25],
            "stop_outside": [0, 1],
        },
    ]

    data = {
        "nametag": "MYDATA1",
        "path": PATH,
        "grid": GRID,
        "report": REPORT,
        "actions": actions,
        "dump_yaml": SOMEYAML,
    }

    qcf.grid_statistics(data)

    # now read the dump file:
    qcf.grid_statistics(SOMEYAML)

    dfr = pd.read_csv(REPORT)

    assert dfr.loc[dfr["CALCULATION"] == "Avg"].iloc[0]["STATUS"] == "WARN"
    assert dfr.loc[dfr["CALCULATION"] == "Avg"].iloc[0]["VALUE"] == pytest.approx(
        0.1677, 0.001
    )

    pathlib.Path(REPORT).unlink()
    pathlib.Path(SOMEYAML).unlink()
