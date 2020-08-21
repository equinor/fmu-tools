"""
This private module in qcforward is used to check wellzonation vs grid zonation
"""
from __future__ import absolute_import, division, print_function  # PY2

import sys
from os.path import join
import collections
from pathlib import Path

import json
from jsonschema import validate
import numpy as np
import pandas as pd

import fmu.tools
from ._parse_data import _QCForwardData
from ._common import _QCCommon
from ._qcforward import QCForward


QCC = _QCCommon()


class _LocalData(object):  # pylint: disable=too-few-public-methods
    def __init__(self):
        """Defining and hold data local for this routine"""

        self.zonelogname = "Zonelog"
        self.zonelogrange = [0, 99]
        self.depthrange = [0.0, 999999.0]
        self.actions_each = None
        self.actions_all = None
        self.perflogname = None
        self.perflogrange = [1, 9999]
        self.gridzone = None
        self.gridzonerange = [1, 9999]

    def parse_data(self, data, gdata):
        """Parsing the actual data"""

        # TODO: verify and qc

        self.zonelogname = data["zonelog"]["name"]
        self.zonelogrange = data["zonelog"]["range"]
        self.depthrange = data["depthrange"]
        self.actions_each = data["actions_each"]
        self.actions_all = data["actions_all"]
        self.perflogname = None
        self.perflogrange = [1, 9999]

        # need to get the GridProperty() instance for GridProperties()
        self.gridzone = gdata.gridprops.props[0]


class WellZonationVsGrid(QCForward):
    def main(self, data):
        """Main routine for evaulating well zonation match in 3D grids.

        The routine depends on existing XTGeo functions for this purpose
        """
        self._data = self.handle_data(data)
        self._validate_input(self._data)

        data = self._data

        QCC.verbosity = data.get("verbosity", 0)

        # parsing data stored is self._xxx (general data like grid)
        QCC.print_info("Parsing general data...")
        self.gdata = _QCForwardData(data)

        # parse data that are special for this check
        QCC.print_info("Parsing additional data...")
        self.ldata = _LocalData()
        self.ldata.parse_data(data, self.gdata)

        # results are stored in a dict based table which be turned into a Pandas
        # dataframe in the end (most efficient; then turn into pandas at end)
        results = collections.OrderedDict(
            [
                ("WELL", []),
                ("MATCH", []),
                ("WARN_LIMIT", []),
                ("STOP_LIMIT", []),
                ("STATUS", []),
            ]
        )

        results = self._evaluate_per_well(results)

        # all data (look at averages)
        match_allv = np.array(results["MATCH"])
        wlimit = self.ldata.actions_all["warnthreshold"]
        slimit = self.ldata.actions_all["stopthreshold"]
        mmean = np.nanmean(match_allv)

        results["WELL"].append("SUM_WELLS")
        results["MATCH"].append(mmean)
        results["WARN_LIMIT"].append(wlimit)
        results["STOP_LIMIT"].append(wlimit)

        status = "OK"
        if mmean < wlimit:
            status = "WARN"
        if mmean < slimit:
            status = "STOP"

        results["STATUS"].append(status)

        dfr = self._make_report(results)

        QCC.print_debug("Results:")
        print(dfr)

        dfr_warn = dfr[dfr["STATUS"] == "WARN"]
        if len(dfr_warn) > 0:
            print(dfr_warn)

        dfr_stop = dfr[dfr["STATUS"] == "STOP"]
        if len(dfr_stop) > 0:
            print(dfr_stop, file=sys.stderr)
            msg = "One or more wells has status = STOP"
            QCC.force_stop(msg)

        return dfr

    @staticmethod
    def _validate_input(data):
        """Validate data against JSON schemas"""

        spath = Path(fmu.tools.__file__).parent / "qcforward" / "_schemas"

        schemafile = "wellzonation_vs_grid_asfile.json"

        if "project" in data.keys():
            schemafile = "wellzonation_vs_grid_asroxarapi.json"

        with open((spath / schemafile), "r") as thisschema:
            schema = json.load(thisschema)

        validate(instance=data, schema=schema)

    def _evaluate_per_well(self, inresults):  # pylint: disable=too-many-locals
        """Do a check per well"""

        qcdata = self.gdata
        wzong = self.ldata

        results = inresults.copy()

        for wll in qcdata.wells.wells:
            QCC.print_debug("Working with well {}".format(wll.name))

            dfr = wll.dataframe
            useperflog = None
            if wzong.perflogname and wzong.perflogname in dfr.columns:
                useperflog = "PERF_local"
                rng_min = wzong.perflogrange[0]
                rng_max = wzong.perflogrange[1]
                dfr[useperflog] = dfr[wzong.perflogname] * 0
                dfr[useperflog].where(
                    (dfr[wzong.perflogname] >= rng_min)
                    & (dfr[wzong.perflogname] <= rng_max),
                    1,
                    inplace=True,
                )
                wll.dataframe = dfr

            res = qcdata.grid.report_zone_mismatch(
                well=wll,
                zonelogname=wzong.zonelogname,
                zoneprop=wzong.gridzone,
                zonelogrange=wzong.zonelogrange,
                depthrange=wzong.depthrange,
                perflogname=useperflog,
                resultformat=2,
            )
            print("XXX", res)

            results["WELL"].append(wll.name)

            if res:
                wname = wll.name
                match = res["MATCH2"]
                QCC.print_info("Well: {0:30s} - {1: 5.3f}".format(wname, match))
                wlimit = wzong.actions_each["warnthreshold"]
                slimit = wzong.actions_each["stopthreshold"]
                results["WARN_LIMIT"].append(wlimit)
                results["STOP_LIMIT"].append(slimit)

                status = "OK"
                if match < wlimit:
                    status = "WARN"
                if match < slimit:
                    status = "STOP"

                results["MATCH"].append(match)
                results["STATUS"].append(status)

            else:
                results["MATCH"].append(float("nan"))
                results["WARN_LIMIT"].append(float("nan"))
                results["STOP_LIMIT"].append(float("nan"))
                results["STATUS"].append(float("nan"))

        return results

    def _make_report(self, results):
        """Make a report which e.g. can be used in webviz plotting

        Args:
            self (instance): The QCForward instance
            results (dict): Results table

        Returns:
            A Pandas dataframe
        """

        dfr = pd.DataFrame(results)
        dfr["NAMETAG"] = self.gdata.nametag

        if self.gdata.reportfile:
            reportfile = join(self._path, self.gdata.reportfile)
            if self.gdata.reportmode in ("append", "a"):
                dfr.to_csv(reportfile, index=False, mode="a", header=None)
            else:
                dfr.to_csv(reportfile, index=False)

        return dfr


