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
            "description": "test",
        },
    ]

    data = {
        "nametag": "MYDATA1",
        "path": PATH,
        "grid": GRID,
        "report": REPORT,
        "actions": actions,
    }
    qcjob = qcf.GridStatistics()
    qcjob.run(data)

    dfr = pd.read_csv(REPORT)

    assert dfr.loc[dfr["CALCULATION"] == "Avg"].iloc[0]["STATUS"] == "WARN"
    assert dfr.loc[dfr["CALCULATION"] == "Avg"].iloc[0]["VALUE"] == pytest.approx(
        0.1677, 0.001
    )

    pathlib.Path(REPORT).unlink()


def test_action_with_disc_and_cont_props():

    actions = [
        {
            "property": "reek_sim_poro.roff",
            "warn_outside": [0.18, 0.25],
            "stop_outside": [0, 1],
            "description": "test",
        },
        {
            "property": "reek_sim_facies2.roff",
            "codename": "SHALE",
            "warn_outside": [30, 70],
            "stop_outside": [0, 100],
            "description": "test2",
        },
    ]

    data = {
        "nametag": "MYDATA1",
        "path": PATH,
        "grid": GRID,
        "report": REPORT,
        "actions": actions,
    }
    qcjob = qcf.GridStatistics()
    qcjob.run(data)

    dfr = pd.read_csv(REPORT)

    assert dfr.loc[dfr["CALCULATION"] == "Avg"].iloc[0]["STATUS"] == "WARN"
    assert dfr.loc[dfr["CALCULATION"] == "Avg"].iloc[0]["VALUE"] == pytest.approx(
        0.1677, 0.001
    )
    assert dfr.loc[dfr["CALCULATION"] == "Percent"].iloc[0]["VALUE"] == pytest.approx(
        58.50, abs=0.01
    )

    pathlib.Path(REPORT).unlink()


def test_multiple_actions():

    zones_stop = [
        ["Below_Top_reek", [0.1, 0.3]],
        ["Below_Mid_reek", [0.1, 0.25]],
        ["Below_Low_reek", [0.1, 0.20]],
    ]

    data = {
        "nametag": "MYDATA1",
        "path": PATH,
        "grid": GRID,
        "report": REPORT + "1",
    }

    actions = []
    for zs in zones_stop:
        actions.append(
            {
                "property": "reek_sim_poro.roff",
                "selectors": {"reek_sim_zone.roff": zs[0]},
                "stop_outside": zs[1],
            }
        )

    data["actions"] = actions
    qcjob = qcf.GridStatistics()
    qcjob.run(data)

    dfr = pd.read_csv(REPORT + "1")
    print(dfr)
    pathlib.Path(REPORT + "1").unlink()


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
        "report": REPORT + "2",
        "actions": actions,
    }
    qcjob = qcf.GridStatistics()
    qcjob.run(data)

    dfr = pd.read_csv(REPORT + "2")

    assert dfr.loc[dfr["CALCULATION"] == "Avg"].iloc[0]["STATUS"] == "WARN"
    assert dfr.loc[dfr["CALCULATION"] == "Avg"].iloc[0]["VALUE"] == pytest.approx(
        0.1606, 0.001
    )

    pathlib.Path(REPORT + "2").unlink()


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
        "report": REPORT + "3",
        "actions": actions,
    }
    qcjob = qcf.GridStatistics()
    qcjob.run(data)

    dfr = pd.read_csv(REPORT + "3")

    assert dfr.loc[dfr["CALCULATION"] == "Avg"].iloc[0]["STATUS"] == "OK"
    assert dfr.loc[dfr["CALCULATION"] == "Avg"].iloc[0]["VALUE"] == pytest.approx(
        0.2384, 0.001
    )

    pathlib.Path(REPORT + "3").unlink()


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
        "report": REPORT + "4",
        "actions": actions,
    }
    qcjob = qcf.GridStatistics()
    qcjob.run(data)

    dfr = pd.read_csv(REPORT + "4")

    assert dfr.loc[dfr["CALCULATION"] == "Avg"].iloc[0]["STATUS"] == "OK"
    assert dfr.loc[dfr["CALCULATION"] == "Avg"].iloc[0]["VALUE"] == pytest.approx(
        0.2384, 0.001
    )

    pathlib.Path(REPORT + "4").unlink()


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
    qcjob = qcf.GridStatistics()
    with pytest.raises(SystemExit):
        qcjob.run(data)


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
    qcjob = qcf.GridStatistics()
    with pytest.raises(SystemExit):
        qcjob.run(data)


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
        "report": REPORT + "5",
        "actions": actions,
    }
    qcjob = qcf.GridStatistics()
    qcjob.run(data)

    dfr = pd.read_csv(REPORT + "5")

    assert dfr.loc[dfr["CALCULATION"] == "Avg"].iloc[0]["STATUS"] == "WARN"
    assert dfr.loc[dfr["CALCULATION"] == "Avg"].iloc[0]["VALUE"] == pytest.approx(
        0.3117, 0.001
    )

    pathlib.Path(REPORT + "5").unlink()


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
        "report": REPORT + "6",
        "actions": actions,
        "dump_yaml": SOMEYAML,
    }
    qcjob = qcf.GridStatistics()
    qcjob.run(data)

    # now read the dump file:
    qcjob.run(data=SOMEYAML)

    dfr = pd.read_csv(REPORT + "6")

    assert dfr.loc[dfr["CALCULATION"] == "Avg"].iloc[0]["STATUS"] == "WARN"
    assert dfr.loc[dfr["CALCULATION"] == "Avg"].iloc[0]["VALUE"] == pytest.approx(
        0.1677, 0.001
    )

    pathlib.Path(REPORT + "6").unlink()
    pathlib.Path(SOMEYAML).unlink()
