"""
This private module in qcforward is used to check wellzonation vs grid
"""

from warnings import warn
import collections
import numpy as np
from . import _parse_data

WZong = collections.namedtuple(
    "WZong", "zonelogrange depthrange actions_each actions_all"
)


def _parse_wzong(data):
    """Parse ande check data local to this routine, return a named tuple"""

    # defaults:
    zonelogrange = (1, 99)
    depthrange = (0, 9999)
    actions_each = {"warnthreshold": 99, "stopthreshold": 50}
    actions_all = ({"warnthreshold": 99, "stopthreshold": 88},)

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

    wzong = WZong(
        zonelogrange=zonelogrange,
        depthrange=depthrange,
        actions_each=actions_each,
        actions_all=actions_all,
    )

    return wzong


def wellzonation_vs_grid(self, data):

    # parsing data stored is self._xxx (general data like grid)
    _parse_data.parse(self, data)

    # parse data that are special for this check
    wzong = _parse_wzong(data)

    match_all = []

    for wll in self._wells.wells:

        res = self._grid.report_zone_mismatch(
            well=wll,
            zonelogname=data["zonelogname"],
            zoneprop=self._gridzone,
            zonelogrange=wzong.zonelogrange,
            depthrange=[1300, 9999],
            resultformat=2,
        )

        if res:
            wname = wll.name
            match = res["MATCH2"]
            self.print_info("Well: {0:30s} - {1: 5.3f}".format(wname, match))
            wlimit = wzong.actions_each["warnthreshold"]
            slimit = wzong.actions_each["stopthreshold"]

            if match < wlimit:
                self.give_warn(
                    "Well {} has zonelogmatch = {} < {}".format(wname, match, wlimit),
                )

            if match < slimit:
                msg = "Well {} has zonelogmatch = {} < {}".format(wname, match, slimit)
                self.force_stop(
                    "Well {} has zonelogmatch = {} < {}".format(wname, match, wlimit),
                )

            match_all.append(match)

    # all data (look at averages)
    match_all = np.array(match_all)
    wlimit = wzong.actions_all["warnthreshold"]
    slimit = wzong.actions_all["stopthreshold"]
    mmean = match_all.mean()

    if mmean < wlimit:
        self.give_warn("Well average zonelogmatch = {} < {}".format(mmean, wlimit))

    if mmean < slimit:
        msg = "Well average zonelogmatch = {} < {}".format(mmean, slimit)
        self.force_stop(msg)
