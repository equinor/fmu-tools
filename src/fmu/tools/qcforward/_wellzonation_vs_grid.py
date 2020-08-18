"""
This private module in qcforward is used to check wellzonation vs grid zonation
"""
from __future__ import absolute_import, division, print_function  # PY2

import sys
from os.path import join
import collections
import numpy as np
import pandas as pd
from . import _parse_data

# named tuple for local data
WZong = collections.namedtuple(
    "WZong",
    "zonelogname zonelogrange depthrange actions_each actions_all "
    "report perflogname perflogrange",
)


def _parse_local_data(data):
    """
    Parse and check data which are more special/local to this routine, return
    data via a named tuple

    Args:
        data (dict): The data dictionary
    """

    # defaults:
    zonelogname = "Zonelog"
    zonelogrange = (1, 99)
    depthrange = (0, 9999)
    actions_each = {"warnthreshold": 99, "stopthreshold": 50}
    actions_all = {"warnthreshold": 99, "stopthreshold": 88}
    report = {"file": None, "write": "write"}
    perflogname = None
    perflogrange = (1, 9999)

    if "zonelog" in data:
        zonelogname = data["zonelog"].get("name", "Zonelog")
        zlrange = data["zonelog"].get("range", zonelogrange)
        if (
            isinstance(zlrange, list)
            and len(zlrange) == 2
            and isinstance(zlrange[0], int)
            and isinstance(zlrange[1], int)
            and zlrange[1] >= zlrange[0]
        ):
            zonelogrange = tuple(zlrange)
        else:
            raise ValueError("zonelogrange on wrong format: ", zlrange)
    else:
        raise ValueError("Key zonelog is missing in data")

    if "depthrange" in data:
        drange = data["depthrange"]
        if (
            isinstance(drange, list)
            and len(drange) == 2
            and isinstance(drange[0], (int, float))
            and isinstance(drange[1], (int, float))
            and drange[1] > drange[0]
        ):
            depthrange = tuple(drange)
        else:
            raise ValueError("depthrange on wrong format: ", drange)

    if "perforationlog" in data:
        perflogname = data["perforationlog"].get("name", "PERFLOG")
        perflogrange = tuple(data["perforationlog"].get("range", [1, 9999]))

    if "actions_each" in data:
        # todo check data
        actions_each = data["actions_each"]

    if "actions_all" in data:
        # todo check data
        actions_all = data["actions_all"]

    if "report" in data:
        # todo check data
        report = data["report"]

    wzong = WZong(
        zonelogname=zonelogname,
        zonelogrange=zonelogrange,
        depthrange=depthrange,
        actions_each=actions_each,
        actions_all=actions_all,
        report=report,
        perflogname=perflogname,
        perflogrange=perflogrange,
    )

    return wzong


def _make_report(self, wzong, results):
    """Make a report which e.g. can be used in webviz plotting

    Args:
        self (instance): The QCForward instance
        wzong (named tuple): local data
        results (dict): Results table

    Returns:
        A Pandas dataframe
    """

    dfr = pd.DataFrame(results)

    if wzong.report["file"]:
        reportfile = join(self._path, wzong.report["file"])
        if wzong.report["mode"] == "append":
            dfr.to_csv(reportfile, index=False, mode="a", header=None)
        else:
            dfr.to_csv(reportfile, index=False)

    return dfr


def _evaluate_per_well(self, wzong, inresults):
    """Do a check per well"""

    results = inresults.copy()

    for wll in self._wells.wells:
        self.print_debug("Working with well {}".format(wll.name))

        dfr = wll.dataframe
        useperflog = "PERF__local"
        if wzong.perflogname and wzong.perflogname in dfr.columns:
            rng_min = wzong.perflogrange[0]
            rng_max = wzong.perflogrange[1]
            dfr[useperflog] = dfr[wzong.perflogname] * 0
            dfr[useperflog].where(
                (dfr[wzong.perflogname] >= rng_min)
                & (dfr[wzong.perflogname] <= rng_max),
                1,
                inplace=True,
            )

        res = self._grid.report_zone_mismatch(
            well=wll,
            zonelogname=self._zonelogname,
            zoneprop=self._gridzone,
            zonelogrange=wzong.zonelogrange,
            depthrange=wzong.depthrange,
            perflogname=useperflog,
            resultformat=2,
        )
        self.print_debug(res)

        results["WELL"].append(wll.name)

        if res:
            wname = wll.name
            match = res["MATCH2"]
            self.print_info("Well: {0:30s} - {1: 5.3f}".format(wname, match))
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


def wellzonation_vs_grid(self, data):
    """Main routine for evaulating well zonation match in 3D grids.

    The routine depends on existing XTGeo functions for this purpose

    Args:
        data (dict): Input data
    """

    # parsing data stored is self._xxx (general data like grid)
    self.print_info("Parsing general data...")
    _parse_data.parse(self, data)

    # parse data that are special for this check
    self.print_info("Parsing additional data...")
    wzong = _parse_local_data(data)

    # results are stored in a dict based table which be turned into a Pandas
    # dataframe in the end (most efficient to increment lists; then turn into pandas)
    results = collections.OrderedDict(
        [
            ("WELL", []),
            ("MATCH", []),
            ("WARN_LIMIT", []),
            ("STOP_LIMIT", []),
            ("STATUS", []),
        ]
    )

    results = _evaluate_per_well(self, wzong, results)

    # all data (look at averages)
    match_allv = np.array(results["MATCH"])
    wlimit = wzong.actions_all["warnthreshold"]
    slimit = wzong.actions_all["stopthreshold"]
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

    results["MATCH"].append(status)

    dfr = _make_report(self, wzong, results,)

    self.print_debug("Results:")
    print(dfr)

    dfr_warn = dfr[dfr["STATUS"] == "WARN"]
    if len(dfr_warn) > 0:
        print(dfr_warn)

    dfr_stop = dfr[dfr["STATUS"] == "STOP"]
    if len(dfr_stop) > 0:
        print(dfr_stop, file=sys.stderr)
        msg = "One or more wells has status = STOP"
        self.force_stop(msg)

    return dfr
