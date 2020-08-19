"""The qcforward module"""
from __future__ import absolute_import, division, print_function  # PY2

import sys
from os.path import join
from pathlib import Path
import json
import yaml

from jsonschema import validate
import fmu.tools
from . import _wellzonation_vs_grid as _wzong
from . import _grid_statistics as _gstat


class QCForward(object):
    """
    The QCforward class which has a set of QC functions that can be ran from
    either RMS python, or on disk. The input `data` will be
    somewhat different for the two run environents.

    It should be easy to add new functions to this class. The idea is to reuse
    as much as possible, and principles are:

    * For the client (user), the callings scripts shall be lean

    * All methods shal have a rich documention with examples, i.e. it shall
      be possible for users with less skills in scripting to copy/paste and then modify
      to their needs.

    """

    def __init__(self):
        self._method = None
        self._data = None

        self._verbosity = 0
        self._project = None  # Roxar API project
        self._path = "."

        self._grid = None  # the primary XTGeo Grid() object
        self._gridname = None  # keep track of grid (path) name to avoid double reading
        self._gridzone = None  # the primary XTGeo GridProperty() zone object
        self._gridzonename = None  # keep track of grid zone (path) name

        self._wells = None  # primary list of wells, as XTGeo Wells() object
        self._wlogrun = "log"  # logrun (Roxar API only)
        self._wtrajectory = "Drilled trajectory"  # trajectory (Roxar API)
        self._zonelogname = "Zonelog"  # zone log name for well

    def print_info(self, string):
        """Do print based on verbosity level >= 1"""
        if self._verbosity > 0:
            print("INFO  >>", string)

    def print_debug(self, string):
        """Do debug print based on verbosity level >= 2"""
        if self._verbosity > 1:
            print("DEBUG >>", string)

    @staticmethod
    def give_warn(string):
        """Give warning to user"""
        print("WARN  >>", string)

    def force_stop(self, string):
        """Give stop message to STDERR and stop process"""
        mode = sys.stderr
        print()
        print(
            "QCForward:{} from fmu.tools version: {}".format(
                self._method, fmu.tools.__version__
            )
        )
        print("!" * 70, file=mode)
        print("STOP! >>", string, file=mode)
        print("!" * 70, file=mode)
        print()

        sys.exit(string)

    def handle_data(self, data):
        if isinstance(data, str):
            try:
                with open(data, "r") as stream:
                    xdata = yaml.safe_load(stream)
            except FileNotFoundError as err:
                raise RuntimeError(err)
        else:
            xdata = data.copy()

        if "dump_yaml" in xdata and xdata["dump_yaml"]:
            xdata.pop("dump_yaml", None)
            with open(join(self._path, data["dump_yaml"]), "w") as stream:
                yaml.dump(xdata, stream, default_flow_style=None)
            self.print_info("Dumped YAML to {}".format(data["dump_yaml"]))

        return xdata

    # QC methods:
    # ==================================================================================

    def wellzonation_vs_grid(self, data):
        """Check well zonation or perforations vs 3D grid.

        Args:
            data (dict): This is dictonary telling where data comes from
            dryrun (bool): Just for testing without actually reading data etc.

        """

        self._method = "wellzonation_vs_grid"
        data = self.handle_data(data)
        validate_input("wellzonation_vs_grid.schema", data)

        _wzong.wellzonation_vs_grid(self, data)

    def grid_statistics(self, data):
        """Check grid statistics..."""

        self._method = "grid_statistics"

        _gstat.grid_statistics(self, data)


def validate_input(schema, data):
    schemapath = Path(fmu.tools.__file__).parent / "_schemas"
    with open((schemapath / "wellzonation_vs_grid.schema"), "r") as schemafile:
        schema = json.load(schemafile)
    validate(instance=data, schema=schema)
