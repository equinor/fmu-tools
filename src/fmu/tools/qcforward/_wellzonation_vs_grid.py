"""
This private module in qcforward is used to check wellzonation vs grid zonation
"""

import collections
import json
from pathlib import Path

import numpy as np
from jsonschema import validate

import fmu.tools
from fmu.tools._common import _QCCommon
from fmu.tools.qcforward._qcforward import ActionsParser, QCForward

QCC = _QCCommon()
UNDEF = float("nan")


class _LocalData:
    def __init__(self):
        """Defining and hold data local for this routine"""

        self.zonelogname = "Zonelog"
        self.zonelogrange = [0, 99]
        self.zonelogshift = 0
        self.depthrange = [0.0, 999999.0]
        self.actions = None
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

        self.actions = data["actions"]

        if "perflog" in data and data["perflog"]:
            self.perflogname = data["perflog"].get("name", None)
            self.perflogrange = data["perflog"].get("range", [1, 9999])
            self.infotext = "PERFLOG MATCH"

        if "well_resample" in data:
            self.wellresample = data.get("well_resample", None)


class WellZonationVsGrid(QCForward):
    def run(self, data, reuse=False, project=None):
        """Main routine for evaulating well zonation match in 3D grids.

        The routine depends on existing XTGeo functions for this purpose

        Args:
            data (dict or str): The input data either as a Python dictionary or
                a path to a YAML file
            reuse (bool or list): Reusing some "timeconsuming to read" data in the
                instance. If True, then grid and gridprops will be reused as default.
                Alternatively it can be a list for more fine grained control, e.g.
                ["grid", "gridprops", "wells"]
            project (Union[object, str]): For usage inside RMS

        """
        data = self._data = self.handle_data(data, project)
        self._validate_input(self._data, project)

        QCC.verbosity = data.get("verbosity", 0)

        # parse data that are special (local) for this check
        QCC.print_info("Parsing additional data...")
        self.ldata = _LocalData()
        self.ldata.parse_data(data)

        # parsing data stored is self._xxx (general data like grid)
        QCC.print_info("Parsing local data...")
        lognames = [self.ldata.zonelogname]
        if self.ldata.perflogname:
            lognames.append(self.ldata.perflogname)

        wsettings = {
            "lognames": lognames,
            "depthrange": self.ldata.depthrange,
            "rescale": self.ldata.wellresample,
        }

        QCC.print_info("Parsing grid, gridprops, .... data...")
        self.gdata.parse(
            project=project, data=data, reuse=reuse, wells_settings=wsettings
        )

        self.ldata.gridzone = self.gdata.gridprops.props[0]

        actions = self._data.get("actions", None)
        if actions is None or not isinstance(actions, list):
            raise ValueError("No actions are defined or wrong data-input for actions")

        # need to evaluate once per well anyway, also of only "all"; this will fill
        # the MATCH% and WELL column in the dataframe given as an OrderedDict
        QCC.print_info("Each well find zonelog match")
        wellmatches = self._evaluate_wells()

        QCC.print_debug(list(wellmatches.keys()))
        QCC.print_debug(list(wellmatches.values()))

        # results are stored in a dict based table which be turned into a Pandas
        # dataframe in the end (most efficient; then turn into pandas at end)
        result = collections.OrderedDict(
            [
                ("WELL", []),
                ("WARNRULE", []),
                ("STOPRULE", []),
                ("MATCH%", []),
                ("STATUS", []),
            ]
        )

        for therule in actions:
            warnrule = ActionsParser(
                therule.get("warn", None), mode="warn", verbosity=QCC.verbosity
            )
            stoprule = ActionsParser(
                therule.get("stop", None), mode="stop", verbosity=QCC.verbosity
            )

            QCC.print_debug(f"WARN RULE {warnrule.status}  {warnrule.expression}")
            QCC.print_debug(f"STOP RULE {stoprule.status}  {stoprule.expression}")

            for well, actualmatch in wellmatches.items():
                status = None
                QCC.print_debug(f"Loop well {well} which has match {actualmatch}")

                for num, issue in enumerate([warnrule, stoprule]):
                    # both issues will be on same line
                    QCC.print_debug(f"Issue no {num} {issue.mode} {issue.expression}")

                    if issue.all and well != "all" or not issue.all and well == "all":
                        continue

                    if status is None:
                        status = "OK"

                    if num == 0:
                        result["WELL"].append(well)
                        result["MATCH%"].append(actualmatch)

                    if issue.status is None:
                        result[issue.mode.upper() + "RULE"].append(UNDEF)
                        status = "OK"
                        continue

                    result[issue.mode.upper() + "RULE"].append(issue.expression)
                    if (issue.compare == ">" and actualmatch > issue.limit) or (
                        issue.compare == "<" and actualmatch < issue.limit
                    ):
                        status = issue.mode.upper()

                if status is not None:
                    result["STATUS"].append(status)

        dfr = self.make_report(
            result, reportfile=self.ldata.reportfile, nametag=self.ldata.nametag
        )
        dfr.set_index("WELL", inplace=True)
        self.evaluate_qcreport(dfr, "well zonation vs grid")

    @staticmethod
    def _validate_input(data, project):
        """Validate data against JSON schemas. TODO complete JSON files"""

        spath = Path(fmu.tools.__file__).parent / "qcforward" / "_schemas"

        schemafile = "wellzonation_vs_grid_asfile.json"

        if project:
            schemafile = "wellzonation_vs_grid_asroxapi.json"

        with open((spath / schemafile), "r", encoding="utf-8") as thisschema:
            schema = json.load(thisschema)

        validate(instance=data, schema=schema)

    def _evaluate_wells(self):
        """Do a check per well and the sum; return an Ordered Dict"""

        wells = []
        matches = []

        for wll in self.gdata.wells.wells:
            QCC.print_debug(f"Working with well {wll.name}")

            dfr = wll.dataframe

            if self.ldata.zonelogname not in dfr.columns:
                print(
                    "Well {} have no requested zonelog <{}> and will be skipped".format(
                        wll.name,
                        self.ldata.zonelogname,
                    )
                )
                continue

            if self.ldata.perflogname and self.ldata.perflogname not in dfr.columns:
                print(
                    "Well {} have no requested perflog <{}> and will be skipped".format(
                        wll.name,
                        self.ldata.perflogname,
                    )
                )
                continue

            QCC.print_debug(f"XTGeo work for {wll.name}...")
            res = self.gdata.grid.report_zone_mismatch(
                well=wll,
                zonelogname=self.ldata.zonelogname,
                zoneprop=self.ldata.gridzone,
                zonelogrange=self.ldata.zonelogrange,
                zonelogshift=self.ldata.zonelogshift,
                depthrange=self.ldata.depthrange,
                perflogname=self.ldata.perflogname,
                perflogrange=self.ldata.perflogrange,
                resultformat=2,
            )
            QCC.print_debug(f"XTGeo work for {wll.name}... done")

            wells.append(wll.name)

            if res:
                matches.append(res["MATCH2"])

            else:
                matches.append(UNDEF)

        # finally averages, for "all" results
        match_allv = np.array(matches)
        mmean = np.nanmean(match_allv)
        wells.append("all")
        matches.append(mmean)

        return collections.OrderedDict(zip(wells, matches))
