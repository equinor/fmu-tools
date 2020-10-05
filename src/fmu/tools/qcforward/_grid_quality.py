"""
This private module in qcforward is used to check grid quality
"""
from __future__ import absolute_import, division, print_function  # PY2

import sys
from os.path import join
import collections
from pathlib import Path

import json
import numpy as np
import pandas as pd

import fmu.tools
from jsonschema import validate

from ._qcforward_data import _QCForwardData
from ._common import _QCCommon
from ._qcforward import QCForward


QCC = _QCCommon()


class _LocalData(object):  # pylint: disable=too-few-public-methods
    def __init__(self):
        """Defining and hold data local for this routine"""

        self.actions_each = None
        self.actions_all = None
        self.infotext = "GRID QUALITY"

    def parse_data(self, data):
        """Parsing the actual data"""

        # TODO: verify and qc

        self.actions_each = data["actions_each"]
        self.actions_all = data["actions_all"]


class GridQuality(QCForward):
    def run(
        self, data, reuse=False, project=None
    ):  # pylint: disable=too-many-locals, too-many-statements
        """Main routine for evaluating grid quality and stop/warn if too bad

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
        self._data = self.handle_data(data, project)
        # self._validate_input(self._data)

        data = self._data

        QCC.verbosity = data.get("verbosity", 0)

        # parse data that are special for this check
        QCC.print_info("Parsing additional data...")
        self.ldata = _LocalData()
        self.ldata.parse_data(data)

        if isinstance(self.gdata, _QCForwardData):
            self.gdata.parse(data, reuse=reuse)
        else:
            self.gdata = _QCForwardData()
            self.gdata.parse(data)

        # # results are stored in a dict based table which be turned into a Pandas
        # # dataframe in the end (most efficient; then turn into pandas at end)
        # results = collections.OrderedDict(
        #     [
        #         ("WELL", []),
        #         ("MATCH", []),
        #         ("WARN_LIMIT", []),
        #         ("STOP_LIMIT", []),
        #         ("STATUS", []),
        #     ]
        # )
        # results = self._evaluate_per_cell(results)

        # # all data (look at averages)
        # match_allv = np.array(results["MATCH"])
        # wlimit = self.ldata.actions_all["warnthreshold"]
        # slimit = self.ldata.actions_all["stopthreshold"]
        # mmean = np.nanmean(match_allv)

        # results["WELL"].append("ALL_WELLS")
        # results["MATCH"].append(mmean)
        # results["WARN_LIMIT"].append(wlimit)
        # results["STOP_LIMIT"].append(wlimit)

        # status = "OK"
        # if mmean < wlimit:
        #     status = "WARN"
        # if mmean < slimit:
        #     status = "STOP"

        # results["STATUS"].append(status)

        # dfr = self._make_report(results)

        # QCC.print_debug("Results: \n{}".format(dfr))

        # dfr_ok = dfr[dfr["STATUS"] == "OK"]
        # if len(dfr_ok) > 0:
        #     print(
        #         "\nWells with status OK ({} - {})".format(
        #             self.gdata.nametag, self.ldata.infotext
        #         )
        #     )
        #     print(dfr_ok)

        # dfr_warn = dfr[dfr["STATUS"] == "WARN"]
        # if len(dfr_warn) > 0:
        #     print(
        #         "\nWells with status WARN ({} - {})".format(
        #             self.gdata.nametag, self.ldata.infotext
        #         )
        #     )
        #     print(dfr_warn)

        # dfr_stop = dfr[dfr["STATUS"] == "STOP"]
        # if len(dfr_stop) > 0:
        #     print(
        #         "\nWells with status STOP ({} - {})".format(
        #             self.gdata.nametag, self.ldata.infotext
        #         )
        #     )
        #     print(dfr_stop, file=sys.stderr)
        #     msg = "One or more wells has status = STOP"
        #     QCC.force_stop(msg)

        # print(
        #     "\n== QC forward check {} ({}) finished ==".format(
        #         self.__class__.__name__, self.gdata.nametag
        #     )
        # )

    @staticmethod
    def _validate_input(data):
        """Validate data against JSON schemas"""

        # TODO: complete JSON files
        spath = Path(fmu.tools.__file__).parent / "qcforward" / "_schemas"

        schemafile = "gridquality_asfile.json"

        if "project" in data.keys():
            schemafile = "gridquality_asroxapi.json"

        with open((spath / schemafile), "r") as thisschema:
            schema = json.load(thisschema)

        validate(instance=data, schema=schema)

    # def _evaluate_per_well(self, inresults):  # pylint: disable=too-many-locals
    #     """Do a check per well"""

    #     qcdata = self.gdata
    #     wzong = self.ldata

    #     results = inresults.copy()

    #     for wll in qcdata.wells.wells:
    #         QCC.print_debug("Working with well {}".format(wll.name))

    #         dfr = wll.dataframe

    #         if wzong.zonelogname not in dfr.columns:
    #             print(
    #                 "Well {} have no requested zonelog <{}> and will be skipped".format(
    #                     wll.name, wzong.zonelogname,
    #                 )
    #             )
    #             continue

    #         if wzong.perflogname and wzong.perflogname not in dfr.columns:
    #             print(
    #                 "Well {} have no requested perflog <{}> and will be skipped".format(
    #                     wll.name, wzong.perflogname,
    #                 )
    #             )
    #             continue

    #         QCC.print_debug("XTGeo work for {}...".format(wll.name))
    #         res = qcdata.grid.report_zone_mismatch(
    #             well=wll,
    #             zonelogname=wzong.zonelogname,
    #             zoneprop=wzong.gridzone,
    #             zonelogrange=wzong.zonelogrange,
    #             zonelogshift=wzong.zonelogshift,
    #             depthrange=wzong.depthrange,
    #             perflogname=wzong.perflogname,
    #             perflogrange=wzong.perflogrange,
    #             resultformat=2,
    #         )
    #         QCC.print_debug("XTGeo work for {}... done".format(wll.name))

    #         results["WELL"].append(wll.name)

    #         if res:
    #             wname = wll.name
    #             match = res["MATCH2"]
    #             QCC.print_info("Well: {0:30s} - {1: 5.3f}".format(wname, match))
    #             wlimit = wzong.actions_each["warnthreshold"]
    #             slimit = wzong.actions_each["stopthreshold"]
    #             results["WARN_LIMIT"].append(wlimit)
    #             results["STOP_LIMIT"].append(slimit)

    #             status = "OK"
    #             if match < wlimit:
    #                 status = "WARN"
    #             if match < slimit:
    #                 status = "STOP"

    #             results["MATCH"].append(match)
    #             results["STATUS"].append(status)

    #         else:
    #             results["MATCH"].append(float("nan"))
    #             results["WARN_LIMIT"].append(float("nan"))
    #             results["STOP_LIMIT"].append(float("nan"))
    #             results["STATUS"].append(float("nan"))

    #     return results

    # def _make_report(self, results):
    #     """Make a report which e.g. can be used in webviz plotting

    #     Args:
    #         results (dict): Results table

    #     Returns:
    #         A Pandas dataframe
    #     """

    #     dfr = pd.DataFrame(results)
    #     dfr["NAMETAG"] = self.gdata.nametag

    #     if self.gdata.reportfile:
    #         reportfile = join(self._path, self.gdata.reportfile)
    #         if self.gdata.reportmode in ("append", "a"):
    #             dfr.to_csv(reportfile, index=False, mode="a", header=None)
    #         else:
    #             dfr.to_csv(reportfile, index=False)

    #     return dfr
