import pathlib
from os.path import abspath
import pytest
import pandas as pd

from fmu.tools import qcforward as qcf

SOMEYAML = abspath("/tmp/somefile.yml")
REPORT = abspath("/tmp/somefile.csv")


@pytest.fixture(name="data")
def fixture_data():
    return {
        "path": abspath("../xtgeo-testdata/3dgrids/reek/"),
        "grid": "reek_sim_grid.roff",
        "report": REPORT,
        "verbosity": 1,
    }


def test_simple_action(data):

    data["actions"] = [
        {
            "property": "reek_sim_poro.roff",
            "warn_outside": [0.18, 0.25],
            "stop_outside": [0, 1],
            "description": "test",
        },
    ]

    qcjob = qcf.GridStatistics()
    qcjob.run(data)

    dfr = pd.read_csv(REPORT)

    assert dfr.loc[dfr["CALCULATION"] == "Avg"].iloc[0]["STATUS"] == "WARN"
    assert dfr.loc[dfr["CALCULATION"] == "Avg"].iloc[0]["VALUE"] == pytest.approx(
        0.1677, 0.001
    )

    pathlib.Path(REPORT).unlink()


def test_action_with_disc_and_cont_props(data):

    data["actions"] = [
        {
            "property": "reek_sim_poro.roff",
            "warn_outside": [0.18, 0.25],
            "stop_outside": [0, 1],
            "description": "test",
        },
        {
            "property": "reek_sim_facies2.roff",
            "codename": "SHALE",
            "warn_outside": [0.3, 0.7],
            "stop_outside": [0, 1],
            "description": "test2",
        },
        {
            "property": "reek_sim_facies2.roff",
            "codename": "SHALE",
            "selectors": {"reek_sim_zone.roff": "Below_Top_reek"},
            "warn_outside": [0.3, 0.7],
            "stop_outside": [0, 1],
            "description": "test3",
        },
    ]

    qcjob = qcf.GridStatistics()
    qcjob.run(data)

    dfr = pd.read_csv(REPORT)

    assert dfr.loc[dfr["PROPERTY"] == "reek_sim_poro.roff"].iloc[0]["STATUS"] == "WARN"
    assert dfr.loc[dfr["PROPERTY"] == "reek_sim_poro.roff"].iloc[0][
        "VALUE"
    ] == pytest.approx(0.1677, 0.001)
    assert dfr.loc[
        (dfr["PROPERTY"] == "reek_sim_facies2.roff") & (dfr["DESCRIPTION"] == "test2")
    ].iloc[0]["VALUE"] == pytest.approx(0.585, abs=0.001)

    pathlib.Path(REPORT).unlink()


def test_multiple_actions(data):

    zones_stop = [
        ["Below_Top_reek", [0.1, 0.3]],
        ["Below_Mid_reek", [0.1, 0.25]],
        ["Below_Low_reek", [0.1, 0.20]],
    ]

    actions = []
    for zstop in zones_stop:
        actions.append(
            {
                "property": "reek_sim_poro.roff",
                "selectors": {"reek_sim_zone.roff": zstop[0]},
                "stop_outside": zstop[1],
            }
        )

    data["actions"] = actions
    qcjob = qcf.GridStatistics()
    qcjob.run(data)

    dfr = pd.read_csv(REPORT)
    print(dfr)
    pathlib.Path(REPORT).unlink()


def test_action_with_selectors(data):

    data["actions"] = [
        {
            "property": "reek_sim_poro.roff",
            "selectors": {"reek_sim_zone.roff": "Below_Mid_reek"},
            "warn_outside": [0.17, 0.25],
            "stop_outside": [0, 1],
        },
    ]

    qcjob = qcf.GridStatistics()
    qcjob.run(data)

    dfr = pd.read_csv(REPORT)

    assert dfr.loc[dfr["CALCULATION"] == "Avg"].iloc[0]["STATUS"] == "WARN"
    assert dfr.loc[dfr["CALCULATION"] == "Avg"].iloc[0]["VALUE"] == pytest.approx(
        0.1606, 0.001
    )

    pathlib.Path(REPORT).unlink()


def test_action_with_filters(data):

    data["actions"] = [
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

    qcjob = qcf.GridStatistics()
    qcjob.run(data)

    dfr = pd.read_csv(REPORT)

    assert dfr.loc[dfr["CALCULATION"] == "Avg"].iloc[0]["STATUS"] == "OK"
    assert dfr.loc[dfr["CALCULATION"] == "Avg"].iloc[0]["VALUE"] == pytest.approx(
        0.2384, 0.001
    )

    pathlib.Path(REPORT).unlink()


def test_action_with_filters_and_selectors(data):

    data["actions"] = [
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

    qcjob = qcf.GridStatistics()
    qcjob.run(data)

    dfr = pd.read_csv(REPORT)

    assert dfr.loc[dfr["CALCULATION"] == "Avg"].iloc[0]["STATUS"] == "OK"
    assert dfr.loc[dfr["CALCULATION"] == "Avg"].iloc[0]["VALUE"] == pytest.approx(
        0.2384, 0.001
    )

    pathlib.Path(REPORT).unlink()


def test_actions_shall_stop(data):

    data["actions"] = [
        {
            "property": "reek_sim_poro.roff",
            "warn_outside": [0.17, 0.4],
            "stop_outside": [0.20, 1],
        }
    ]

    qcjob = qcf.GridStatistics()
    with pytest.raises(SystemExit):
        qcjob.run(data)


def test_actions_shall_stop_no_warnlimits(data):

    data["actions"] = [
        {
            "property": "reek_sim_poro.roff",
            "stop_outside": [0.20, 1],
        }
    ]

    qcjob = qcf.GridStatistics()
    with pytest.raises(SystemExit):
        qcjob.run(data)


def test_actions_with_selectors(data):

    data["actions"] = [
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

    qcjob = qcf.GridStatistics()
    qcjob.run(data)

    dfr = pd.read_csv(REPORT)

    assert dfr.loc[dfr["CALCULATION"] == "Avg"].iloc[0]["STATUS"] == "WARN"
    assert dfr.loc[dfr["CALCULATION"] == "Avg"].iloc[0]["VALUE"] == pytest.approx(
        0.3117, 0.001
    )

    pathlib.Path(REPORT).unlink()


def test_yaml_dump(data):

    data["actions"] = [
        {
            "property": "reek_sim_poro.roff",
            "warn_outside": [0.18, 0.25],
            "stop_outside": [0, 1],
        },
    ]

    data["dump_yaml"] = SOMEYAML
    qcjob = qcf.GridStatistics()
    qcjob.run(data)

    # now read the dump file:
    qcjob.run(data=SOMEYAML)

    dfr = pd.read_csv(REPORT)

    assert dfr.loc[dfr["CALCULATION"] == "Avg"].iloc[0]["STATUS"] == "WARN"
    assert dfr.loc[dfr["CALCULATION"] == "Avg"].iloc[0]["VALUE"] == pytest.approx(
        0.1677, 0.001
    )

    pathlib.Path(REPORT).unlink()
    pathlib.Path(SOMEYAML).unlink()
