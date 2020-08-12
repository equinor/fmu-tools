"""
This private module in qcforward is used to check wellzonation vs grid
"""

import collections
import numpy as np
import pandas as pd
from . import _parse_data

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
    report = (None, "write")

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
        report = tuple(data["report"])

    wzong = WZong(
        zonelogrange=zonelogrange,
        depthrange=depthrange,
        actions_each=actions_each,
        actions_all=actions_all,
        report=report,
    )

    return wzong


def wellzonation_vs_grid(self, data, dryrun=False):

    # parsing data stored is self._xxx (general data like grid)
    self.print_info("Parsing data...")
    _parse_data.parse(self, data)

    # parse data that are special for this check
    self.print_info("Parsing additional data...")
    wzong = _parse_wzong(data)

    if dryrun:
        self.print_info("Dryrun only, not much done, return")
        return

    match_all = []
    well_all = []
    well_warn = []
    well_stop = []

    for wll in self._wells.wells:
        self.print_debug("Working with well {}".format(wll.name))

        res = self._grid.report_zone_mismatch(
            well=wll,
            zonelogname=self._zonelogname,
            zoneprop=self._gridzone,
            zonelogrange=wzong.zonelogrange,
            depthrange=[1300, 9999],
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
            well_warn.append(wlimit)
            well_stop.append(slimit)

            if match < wlimit:
                self.give_warn(
                    "Well {} has zonelogmatch = {} < {}".format(wname, match, wlimit)
                )

            if match < slimit:
                msg = "Well {} has zonelogmatch = {} < {}".format(wname, match, slimit)
                self.force_stop(
                    "Well {} has zonelogmatch = {} < {}".format(wname, match, slimit)
                )

            match_all.append(match)
        else:
            match_all.append(0.0)
            well_warn.append("?")
            well_stop.append("?")

    # all data (look at averages)
    match_allv = np.array(match_all)
    wlimit = wzong.actions_all["warnthreshold"]
    slimit = wzong.actions_all["stopthreshold"]
    mmean = match_allv.mean()

    well_all.append("SUM_WELLS")
    match_all.append(mmean)
    well_warn.append(wlimit)
    well_stop.append(slimit)

    self.print_debug("Results:")

    if wzong.report[0]:
        res = collections.OrderedDict()
        res["WELL"] = well_all
        res["MATCH"] = match_all
        res["WARN_LIMIT"] = well_warn
        res["STOP_LIMIT"] = well_stop

        dfr = pd.DataFrame(res)
        if wzong.report[1] == "append":
            dfr.to_csv(wzong.report[0], mode="a", header=None)
        else:
            dfr.to_csv(wzong.report[0])

    if mmean < wlimit:
        self.give_warn("Well average zonelogmatch = {} < {}".format(mmean, wlimit))

    if mmean < slimit:
        msg = "Well average zonelogmatch = {} < {}".format(mmean, slimit)
        self.force_stop(msg)
