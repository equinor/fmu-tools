"""Testing qcforward method wellzonation vs grid"""

import pathlib
import sys
from os.path import abspath
import pytest
import pandas as pd

import fmu.tools.qcforward as qcf


import xtgeo


# filedata
PATH = abspath(".")  # normally not needed; here due to pytest fixture tmpdir
GRIDFILE = "../xtgeo-testdata/3dgrids/reek/reek_sim_grid.roff"
ZONENAME = "Zone"
ZONEFILE = "../xtgeo-testdata/3dgrids/reek/reek_sim_zone.roff"
WELLFILES = [
    "../xtgeo-testdata/wells/reek/1/OP*.w",
    "../xtgeo-testdata/wells/reek/1/WI*.w",
]

ZONELOGNAME = "Zonelog"
PERFLOGNAME = "Perflog"
REPORT = abspath("/tmp/somefile.csv")
SOMEYAML = abspath("/tmp/somefile.yml")

DATA1 = {
    "nametag": "MYDATA1",
    "verbosity": "debug",
    "path": PATH,
    "grid": GRIDFILE,
    "gridprops": [[ZONENAME, ZONEFILE]],
    "wells": WELLFILES,
    "zonelog": {"name": ZONELOGNAME, "range": [1, 3]},
    "depthrange": [1580, 9999],
    "actions_each": {"warnthreshold": 50, "stopthreshold": 20},
    "actions_all": {"warnthreshold": 80, "stopthreshold": 20},
    "report": {"file": REPORT, "mode": "write"},
    "dump_yaml": SOMEYAML,
}


def test_zonelog_vs_grid_asfiles():
    """Testing the zonelog vs grid functionality using files"""

    qcf.wellzonation_vs_grid(DATA1)

    # now read the dump file:
    qcf.wellzonation_vs_grid(SOMEYAML)

    dfr = pd.read_csv(REPORT)
    print(dfr)
    assert dfr.loc[11, "MATCH"] == pytest.approx(63.967, 0.01)

    pathlib.Path(REPORT).unlink()
    pathlib.Path(SOMEYAML).unlink()


# def test_zonelog_vs_grid_asfiles_shall_stop():
#     """Testing the zonelog vs grid functionality using files"""

#     data = {
#         "verbosity": "debug",
#         "path": PATH,
#         "grid": GRIDFILE,
#         "zone": {ZONENAME: ZONEFILE},
#         "wells": WELLFILES,
#         "zonelogname": ZONELOGNAME,
#         "zonelogrange": [1, 3],  # inclusive range at both ends
#         "depthrange": [1580, 9999],
#         "actions_each": {"warnthreshold": 50, "stopthreshold": 70},
#         "actions_all": {"warnthreshold": 80, "stopthreshold": 70},
#     }

#     wellcheck = qcf.QCForward()

#     with pytest.raises(SystemExit):
#         wellcheck.wellzonation_vs_grid(data)


# @pytest.mark.skipif(sys.version_info < (3, 0), reason="requires Python3")
# def test_perflog_vs_grid_asfiles():
#     """
#     Testing the perforation log as zonelog filter vs grid functionality using files.

#     When a perflog is present, it means in this example
#     that all intervals within a PERFLOG range will have a zonelog vs grid check,
#     i.e. the PERFLOG acts a contrain/filter. In intervals with missing PERFLOG,
#     or if PERFLOG is zero, then zonelog vs grid checks is ignored.


#     """

#     data = {
#         "verbosity": "debug",
#         "path": PATH,
#         "grid": GRIDFILE,
#         "gridprops": [{ZONENAME: ZONEFILE}],
#         "wells": WELLFILES,
#         "zonelogname": ZONELOGNAME,
#         "zonelogrange": [1, 3],  # inclusive range at both ends
#         "depthrange": [1580, 9999],
#         "perforationlog": {"name": PERFLOGNAME, "range": [1, 9999]},
#         "actions_each": {"warnthreshold": 50, "stopthreshold": 20},
#         "actions_all": {"warnthreshold": 80, "stopthreshold": 20},
#         "report": {"file": REPORT, "mode": "write"},
#         "dump_yaml": "somefile.yml",
#     }

#     wellcheck = qcf.QCForward()
#     # wellcheck.wellzonation_vs_grid(data)

#     # print(dfr)
#     # assert dfr.loc[11, "MATCH"] == pytest.approx(58.15, 0.01)
#     # os.unlink("somefile.yml")
#     # os.unlink(REPORT)
