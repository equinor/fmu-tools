"""
The qcforward module contain the QCforward class which has a set of functions
that can be ran from either RMS python, or on disk. The input will be
similar in such cases, excpet for the `data` key which will differ.
"""

import sys

from . import _wellzonation_vs_grid as _wzong
from . import _grid_statistics as _gstat


class QCForward(object):
    def __init__(self):
        self._method = None
        self._data = None
        self._verbosity = 0
        self._project = None  # Roxar API project

        self._path = "."
        self._grid = None  # the primary XTGeo Grid() object
        self._gridzone = None  # the primary XTGeo GridProperty() zone object
        self._wells = None  # primary list of wells, as XTGeo Wells() object

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

    def wellzonation_vs_grid(self, data):
        """Check well zonation or perforations vs 3D grid.

        Args:
            data {dict}: This is dictonary telling where data comes from

        """

        self._method = "wellzonation_vs_grid"

        _wzong.wellzonation_vs_grid(self, data)

    def grid_statistics(self, data):
        """Check grid statistics..."""

        self._method = "grid_statistics"

        _gstat.grid_statistics(self, data)
