"""
This private module in qcforward is used to check wellzonation vs grid
"""
from __future__ import absolute_import, division, print_function  # PY2

import logging
import sys
from os.path import join
import collections
import numpy as np
import pandas as pd
from . import _parse_data

logger = logging.getLogger(__name__)
logger.setLevel(logging.CRITICAL)

WZong = collections.namedtuple(
    "WZong", "zonelogrange depthrange actions_each actions_all report"
)


def _parse_wzong(data):
    """Parse ande check data local to this routine, return a named tuple"""

    # defaults:
    zonelogrange = (1, 99)
    depthrange = (0, 9999)
    actions_each = {"warnthreshold": 99, "stopthreshold": 50}
    actions_all = {"warnthreshold": 99, "stopthreshold": 88}
    report = {"file": None, "write": "write"}

    if "zonelogrange" in data:
        zlrange = data["zonelogrange"]
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
        zonelogrange=zonelogrange,
        depthrange=depthrange,
        actions_each=actions_each,
        actions_all=actions_all,
        report=report,
    )

    return wzong


def _make_report(
    self, wzong, data, well_all, match_all, well_warn, well_stop, well_status
):
    """Make a report which e.g. can be used in webviz plotting"""

    res = collections.OrderedDict()
    res["WELL"] = well_all
    res["MATCH"] = match_all
    res["WARN_LIMIT"] = well_warn
    res["STOP_LIMIT"] = well_stop
    res["STATUS"] = well_status

    dfr = pd.DataFrame(res)

    if wzong.report["file"]:
        reportfile = join(self._path, wzong.report["file"])
        if wzong.report["mode"] == "append":
            dfr.to_csv(reportfile, index=False, mode="a", header=None)
        else:
            dfr.to_csv(reportfile, index=False)

    return dfr


def wellzonation_vs_grid(
    self, data
):  # pylint: disable=too-many-locals, too-many-statements

    # parsing data stored is self._xxx (general data like grid)
    self.print_info("Parsing data...")
    _parse_data.parse(self, data)

    # parse data that are special for this check
    self.print_info("Parsing additional data...")
    wzong = _parse_wzong(data)

    match_all = []
    well_all = []
    well_warn_limit = []
    well_stop_limit = []
    well_status = []

    for wll in self._wells.wells:
        self.print_debug("Working with well {}".format(wll.name))

        res = self._grid.report_zone_mismatch(
            well=wll,
            zonelogname=self._zonelogname,
            zoneprop=self._gridzone,
            zonelogrange=wzong.zonelogrange,
            depthrange=wzong.depthrange,
            resultformat=2,
        )
        self.print_debug(res)

        well_all.append(wll.name)

        if res:
            wname = wll.name
            match = res["MATCH2"]
            self.print_info("Well: {0:30s} - {1: 5.3f}".format(wname, match))
            wlimit = wzong.actions_each["warnthreshold"]
            slimit = wzong.actions_each["stopthreshold"]
            well_warn_limit.append(wlimit)
            well_stop_limit.append(slimit)

            status = "OK"
            if match < wlimit:
                status = "WARN"
            if match < slimit:
                status = "STOP"

            match_all.append(match)
            well_status.append(status)
        else:
            match_all.append(0.0)
            well_warn_limit.append("?")
            well_stop_limit.append("?")
            well_status.append("?")

    # all data (look at averages)
    match_allv = np.array(match_all)
    wlimit = wzong.actions_all["warnthreshold"]
    slimit = wzong.actions_all["stopthreshold"]
    mmean = match_allv.mean()

    well_all.append("SUM_WELLS")
    match_all.append(mmean)
    well_warn_limit.append(wlimit)
    well_stop_limit.append(slimit)

    status = "OK"
    if mmean < wlimit:
        status = "WARN"
    if mmean < slimit:
        status = "STOP"

    well_status.append(status)

    dfr = _make_report(
        self,
        wzong,
        data,
        well_all,
        match_all,
        well_warn_limit,
        well_stop_limit,
        well_status,
    )

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
