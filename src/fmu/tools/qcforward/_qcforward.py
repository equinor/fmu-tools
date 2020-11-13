"""The _qcforward module contains the base class"""

import sys
from os.path import join

import yaml
import pandas as pd

from fmu.tools._common import _QCCommon
from fmu.tools.qcdata import QCData

QCC = _QCCommon()


class QCForward(object):
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
    def gdata(self):
        return self._gdata

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
                with open(data, "r") as stream:
                    xdata = yaml.safe_load(stream)
            except FileNotFoundError as err:
                raise RuntimeError(err)
            data_is_yaml = False
        else:
            xdata = data.copy()

        QCC.verbosity = xdata.get("verbosity", None)

        if data_is_yaml and "dump_yaml" in xdata and xdata["dump_yaml"]:
            xdata.pop("dump_yaml", None)
            with open(join(self._path, data["dump_yaml"]), "w") as stream:
                yaml.safe_dump(
                    xdata,
                    stream,
                    default_flow_style=None,
                )
            QCC.print_info("Dumped YAML to {}".format(data["dump_yaml"]))

        if project:
            xdata["project"] = project
            QCC.print_info("Project type is {}".format(type(project)))

        return xdata

    def make_report(
        self, results: dict, reportfile: str = None, nametag: str = None
    ) -> pd.DataFrame():
        """Make a report which e.g. can be used in webviz plotting"""

        dfr = pd.DataFrame(results).assign(NAMETAG=nametag)

        if reportfile is not None:
            if reportfile in self.reports:
                dfr.to_csv(reportfile, index=False, mode="a", header=None)
            else:
                dfr.to_csv(reportfile, index=False)
                self._reports.append(reportfile)

        return dfr

    def evaluate_qcreport(self, dfr, name):
        """Evalute and do actions on dataframe which contains the gridquality report.

        Args:
            dfr (DataFrame): Pandas dataframe which needs a STATUS column with
                "OK", "WARN" or "STOP"
            name (str): Name of feature is under evaluation, e.g. "grid quality"

        """

        statuslist = ("OK", "WARN", "STOP")

        for status in statuslist:
            dfr_status = dfr[dfr["STATUS"] == status]
            if len(dfr_status) > 0:
                print(f"Status {status} for <{name}> nametag: {self.ldata.nametag})")

                stream = sys.stderr if status == "STOP" else sys.stdout
                print(f"{dfr_status}\n", file=stream)
                if status == "STOP":
                    QCC.force_stop("STOP criteria is found!")

        print(
            "\n== QC forward check {} ({}) finished ==".format(
                self.__class__.__name__, self.ldata.nametag
            )
        )
