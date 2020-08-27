"""
This private module in qcforward is used to parse data on a general level.

The resulting data will be stored as class instance attributes, e.g. self._grid

"""
from os.path import join
from glob import glob
import re

import xtgeo
from . import _common

CMN = _common._QCCommon()


class _QCForwardData(object):
    """
    This is a local class which parse/reads and stores some common data
    like 3D grids, maps etc for all QCForward methods.

    It shall be semi-agnostic to where data comes from, i.e. accept both files
    and RMS input.

    By having it as a class one can store different datasets and compare them later
    if needed. E.g. if one need to compare two grid models, they will be members
    of two different instances of the _QCForwardData()
    """

    def __init__(self):

        # if this is active, then heavy stuff such as grids are not read again
        self._reuse = []

        self._path = "."  # usually not needed to set explisit
        self._project = None  # pointing to  RMS project ID if any
        self._grid = None  # A XTGeo Grid()
        self._gridprops = None  # XTGeo GridProperties() for multiple props

        self._wells = None  # XTGeo Wells() instance (multiple wells)
        self._wells_lognames = "all"
        self._wells_depthrange = None
        self._wells_rescale = None

        self._surfaces = None  # XTGeo Surfaces() instance (in prep)

        self._reportfile = "default.csv"  # report file settings
        self._reportmode = "write"  # report file settings
        self._nametag = "unset_nametag"

        self._data = None

    @property
    def path(self):
        """Path settings"""
        return self._path

    @property
    def project(self):
        """Project attribute as Roxar project instance"""
        return self._project

    @property
    def grid(self):
        """Grid attribute as XTGeo Grid() instance"""
        return self._grid

    @property
    def gridprops(self):
        """GridProperties attribute as XTGeo GridProperties() instance"""
        return self._gridprops

    @property
    def wells(self):
        """Wells attribute as XTGeo Wells() instance"""
        return self._wells

    @property
    def reportfile(self):
        """dict:: Report file settings"""
        return self._reportfile

    @property
    def reportmode(self):
        """dict:: Report mode settings"""
        return self._reportmode

    @property
    def nametag(self):
        """str:: Nametag for data set"""
        return self._nametag

    @staticmethod
    def _unpack_dict1(mydict):
        """Unpack elements from a dict with one pair"""
        if len(mydict) != 1 or not isinstance(mydict, dict):
            raise ValueError("Incorrect input to _unpack_dict1")

        key = list(mydict.keys())[0]
        value = list(mydict.values())[0]
        return key, value

    def parse(self, data, reuse=False, wells_settings=None):
        """Parse the actual data, such as grids, gridprops etc.

        Args:
            data (dict): The input data dictionary
            reuse (bool or list): If True, do not reread grid and gridprops. Can also be
                a list referring to key names.
            wells_settings (dict): More granular settings for wells which may speed
                up reading and/or execution. If set, this is a dictionary with keys
                ``lognames``, ``depthrange``, ``resample``

        Example::

            wsettings = {"lognames": "all", "depthrange": (1300, 2800), resample=1.0}
            self.gdata.parse(data, wells_settings=wsettings)

        """
        CMN.verbosity = data.get("verbosity", None)

        if isinstance(reuse, bool):
            if reuse is True:
                self._reuse = ["grid", "gridprops"]
            else:
                self._reuse = []
        else:
            self._reuse = reuse

        if wells_settings:
            self._wells_lognames = wells_settings.get("lognames", "all")
            self._wells_depthrange = wells_settings.get("depthrange", None)
            self._wells_rescale = wells_settings.get("rescale", None)

        self._data = data

        self.set_path()
        self.set_report()
        self.set_nametag()
        self.parse_project()
        self.read_grid()
        self.read_gridprops()
        self.read_wells()

    def set_path(self):
        """General path prefix settings"""
        self._path = self._data.get("path", ".")

    def set_report(self):
        """General report settings"""
        myreport = self._data.get("report", {"file": "default.csv", "mode": "write"})

        self._reportfile = myreport["file"]
        self._reportmode = myreport["mode"]

    def set_nametag(self):
        """General nametag settings"""
        self._nametag = self._data.get("nametag", {"file": "unset_nametag"})

    def parse_project(self):
        """Get the RoxarAPI project magics"""

        if "project" in self._data.keys():
            rox = xtgeo.RoxUtils(self._data["project"])
            self._project = rox.project

        else:
            self._project = None

    def read_grid(self):
        """Read 3D grid (which is required), from file or RMS"""

        if "grid" not in self._data.keys():
            return

        if "grid" in self._reuse:
            CMN.print_info("Reuse current grid...")
            return

        CMN.print_info("Reading grid geometry...")
        if self._project is None:
            gridpath = join(self._path, self._data["grid"])

            CMN.print_debug("GRIDPATH: {}".format(gridpath))
            self._grid = xtgeo.Grid(gridpath)

        # read from RMS/ROXAPI
        else:
            gridname = self._data["grid"]

            CMN.print_info("Reading grid...")
            CMN.print_debug("GRIDNAME: {}".format(gridname))
            self._grid = xtgeo.grid_from_roxar(self._project, gridname)

    def read_gridprops(self):
        """Read 3D grid props, from file or RMS"""


        if "gridprops" not in self._data.keys():
            return
            
        if "gridprops" in self._reuse:
            CMN.print_info("Reuse current grid properties...")
            return

        CMN.print_info("Reading grid properties...")
        gprops = []
        if self._project is None:

            for mytuple in self._data["gridprops"]:
                pname, pfile = mytuple

                gridproppath = join(self._path, pfile)
                current = xtgeo.gridproperty_from_file(
                    gridproppath, name=pname, grid=self.grid
                )
                gprops.append(current)
        else:
            for pname in self._data["gridprops"]:
                current = xtgeo.gridproperty_from_roxar(
                    self._project, self._data["grid"], pname
                )
                gprops.append(current)

        self._gridprops = xtgeo.GridProperties()
        self._gridprops.append_props(gprops)

    def read_wells(self):  # pylint: disable=too-many-branches
        """Reading wells"""

        if "wells" in self._reuse:
            CMN.print_info("Reuse current wells...")
            return

        if "wells" not in self._data.keys():
            return

        CMN.print_info("Reading wells...")
        wdata = []

        # pylint: disable=too-many-nested-blocks
        if self._project is None:
            # fields may contain wildcards for "globbing"
            if isinstance(self._data["wells"], list):
                for welldata in self._data["wells"]:
                    abswelldata = join(self._path, welldata)
                    for wellentry in glob(abswelldata):
                        mywell = xtgeo.Well()
                        mywell.from_file(wellentry, lognames=self._wells_lognames)

                        if self._wells_depthrange:
                            tmin, tmax = self._wells_depthrange
                            mywell.limit_tvd(tmin, tmax)

                        if self._wells_rescale:
                            mywell.rescale(self._wells_rescale)

                        wdata.append(mywell)
                        CMN.print_debug(wellentry)

        else:

            # roxar API input:
            # wells: {"names": WELLS, "logrun": LOGRUN, "trajectory": TRAJ}

            wnames = self._data["wells"].get("names", None)
            wlogrun = self._data["wells"].get("logrun", "log")
            wtraj = self._data["wells"].get("trajectory", "Drilled trajectory")

            rmswells = [wll.name for wll in self._project.wells]
            CMN.print_debug("All RMS wells: {}".format(rmswells))

            CMN.print_debug("Data wells to match: {}".format(wnames))

            for rmswell in rmswells:
                for wreg in wnames:
                    CMN.print_debug("Trying match {} vs re {}".format(rmswell, wreg))
                    if re.match(wreg + "$", rmswell):
                        try:
                            mywell = xtgeo.well_from_roxar(
                                self._project,
                                rmswell,
                                lognames=self._wells_lognames,
                                logrun=wlogrun,
                                trajectory=wtraj,
                            )

                            CMN.print_info(
                                "Regex match found, RMS well: {}".format(rmswell)
                            )

                            if self._wells_depthrange:
                                tmin, tmax = self._wells_depthrange
                                mywell.limit_tvd(tmin, tmax)

                            if self._wells_rescale:
                                mywell.rescale(self._wells_rescale)

                            wdata.append(mywell)

                        except ValueError as verr:
                            print("Could not read well {}: {}".format(rmswell, verr))

            CMN.print_debug("All valid welldata: {}".format(wdata))

        if wdata:
            self._wells = xtgeo.Wells()
            self._wells.wells = wdata
        else:
            raise RuntimeError("No wells read, wrong settings?")
