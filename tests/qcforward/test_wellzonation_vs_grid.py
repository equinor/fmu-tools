"""Testing qcforward method wellzonation vs grid"""

from os.path import abspath

import pandas as pd
import pytest

import fmu.tools.qcforward as qcf

ZONENAME = "Zone"
ZONELOGNAME = "Zonelog"
PERFLOGNAME = "PERF"


@pytest.fixture
def make_data(tmp_path, testdata_path):
    report_path = str(tmp_path / "somefile.csv")
    yaml_path = str(tmp_path / "somefile.yml")
    gridfile = abspath(testdata_path / "3dgrids/reek/reek_sim_grid.roff")
    zonefile = abspath(testdata_path / "3dgrids/reek/reek_sim_zone.roff")
    wellfiles = [
        abspath(testdata_path / "wells/reek/1/OP*.w"),
        abspath(testdata_path / "wells/reek/1/WI*.w"),
    ]
    data = {
        "nametag": "MYDATA1",
        "verbosity": "debug",
        "path": str(tmp_path),
        "grid": gridfile,
        "gridprops": [[ZONENAME, zonefile]],
        "wells": wellfiles,
        "zonelog": {"name": ZONELOGNAME, "range": [1, 3]},
        "depthrange": [1580, 9999],
        "actions": [
            {"warn": "anywell < 50%", "stop": "anywell < 20%"},
            {"warn": "allwells < 80%", "stop": "allwells < 20%"},
        ],
        "report": {"file": report_path, "mode": "write"},
        "dump_yaml": yaml_path,
    }
    return data, report_path, yaml_path


def test_zonelog_vs_grid_asfiles(make_data):
    """Testing the zonelog vs grid functionality using files"""
    data, report_path, yaml_path = make_data
    qcf.wellzonation_vs_grid(data)

    # now read the dump file:
    qcf.wellzonation_vs_grid(yaml_path)

    dfr = pd.read_csv(report_path, index_col="WELL")
    assert dfr.loc["all", "MATCH%"] == pytest.approx(63.967, 0.01)


def test_zonelog_vs_grid_asfiles_shall_stop(make_data):
    """Testing the zonelog vs grid functionality using files"""
    data, *_ = make_data
    data["actions"] = [{"warn": "any < 90%", "stop": "any < 80%"}]

    with pytest.raises(SystemExit):
        qcf.wellzonation_vs_grid(data)


def test_zonelog_vs_grid_asfiles_reuse_instance(make_data):
    """Testing reusing the instance"""
    data, *_ = make_data
    newdata = data.copy()
    newdata["actions"] = [{"warn": "anywell < 33%", "stop": "anywell < 22%"}]

    job = qcf.WellZonationVsGrid()

    job.run(data)
    job.run(newdata, reuse=True)


def test_perflog_vs_grid_asfiles(make_data):
    """
    Testing the perforation log as zonelog filter vs grid functionality using files.

    When a perflog is present, it means in this example
    that all intervals within a PERFLOG range will have a zonelog vs grid check,
    i.e. the PERFLOG acts a contrain/filter. In intervals with missing PERFLOG,
    or if PERFLOG is outside range, then zonelog vs grid checks is ignored.

    """
    data, report_path, _ = make_data
    data["perflog"] = {"name": PERFLOGNAME, "range": [1, 5]}

    wellcheck = qcf.WellZonationVsGrid()
    wellcheck.run(data)

    dfr = pd.read_csv(report_path, index_col="WELL")

    assert dfr.loc["OP_1_PERF", "MATCH%"] == pytest.approx(80.701, 0.01)
