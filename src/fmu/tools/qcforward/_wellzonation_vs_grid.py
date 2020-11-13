"""
This private module in qcforward is used to check wellzonation vs grid zonation
"""
from __future__ import absolute_import, division, print_function  # PY2

import sys
import collections
from pathlib import Path

import json
from jsonschema import validate
import numpy as np

import fmu.tools
from fmu.tools._common import _QCCommon
from ._qcforward import QCForward


QCC = _QCCommon()


class _LocalData(object):
    def __init__(self):
        """Defining and hold data local for this routine"""

        self.zonelogname = "Zonelog"
        self.zonelogrange = [0, 99]
        self.zonelogshift = 0
        self.depthrange = [0.0, 999999.0]
        self.actions_each = None
        self.actions_all = None
        self.perflogname = None
        self.perflogrange = [1, 9999]
        self.gridzone = None
        self.gridzonerange = [1, 9999]
        self.wellresample = None
        self.infotext = "ZONELOG MATCH"
        self.nametag = None
        self.reportfile = None

    def parse_data(self, data):
        """Parsing the actual data"""

        # TODO: verify and qc
        self.nametag = data.get("nametag", "unset_nametag")
        if "report" in data:
            self.reportfile = (
                data["report"].get("file")
                if isinstance(data["report"], dict)
                else data["report"]
            )

        self.zonelogname = data["zonelog"]["name"]
        self.zonelogrange = data["zonelog"]["range"]
        self.zonelogshift = data["zonelog"].get("shift", 0)

        self.depthrange = data.get("depthrange", [0.0, 99999.0])

        self.actions_each = data["actions_each"]
        self.actions_all = data["actions_all"]
        if "perflog" in data.keys() and data["perflog"]:
            self.perflogname = data["perflog"].get("name", None)
            self.perflogrange = data["perflog"].get("range", [1, 9999])
            self.infotext = "PERFLOG MATCH"
        if "well_resample" in data.keys():
            self.wellresample = data.get("well_resample", None)


class WellZonationVsGrid(QCForward):
    def run(
        self, data, reuse=False, project=None
    ):  # pylint: disable=too-many-locals, too-many-statements
        """Main routine for evaulating well zonation match in 3D grids.

        The routine depends on existing XTGeo functions for this purpose

        Args:
            data (dict or str): The input data either as a Python dictionary or
                a path to a YAML file
            reuse (bool or list): Reusing some "timeconsuming to read" data in the
                instance. If True, then grid and gridprops will be reused as default.
                Alternatively it can be a list for more fine grained control, e.g.
                ["grid", "gridprops", "wells"]
            project (obj or str): For usage inside RMS

        """
        data = self._data = self.handle_data(data, project)
        self._validate_input(self._data)

        # data = self._data

        QCC.verbosity = data.get("verbosity", 0)

        # parse data that are special for this check
        QCC.print_info("Parsing additional data...")
        self.ldata = _LocalData()
        self.ldata.parse_data(data)

        # parsing data stored is self._xxx (general data like grid)
        QCC.print_info("Parsing general data...")
        lognames = [self.ldata.zonelogname]
        if self.ldata.perflogname:
            lognames.append(self.ldata.perflogname)

        wsettings = {
            "lognames": lognames,
            "depthrange": self.ldata.depthrange,
            "rescale": self.ldata.wellresample,
        }

        self.gdata.parse(
            project=project, data=data, reuse=reuse, wells_settings=wsettings
        )

        self.ldata.gridzone = self.gdata.gridprops.props[0]

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

        QCC.print_info("Evaluate per well... {}".format(self.ldata.infotext))

        results = self._evaluate_per_well(results)

        # all data (look at averages)
        match_allv = np.array(results["MATCH"])
        wlimit = self.ldata.actions_all["warn<"]
        slimit = self.ldata.actions_all["stop<"]
        mmean = np.nanmean(match_allv)

        results["WELL"].append("ALL_WELLS")
        results["MATCH"].append(mmean)
        results["WARN_LIMIT"].append(wlimit)
        results["STOP_LIMIT"].append(wlimit)

        status = "OK"
        if mmean < wlimit:
            status = "WARN"
        if mmean < slimit:
            status = "STOP"

        results["STATUS"].append(status)

        dfr = self.make_report(
            results, reportfile=self.ldata.reportfile, nametag=self.ldata.nametag
        )

        QCC.print_debug("Results: \n{}".format(dfr))

        self.evaluate_qcreport(dfr, "well zonation vs grid")

    @staticmethod
    def _validate_input(data):
        """Validate data against JSON schemas"""

        # TODO: complete JSON files
        spath = Path(fmu.tools.__file__).parent / "qcforward" / "_schemas"

        schemafile = "wellzonation_vs_grid_asfile.json"

        if "project" in data.keys():
            schemafile = "wellzonation_vs_grid_asroxapi.json"

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

            if wzong.zonelogname not in dfr.columns:
                print(
                    "Well {} have no requested zonelog <{}> and will be skipped".format(
                        wll.name,
                        wzong.zonelogname,
                    )
                )
                continue

            if wzong.perflogname and wzong.perflogname not in dfr.columns:
                print(
                    "Well {} have no requested perflog <{}> and will be skipped".format(
                        wll.name,
                        wzong.perflogname,
                    )
                )
                continue

            QCC.print_debug("XTGeo work for {}...".format(wll.name))
            res = qcdata.grid.report_zone_mismatch(
                well=wll,
                zonelogname=wzong.zonelogname,
                zoneprop=wzong.gridzone,
                zonelogrange=wzong.zonelogrange,
                zonelogshift=wzong.zonelogshift,
                depthrange=wzong.depthrange,
                perflogname=wzong.perflogname,
                perflogrange=wzong.perflogrange,
                resultformat=2,
            )
            QCC.print_debug("XTGeo work for {}... done".format(wll.name))

            results["WELL"].append(wll.name)

            if res:
                wname = wll.name
                match = res["MATCH2"]
                QCC.print_info("Well: {0:30s} - {1: 5.3f}".format(wname, match))
                wlimit = wzong.actions_each["warn<"]
                slimit = wzong.actions_each["stop<"]
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
