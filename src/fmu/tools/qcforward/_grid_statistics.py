"""
This private module in qcforward is used for grid statistics
"""
from typing import Union
import sys
import collections
from pathlib import Path
import json
from jsonschema import validate

import fmu.tools
from fmu.tools.qcproperties.qcproperties import QCProperties

from fmu.tools._common import _QCCommon
from fmu.tools.qcforward._qcforward import QCForward


QCC = _QCCommon()


class _LocalData:
    def __init__(self):
        """Defining and hold data local for this routine"""
        self.actions = None
        self.nametag = None
        self.reportfile = None

    def parse_data(self, data):
        """Parsing the actual data"""
        self.nametag = data.get("nametag", "-")
        self.reportfile = data.get("report", None)
        self.actions = data["actions"]


class GridStatistics(QCForward):
    def run(
        self,
        data: dict,
        project: Union[object, str] = None,
    ):
        """Main routine for evaulating if statistics from 3D grids is
        within user specified thresholds.

        The routine depends on existing fmu.tools functionality for
        extracting property statistics from 3D grids.

        Args:
            data (dict or str): The input data either as a Python dictionary or
                a path to a YAML file
            project (Union[object, str]): For usage inside RMS

        """

        self._data = self.handle_data(data, project)
        # TO-DO:
        # self._validate_input(self._data)

        data = self._data
        QCC.verbosity = data.get("verbosity", 0)

        # parse data that are special for this check
        QCC.print_info("Parsing additional data...")
        self.ldata = _LocalData()
        self.ldata.parse_data(data)

        qcp = QCProperties()

        results = []
        QCC.print_info("Checking status for items in actions...")
        for action in self.ldata.actions:
            # extract parameters from actions and compute statistics
            data_upd = self._extract_parameters_from_action(data, action)
            stat = qcp.get_grid_statistics(
                project=project, data=data_upd, reuse=True, qcdata=self.gdata
            )
            selectors = (
                list(action.get("selectors").values())
                if "selectors" in action
                else None
            )
            # Extract mean value if calculation is not given
            if "calculation" in action:
                calculation = action["calculation"]
            else:
                calculation = "Avg" if action.get("codename") is None else "Percent"

            # Get value from statistics for given property and selectors
            value = stat.get_value(
                action["property"],
                conditions=action.get("selectors"),
                calculation=calculation,
                codename=action.get("codename"),
            )

            status = "OK"
            if "warn_outside" in action:
                if not action["warn_outside"][0] <= value <= action["warn_outside"][1]:
                    status = "WARN"
            if not action["stop_outside"][0] <= value <= action["stop_outside"][1]:
                status = "STOP"

            result = collections.OrderedDict()
            result["PROPERTY"] = action["property"]
            result["SELECTORS"] = f"{selectors}"
            result["FILTERS"] = "yes" if "filters" in action else "no"
            result["CALCULATION"] = calculation
            result["VALUE"] = value
            result["STOP_LIMITS"] = f"{action['stop_outside']}"
            result["WARN_LIMITS"] = (
                f"{action['warn_outside']}" if "warn_outside" in action else "-"
            )
            result["STATUS"] = status
            result["DESCRIPTION"] = action.get("description", "-")

            results.append(result)

        dfr = self.make_report(
            results, reportfile=self.ldata.reportfile, nametag=self.ldata.nametag
        )

        if len(dfr[dfr["STATUS"] == "WARN"]) > 0:
            print(dfr[dfr["STATUS"] == "WARN"])

        if len(dfr[dfr["STATUS"] == "STOP"]) > 0:
            print(dfr[dfr["STATUS"] == "STOP"], file=sys.stderr)
            msg = "One or more actions has status = STOP"
            QCC.force_stop(msg)

        print(
            "\n== QC forward check {} ({}) finished ==".format(
                self.__class__.__name__, self.ldata.nametag
            )
        )

    @staticmethod
    def _validate_input(data):
        """Validate data against JSON schemas"""

        # TODO: complete JSON files
        spath = Path(fmu.tools.__file__).parent / "qcforward" / "_schemas"

        schemafile = "grid_statistics_asfile.json"

        if "project" in data.keys():
            schemafile = "grid_statistics_asroxapi.json"

        with open((spath / schemafile), "r") as thisschema:
            schema = json.load(thisschema)

        validate(instance=data, schema=schema)

    def _extract_parameters_from_action(self, data, action):
        # Function to extract property and selector data from actions
        # and convert to desired input format for QCProperties
        data = data.copy()

        properties = {}
        selectors = []
        filters = {}

        if action["property"] not in properties:
            properties[action["property"]] = {"name": action["property"]}

        if "filters" in action:
            filters = action.get("filters")

        if "selectors" in action:
            for prop, filt in action["selectors"].items():
                if prop not in selectors:
                    selectors.append(prop)
                filters[prop] = {"include": filt}

        data["properties"] = properties
        data["selectors"] = selectors
        data["filters"] = filters

        return data
