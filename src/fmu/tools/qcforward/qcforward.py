"""The qcforward module"""

import sys

from . import _wellzonation_vs_grid as _wzong
from . import _grid_statistics as _gstat


class QCForward(object):
    """
    The QCforward class which has a set of QC functions that can be ran from
    either RMS python, or on disk. The input `data` will be
    somewhat different for the two run environents.
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

    @staticmethod
    def force_stop(string):
        """Give stop message and stop process"""
        print("STOP! >>", string)
        sys.exit(string)

    def wellzonation_vs_grid(self, data, dryrun=False):
        """Check well zonation or perforations vs 3D grid.

        Args:
            data (dict): This is dictonary telling where data comes from
            dryrun (bool): Just for testing without actually reading data etc.

        """

        self._method = "wellzonation_vs_grid"

        _wzong.wellzonation_vs_grid(self, data, dryrun=dryrun)

    def grid_statistics(self, data):
        """Check grid statistics..."""

        self._method = "grid_statistics"

        _gstat.grid_statistics(self, data)
