"""
This private module in qcforward is used for grid statistics
"""

import collections
import json
from pathlib import Path
from typing import Dict, Optional, Union

import pandas as pd
from jsonschema import validate

import fmu.tools
from fmu.tools._common import _QCCommon
from fmu.tools.qcforward._qcforward import QCForward
from fmu.tools.qcproperties.qcproperties import QCProperties

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
        data: Union[dict, str],
        project: Optional[Union[object, str]] = None,
    ) -> None:
        """Main routine for evaulating if statistics from 3D grids is
        within user specified thresholds.

        The routine depends on existing fmu.tools functionality for
        extracting property statistics from 3D grids.

        Args:
            data (dict or str): The input data either as a Python dictionary or
                a path to a YAML file
            project (Union[object, str]): For usage inside RMS

        """

        self._data: dict = self.handle_data(data, project)
        # TO-DO:
        # self._validate_input(self._data)

        data = self._data
        QCC.verbosity = data.get("verbosity", 0)

        # parse data that are special for this check
        QCC.print_info("Parsing additional data...")
        self.ldata = _LocalData()
        self.ldata.parse_data(data)

        dfr = self.check_gridstatistics(project, data)
        QCC.print_debug(f"Results: \n{dfr}")

        self.evaluate_qcreport(dfr, "grid statistics")

    def check_gridstatistics(self, project, data):
        """
        Extract statistics per action and check if property value is
        within user specified limits.

        Returns a dataframe with results
        """

        qcp = QCProperties()

        results = []
        QCC.print_info("Checking status for items in actions...")
        for action in self.ldata.actions:
            # extract parameters from actions
            data_upd = self._extract_parameters_from_action(data, action)

            selectors, calculation = self._get_selecors_and_calculation(action)

            # Create datframe with statistics
            dframe = qcp.get_grid_statistics(project=project, data=data_upd)

            # Get value from statistics for given property and selectors
            value = self._get_statistical_value(
                dframe, action["property"], calculation, selectors
            )

            status = "OK"
            if (
                "warn_outside" in action
                and not action["warn_outside"][0] <= value <= action["warn_outside"][1]
            ):
                status = "WARN"
            if not action["stop_outside"][0] <= value <= action["stop_outside"][1]:
                status = "STOP"

            result = collections.OrderedDict()
            result["PROPERTY"] = action["property"]
            result["SELECTORS"] = f"{list(selectors.values())}"
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

        return self.make_report(
            results, reportfile=self.ldata.reportfile, nametag=self.ldata.nametag
        )

    @staticmethod
    def _validate_input(data: dict):
        """Validate data against JSON schemas"""

        # TODO: complete JSON files
        spath = Path(fmu.tools.__file__).parent / "qcforward" / "_schemas"

        schemafile = "grid_statistics_asfile.json"

        if "project" in data:
            schemafile = "grid_statistics_asroxapi.json"

        with open((spath / schemafile), "r", encoding="utf-8") as thisschema:
            schema = json.load(thisschema)

        validate(instance=data, schema=schema)

    @staticmethod
    def _extract_parameters_from_action(data: dict, action: Dict[str, dict]) -> dict:
        """
        Extract property and selector data from actions
        and convert to desired input format for QCProperties
        """
        data = data.copy()

        properties: dict = {}
        selectors: list = []
        filters: dict = {}

        if action["property"] not in properties:
            properties[action["property"]] = {"name": action["property"]}

        if "filters" in action:
            filters = action["filters"]

        if "selectors" in action:
            for prop, filt in action["selectors"].items():
                if prop not in selectors:
                    selectors.append(prop)
                filters[prop] = {"include": filt}

        data["properties"] = properties
        data["selectors"] = selectors
        data["filters"] = filters

        return data

    @staticmethod
    def _get_selecors_and_calculation(action: dict) -> tuple:
        """
        Get selectors and selected calculation from the action.
        If a discrete property has been input it is added to the selctors.
        If calculation is not specified a default is set.
        """
        selectors = action.get("selectors", {})
        if "codename" in action:
            selectors.update({action["property"]: action["codename"]})
        calculation = action.get("calculation", "Avg")
        return selectors, calculation

    @staticmethod
    def _get_statistical_value(
        dframe: pd.DataFrame,
        prop: str,
        calculation: str,
        selectors: Optional[dict] = None,
    ) -> float:
        """
        Retrive statistical value from the property statistic dataframe
        """

        dframe = dframe[dframe["PROPERTY"] == prop].copy()

        if selectors is not None:
            for selector, value in selectors.items():
                dframe = dframe[dframe[selector] == value]

        if len(dframe.index) > 1:
            print(dframe)
            raise Exception("Ambiguous result, multiple rows meet conditions")

        return dframe.iloc[0][calculation]
