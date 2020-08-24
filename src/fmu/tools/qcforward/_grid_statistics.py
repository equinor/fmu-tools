"""
This private module in qcforward is used for grid statistics
"""

import sys
from pathlib import Path
import json
from jsonschema import validate

import pandas as pd

import fmu.tools
from fmu.tools.qcproperties._propstat import PropStat
from fmu.tools.qcproperties._propstat_parameter_data import PropStatParameterData

from ._qcforward_data import _QCForwardData
from ._common import _QCCommon
from ._qcforward import QCForward


QCC = _QCCommon()


class _LocalData(object):
    def __init__(self):
        """Defining and hold data local for this routine"""
        self.pdata = None
        self.actions = None
        self.parameters = None

    def parse_data(self, data, project):
        """Parsing the actual data"""

        self.actions = data["actions"]

        properties, selectors, filters = self.extract_parameters_from_actions()

        self.pdata = PropStatParameterData(
            properties=properties, selectors=selectors, additional_filters=filters
        )

        self.parameters = self.pdata.params

        if project is None:
            self.parameters = [[None, param] for param in self.parameters]

    def extract_parameters_from_actions(self):
        # Function to extract property and selector data from actions
        # and convert to desired input format for PropStatParameterData
        properties = []
        selectors = []
        filters = {}

        for action in self.actions:

            if action["property"] not in properties:
                properties.append(action["property"])

            if action.get("filters") is not None:
                filters = action.get("filters")

            if action.get("selectors") is not None:
                for selector, filt in action["selectors"].items():
                    if selector not in selectors:
                        selectors.append(selector)
                        filters[selector] = {"include": [filt]}
                    else:
                        if filt not in filters[selector]["include"]:
                            filters[selector]["include"].append(filt)

        return properties, selectors, filters


class GridStatistics(QCForward):
    def run(self, data, reuse=False, project=None):
        """Main routine for evaulating if statistics from 3D grids is
        within user specified thresholds.

        The routine depends on existing fmu.tools functionality for
        extracting property statistics from 3D grids.

        Args:
            data (dict or str): The input data either as a Python dictionary or
                a path to a YAML file
            project (obj or str): For usage inside RMS

        """
        self._data = self.handle_data(data, project)
        # self._validate_input(self._data)

        data = self._data

        QCC.verbosity = data.get("verbosity", 0)

        # parse data that are special for this check
        QCC.print_info("Parsing additional data...")
        self.ldata = _LocalData()
        self.ldata.parse_data(data, project)

        # the gridprops argument defines what parameters are loaded to XTGeo
        data["gridprops"] = self.ldata.parameters

        # parsing data stored is self._xxx (general data like grid)
        QCC.print_info("Parsing general data...")
        if isinstance(self.gdata, _QCForwardData):
            self.gdata.parse(data, reuse=reuse)
        else:
            self.gdata = _QCForwardData()
            self.gdata.parse(data)

        # Compute dataframe with statistics
        stat = PropStat(
            parameter_data=self.ldata.pdata,
            xtgeo_object=self.gdata.gridprops,
        )

        results = []
        for action in self.ldata.actions:

            selectors = (
                list(action.get("selectors").values())
                if "selectors" in action
                else None
            )

            # Extract mean value if calculation is not given
            calculation = (
                action.get("calculation") if "calculation" in action else "Avg"
            )

            # Get value from statistics for given property and selectors
            value = stat.get_value(
                action["property"],
                conditions=action.get("selectors"),
                calculation=calculation,
            )

            status = "OK"
            if "warn_outside" in action:
                if not action["warn_outside"][0] <= value <= action["warn_outside"][1]:
                    status = "WARN"
            if not action["stop_outside"][0] <= value <= action["stop_outside"][1]:
                status = "STOP"

            results.append(
                {
                    "PROPERTY": action["property"],
                    "VALUE": value,
                    "CALCULATION": calculation,
                    "STATUS": status,
                    "STOP_LIMITS": f"{action['stop_outside']}",
                    "WARN_LIMITS": f"{action['warn_outside']}"
                    if "warn_outside" in action
                    else "NA",
                    "SELECTORS": f"{selectors}",
                    "FILTERS": "yes" if "filters" in action else "no",
                }
            )

        dfr = self._make_report(results)

        if len(dfr[dfr["STATUS"] == "WARN"]) > 0:
            print(dfr[dfr["STATUS"] == "WARN"])

        if len(dfr[dfr["STATUS"] == "STOP"]) > 0:
            print(dfr[dfr["STATUS"] == "STOP"], file=sys.stderr)
            msg = "One or more actions has status = STOP"
            QCC.force_stop(msg)

        print(
            "\n== QC forward check {} ({}) finished ==".format(
                self.__class__.__name__, self.gdata.nametag
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

    def _make_report(self, results):
        """Make a report which e.g. can be used in webviz plotting

        Args:
            results (dict): Results table

        Returns:
            A Pandas dataframe
        """
        dfr = pd.DataFrame(results)
        # set column order
        dfr = dfr[
            [
                "PROPERTY",
                "SELECTORS",
                "FILTERS",
                "CALCULATION",
                "VALUE",
                "WARN_LIMITS",
                "STOP_LIMITS",
                "STATUS",
            ]
        ]
        dfr["NAMETAG"] = self.gdata.nametag
        if self.gdata.reportfile is not None:
            reportfile = Path(self._path) / self.gdata.reportfile
            if self.gdata.reportmode == "append":
                dfr.to_csv(reportfile, index=False, mode="a", header=None)
            else:
                dfr.to_csv(reportfile, index=False)

        return dfr
