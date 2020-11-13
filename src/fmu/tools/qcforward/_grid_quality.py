"""
This private module in qcforward is used to check grid quality
"""

from pathlib import Path
import json
from typing import OrderedDict

from jsonschema import validate
import fmu.tools


from fmu.tools._common import _QCCommon
from fmu.tools.qcdata import QCData
from ._qcforward import QCForward


QCC = _QCCommon()


class _LocalData(object):
    def __init__(self):
        """Defining and hold data local for this routine"""

        self.actions = None
        self.infotext = "GRID QUALITY"
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

        self.actions = data["actions"]


class GridQuality(QCForward):
    def run(self, data, reuse=False, project=None):
        """Main routine for evaluating grid quality and stop/warn if too bad

        The routine depends on existing XTGeo functions for this purpose.

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
        self._validate_input(self._data)

        QCC.verbosity = self._data.get("verbosity", 0)

        # parse data that are special for this check
        QCC.print_info("Parsing additional data...")
        self.ldata = _LocalData()
        self.ldata.parse_data(data)

        if isinstance(self.gdata, QCData):
            self.gdata.parse(data, reuse=reuse)
        else:
            self.gdata = QCData()
            self.gdata.parse(data)

        dfr = self.check_gridquality()
        QCC.print_debug(f"Results: \n{dfr}")

        self.evaluate_qcreport(dfr, "grid quality")

    def check_gridquality(self):
        """
        Given data, do check of gridquality via XTGeo

        Final result will be a table like this:

        GRIDQUALITY        WARNRULE         WARN%   STOPRULE        STOP%  STATUS...

        minangle_top_base  if_>_10%_<_60deg 13.44   if_>_0%_<_40deg 2.32   WARN
        collapsed          if_>_15%         12.25   if_>_30%"       0.0    OK
        """

        # get a list of properties
        gqc = self.gdata.grid.get_gridquality_properties()

        actions = self._data.get("actions", None)
        if actions is None:
            raise ValueError("No actions are defined for grid quality")

        result = OrderedDict()
        result["GRIDQUALITY"] = list()
        result["NO"] = list()
        result["WARNRULE"] = list()
        result["WARN%"] = list()
        result["STOPRULE"] = list()
        result["STOP%"] = list()
        result["STATUS"] = list()

        for prop in gqc.props:

            therules = actions.get(prop.name, None)

            if therules is None:
                continue

            for numrule, therule in enumerate(therules):
                warnrule = therule.get("warn", None)
                stoprule = therule.get("stop", None)
                if stoprule is None or warnrule is None:
                    raise ValueError("Rules for both warn and stop must be defined")

                result["GRIDQUALITY"].append(prop.name)
                result["NO"].append(numrule)

                status = "OK"
                for enum, issue in enumerate([warnrule, stoprule]):

                    mode = "WARN" if enum == 0 else "STOP"

                    theissue = issue.split("_")
                    actualpercent = {}
                    if len(theissue) == 5:
                        criteria = float(theissue[4].strip("deg"))
                        sign = theissue[3]
                        percent = float(theissue[2].strip("%"))
                        psign = theissue[1]

                        ncell = prop.values.count()
                        if sign == "<":
                            nbyrule = (prop.values < criteria).sum()
                        else:
                            nbyrule = (prop.values > criteria).sum()
                        actualpercent[mode] = (nbyrule / ncell) * 100

                    elif len(theissue) == 3:
                        percent = float(theissue[2].strip("%"))
                        psign = theissue[1]

                        ncell = prop.values.count()
                        nbyrule = (prop.values == 1).sum()
                        actualpercent[mode] = (nbyrule / ncell) * 100

                    else:
                        raise ValueError(f"Error in reading the rule: {warnrule}")

                    if mode == "WARN":
                        result["WARN%"].append(actualpercent[mode])
                        result["WARNRULE"].append(warnrule)
                    else:
                        result["STOP%"].append(actualpercent[mode])
                        result["STOPRULE"].append(stoprule)

                    if psign == ">" and actualpercent[mode] > percent:
                        status = mode
                    elif psign == "<" and actualpercent[mode] < percent:
                        status = mode

                result["STATUS"].append(status)

        dfr = self.make_report(
            result, reportfile=self.ldata.reportfile, nametag=self.ldata.nametag
        )
        return dfr

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
