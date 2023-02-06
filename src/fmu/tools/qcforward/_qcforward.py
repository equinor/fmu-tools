"""The _qcforward module contains the base class"""

import sys
from copy import deepcopy
from os.path import join
from typing import Optional

import pandas as pd
import yaml

from fmu.tools._common import _QCCommon
from fmu.tools.qcdata import QCData

QCC = _QCCommon()


class QCForward:
    """
    The QCforward base class which has a set of QC functions that can be ran from
    either RMS python, or on disk. The input `data` will be
    somewhat different for the two run environents.

    It should be easy to add new functions to this class. The idea is to reuse
    as much as possible, and principles are:

    * For the client (user), the calling scripts shall be lean

    * All methods shall have a rich documention with examples, i.e. it shall
      be possible for users with less skills in scripting to copy/paste and then modify
      to their needs.

    """

    def __init__(self):
        self._method = None
        self._data = None  # input data dictionary
        self._path = "."
        self._gdata = QCData()  # QCData instance, stores XTGeo data
        self._ldata = None  # special data instance, for local data parsed per method
        self._reports = []  # List of all report, used to determin write/append mode

    @property
    def reports(self):
        return self._reports

    @reports.setter
    def reports(self, data):
        self._reports = data

    @property
    def data(self):
        """The input data dictionary"""
        return self._data

    @property
    def gdata(self):
        """A QCData() instance"""
        return self._gdata

    @gdata.setter
    def gdata(self, obj):
        """A QCData() instance"""
        if not isinstance(obj, QCData):
            raise TypeError("Wrong type of object, shall be QCData")
        self._gdata = obj

    @property
    def ldata(self):
        return self._ldata

    @ldata.setter
    def ldata(self, data):
        self._ldata = data

    def handle_data(self, data, project):
        data_is_yaml = True

        # data may be a yaml file
        if isinstance(data, str):
            try:
                with open(data, "r", encoding="utf-8") as stream:
                    xdata = yaml.safe_load(stream)
            except FileNotFoundError as err:
                raise RuntimeError from err
            data_is_yaml = False
        else:
            xdata = data.copy()

        QCC.verbosity = xdata.get("verbosity", None)

        if data_is_yaml and "dump_yaml" in xdata and xdata["dump_yaml"]:
            xdata.pop("dump_yaml", None)
            with open(
                join(self._path, data["dump_yaml"]), "w", encoding="utf-8"
            ) as stream:
                yaml.safe_dump(
                    xdata,
                    stream,
                    default_flow_style=None,
                )
            QCC.print_info(f"Dumped YAML to {data['dump_yaml']}")

        xdata["project"] = None
        if project:
            xdata["project"] = project
            QCC.print_info(f"Project type is {type(project)}")

        return xdata

    def make_report(
        self,
        results: dict,
        reportfile: Optional[str] = None,
        nametag: Optional[str] = None,
    ) -> pd.DataFrame:
        """Make a report which e.g. can be used in webviz plotting"""

        dfr = pd.DataFrame(results).assign(NAMETAG=nametag)

        if reportfile is not None:
            if reportfile in self.reports:
                dfr.to_csv(reportfile, index=False, mode="a", header=None)
            else:
                dfr.to_csv(reportfile, index=False)
                self._reports.append(reportfile)

        return dfr

    def evaluate_qcreport(self, dfr, name, stopaction=True) -> str:
        """Evalute and do actions on dataframe which contains the gridquality report.

        Action is done here if keyword action is True; otherwise the caller must decide
        upon action dependent on return status.

        Args:
            dfr (DataFrame): Pandas dataframe which needs a STATUS column with "OK",
                "WARN" or "STOP"
            name (str): Name of feature is under evaluation, e.g. "grid
                quality"
            stopaction(bool): If True and a STOP status is found, then a force_stop
                is done here, otherwise the status is returned and the caller need
                to to care of any actions.

        Returns:
            The string "STOP" or "CONTINUE" unless action is True and STOP is found
            and the result dataframe
        """
        statuslist = ("OK", "WARN", "STOP")

        dfr_status = None
        for status in statuslist:
            dfr_status = dfr[dfr["STATUS"] == status]
            if len(dfr_status) > 0:
                print(f"Status {status} for <{name}> nametag: {self.ldata.nametag})")

                stream = sys.stderr if status == "STOP" else sys.stdout

                dfr_status_print = dfr_status.to_string()
                print(f"{dfr_status_print}\n", file=stream)
                if status == "STOP":
                    if stopaction:
                        QCC.force_stop("STOP criteria is found!")
                    return status
        print(
            f"\n== QC forward check {self.__class__.__name__} "
            f"{self.ldata.nametag}) finished =="
        )

        return "CONTINUE"


class ActionsParser:
    def __init__(self, rule, mode="warn", verbosity="info"):
        QCC.verbosity = verbosity
        self.status = None  # in case no rule is set
        self.all = True
        self.compare = ">"
        self.limit = 90
        self.given = "<"
        self.criteria = 50
        self.mode = mode
        self.expression = "UNDEF"

        QCC.print_debug(f"Parse action: {rule}")

        if rule:
            self.parse(rule)

    def parse(self, rule):
        """Parse a rule given for an action.

        Args:
            rule (str): An expression on form "eachwell < 90%" or
                "allcells < 80% when > 99"

        """

        items = rule.split()
        self.status = "rule"
        self.expression = rule.replace(" ", "")

        if len(items) == 6:
            # 'all > 3% when < 20'
            self.all = "all" in items[0]
            self.compare = items[1]
            self.limit = float(items[2].replace("%", ""))
            self.given = items[4]
            self.criteria = float(items[5])

        elif len(items) == 3:
            self.all = "all" in items[0]
            self.compare = items[1]
            self.limit = float(items[2].replace("%", ""))
            self.given = ""
            self.criteria = ""

        else:
            raise ValueError(f"Input is wrong somehow: {rule}")

        key = "all" if self.all else "any"
        self.expression = key + self.compare + str(self.limit) + "%"
        if self.given:
            self.expression += "ifx" + self.given + str(self.criteria)


def actions_validator(actionsin: dict) -> dict:
    """General function to validate that the 'actions' input is on the correct form.

    The typical form is::

        "actions": [
            {"warn": "anywell < 80%", "stop": "anywell < 75%"},
            {"warn": "allwells < 90%", "stop": "allwells < 85%"},
        ],

    Several checks can be implemented; currently many is in a to-do state.

    Args:
        actionsin: Input actions record

    Returns:
        An actions python dictionary (potentially processed)
    """

    actions = deepcopy(actionsin)

    if not isinstance(actions, list):
        raise ValueError("The actions input must be a list")

    if len(actions) != 2:
        raise ValueError("The actions input must be a list with two element")

    # check each line to see if the rules seems logical
    anyhit = False
    allhit = False
    for elem in actions:
        if not set(elem.keys()).issubset(["warn", "stop"]):
            raise ValueError(
                "Both criteria 'warn' and 'stop' are required in actions! "
                f"You have keys: {list(elem.keys())}"
            )
        vals = list(elem.values())
        if "any" in str(vals) and "all" in str(vals):
            # avoid that one entry mixes all and any
            raise ValueError(
                "Seems wrong to mix 'all' and 'any' in one line which is not allowed"
            )
        if "any" in str(vals):
            anyhit = True
        if "all" in str(vals):
            allhit = True

    if not (anyhit and allhit):
        raise ValueError(
            f"One of 'any' or 'all' is missing in the actions input: {actions}"
        )

    return actions
