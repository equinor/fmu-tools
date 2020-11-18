"""
This private module in qcforward is used to check grid quality
"""

from pathlib import Path
import json
from collections import OrderedDict

from jsonschema import validate
import fmu.tools


from fmu.tools._common import _QCCommon
from fmu.tools.qcdata import QCData
from ._qcforward import QCForward, ActionsParser


QCC = _QCCommon()

UNDEF = "na"


class _LocalData(object):
    def __init__(self):
        """Defining and hold data local for this routine"""

        self.actions = None
        self.infotext = "GRID QUALITY"
        self.nametag = None
        self.reportfile = None
        self.writeicon = False

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
        self.writeicon = data.get("writeicon", False)


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
            self.gdata.parse(data=data, reuse=reuse, project=project)
        else:
            self.gdata = QCData()
            self.gdata.parse(data)

        dfr = self.check_gridquality(project)
        QCC.print_debug(f"Results: \n{dfr}")

        self.evaluate_qcreport(dfr, "grid quality")

    def check_gridquality(self, project):
        """
        Given data, do check of gridquality via XTGeo

        Final result will be a table like this:

        GRIDQUALITY        WARNRULE         WARN%   STOPRULE        STOP%  STATUS...

        minangle_top_base  allcells>10%<60  13.44   allcells>0%<40  2.32   WARN
        collapsed          allcells>15%     12.25   allcells>30%    0.0    OK
        """

        # get a list of properties
        gqc = self.gdata.grid.get_gridquality_properties()

        actions = self._data.get("actions", None)
        if actions is None:
            raise ValueError("No actions are defined for grid quality")

        result = OrderedDict(
            [
                ("GRIDQUALITY", []),
                ("WARNRULE", []),
                ("WARN%", []),
                ("STOPRULE", []),
                ("STOP%", []),
                ("STATUS", []),
            ]
        )

        for prop in gqc.props:

            therules = actions.get(prop.name, None)

            if self._ldata.writeicon and project and therules is not None:
                QCC.print_info(f"Write icon for {prop.name}")
                prop.to_roxar(project, self._data["grid"], prop.name)

            if therules is None:
                continue

            for numrule, therule in enumerate(therules):

                warnrule = ActionsParser(
                    therule.get("warn", None), mode="warn", verbosity=QCC.verbosity
                )
                stoprule = ActionsParser(
                    therule.get("stop", None), mode="stop", verbosity=QCC.verbosity
                )

                QCC.print_debug(f"WARN RULE {warnrule.status}")
                QCC.print_debug(f"STOP RULE {stoprule.status}")

                # if stoprule is None or warnrule is None:
                #     raise ValueError("Rules for both warn and stop must be defined")

                result["GRIDQUALITY"].append(f"{prop.name}[{numrule}]")

                status = "OK"
                for issue in [warnrule, stoprule]:

                    if issue.status is None:
                        result[issue.mode.upper() + "%"].append(UNDEF)
                        result[issue.mode.upper() + "RULE"].append(UNDEF)
                        status = "OK"
                        continue

                    ncell = prop.values.count()

                    if issue.given == "<":
                        nbyrule = (prop.values < issue.criteria).sum()
                    elif issue.given == ">":
                        nbyrule = (prop.values > issue.criteria).sum()
                    else:
                        nbyrule = (prop.values > 0).sum()

                    actualpercent = 100.0 * nbyrule / ncell

                    result[issue.mode.upper() + "%"].append(actualpercent)
                    result[issue.mode.upper() + "RULE"].append(issue.expression)

                    if issue.compare == ">" and actualpercent > issue.limit:
                        status = issue.mode.upper()
                    elif issue.compare == "<" and actualpercent < issue.limit:
                        status = issue.mode.upper()
                    else:
                        status = "OK"

                result["STATUS"].append(status)

        dfr = self.make_report(
            result, reportfile=self.ldata.reportfile, nametag=self.ldata.nametag
        )
        dfr.set_index("GRIDQUALITY", inplace=True)
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