# def run_wellzonation_vs_grid():

#     wzong = WellZonationVsGrid()
#     wzong.main()

# cmn = _common._QCCommon(data["verbosity"])

# # defaults:
# zonelogname = "Zonelog"
# zonelogrange = (1, 99)
# depthrange = (0, 9999)
# actions_each = {"warnthreshold": 99, "stopthreshold": 50}
# actions_all = {"warnthreshold": 99, "stopthreshold": 88}
# report = {"file": None, "write": "write"}
# perflogname = None
# perflogrange = (1, 9999)

# if "zonelog" in data:
#     zonelogname = data["zonelog"].get("name", "Zonelog")
#     zlrange = data["zonelog"].get("range", zonelogrange)
#     if (
#         isinstance(zlrange, list)
#         and len(zlrange) == 2
#         and isinstance(zlrange[0], int)
#         and isinstance(zlrange[1], int)
#         and zlrange[1] >= zlrange[0]
#     ):
#         zonelogrange = tuple(zlrange)
#     else:
#         raise ValueError("zonelogrange on wrong format: ", zlrange)
# else:
#     raise ValueError("Key zonelog is missing in data")

# if "depthrange" in data:
#     drange = data["depthrange"]
#     if (
#         isinstance(drange, list)
#         and len(drange) == 2
#         and isinstance(drange[0], (int, float))
#         and isinstance(drange[1], (int, float))
#         and drange[1] > drange[0]
#     ):
#         depthrange = tuple(drange)
#     else:
#         raise ValueError("depthrange on wrong format: ", drange)

# if "perforationlog" in data:
#     perflogname = data["perforationlog"].get("name", "PERFLOG")
#     perflogrange = tuple(data["perforationlog"].get("range", [1, 9999]))

# if "actions_each" in data:
#     # todo check data
#     actions_each = data["actions_each"]

# if "actions_all" in data:
#     # todo check data
#     actions_all = data["actions_all"]

# if "report" in data:
#     # todo check data
#     report = data["report"]

# wzong = WZong(
#     zonelogname=zonelogname,
#     zonelogrange=zonelogrange,
#     depthrange=depthrange,
#     actions_each=actions_each,
#     actions_all=actions_all,
#     report=report,
#     perflogname=perflogname,
#     perflogrange=perflogrange,
# )

# return wzong

