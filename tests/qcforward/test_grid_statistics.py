from os.path import abspath

import pandas as pd
import pytest

from fmu.tools import qcforward as qcf


@pytest.fixture
def make_data(tmp_path, testdata_path):
    report_path = str(tmp_path / "somefile.csv")
    yaml_path = str(tmp_path / "somefile.yml")
    data = {
        "path": abspath(testdata_path / "3dgrids/reek/"),
        "grid": "reek_sim_grid.roff",
        "report": report_path,
        "verbosity": 1,
    }
    return data, report_path, yaml_path


def test_simple_action(make_data):
    data, report_path, _ = make_data
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

    dfr = pd.read_csv(report_path)

    assert dfr.loc[dfr["CALCULATION"] == "Avg"].iloc[0]["STATUS"] == "WARN"
    assert dfr.loc[dfr["CALCULATION"] == "Avg"].iloc[0]["VALUE"] == pytest.approx(
        0.1677, 0.001
    )


def test_action_with_disc_and_cont_props(make_data):
    data, report_path, _ = make_data
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

    dfr = pd.read_csv(report_path)

    assert dfr.loc[dfr["PROPERTY"] == "reek_sim_poro.roff"].iloc[0]["STATUS"] == "WARN"
    assert dfr.loc[dfr["PROPERTY"] == "reek_sim_poro.roff"].iloc[0][
        "VALUE"
    ] == pytest.approx(0.1677, 0.001)
    assert dfr.loc[
        (dfr["PROPERTY"] == "reek_sim_facies2.roff") & (dfr["DESCRIPTION"] == "test2")
    ].iloc[0]["VALUE"] == pytest.approx(0.585, abs=0.001)


def test_multiple_actions(make_data):
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

    data, report_path, _ = make_data
    data["actions"] = actions
    qcjob = qcf.GridStatistics()
    qcjob.run(data)

    _ = pd.read_csv(report_path)


def test_action_with_selectors(make_data):
    data, report_path, _ = make_data
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

    dfr = pd.read_csv(report_path)

    assert dfr.loc[dfr["CALCULATION"] == "Avg"].iloc[0]["STATUS"] == "WARN"
    assert dfr.loc[dfr["CALCULATION"] == "Avg"].iloc[0]["VALUE"] == pytest.approx(
        0.1606, 0.001
    )


def test_action_with_filters(make_data):
    data, report_path, _ = make_data
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

    dfr = pd.read_csv(report_path)

    assert dfr.loc[dfr["CALCULATION"] == "Avg"].iloc[0]["STATUS"] == "OK"
    assert dfr.loc[dfr["CALCULATION"] == "Avg"].iloc[0]["VALUE"] == pytest.approx(
        0.2384, 0.001
    )


def test_action_with_filters_and_selectors(make_data):
    data, report_path, _ = make_data
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

    dfr = pd.read_csv(report_path)

    assert dfr.loc[dfr["CALCULATION"] == "Avg"].iloc[0]["STATUS"] == "OK"
    assert dfr.loc[dfr["CALCULATION"] == "Avg"].iloc[0]["VALUE"] == pytest.approx(
        0.2384, 0.001
    )


def test_actions_shall_stop(make_data):
    data, *_ = make_data
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


def test_actions_shall_stop_no_warnlimits(make_data):
    data, *_ = make_data
    data["actions"] = [
        {
            "property": "reek_sim_poro.roff",
            "stop_outside": [0.20, 1],
        }
    ]

    qcjob = qcf.GridStatistics()
    with pytest.raises(SystemExit):
        qcjob.run(data)


def test_actions_with_selectors(make_data):
    data, report_path, _ = make_data
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

    dfr = pd.read_csv(report_path)

    assert dfr.loc[dfr["CALCULATION"] == "Avg"].iloc[0]["STATUS"] == "WARN"
    assert dfr.loc[dfr["CALCULATION"] == "Avg"].iloc[0]["VALUE"] == pytest.approx(
        0.3117, 0.001
    )


def test_yaml_dump(make_data):
    data, report_path, yaml_path = make_data
    data["actions"] = [
        {
            "property": "reek_sim_poro.roff",
            "warn_outside": [0.18, 0.25],
            "stop_outside": [0, 1],
        },
    ]

    data["dump_yaml"] = yaml_path
    qcjob = qcf.GridStatistics()
    qcjob.run(data)

    # now read the dump file:
    qcjob.run(data=yaml_path)

    dfr = pd.read_csv(report_path)

    assert dfr.loc[dfr["CALCULATION"] == "Avg"].iloc[0]["STATUS"] == "WARN"
    assert dfr.loc[dfr["CALCULATION"] == "Avg"].iloc[0]["VALUE"] == pytest.approx(
        0.1677, 0.001
    )
