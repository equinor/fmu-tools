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

    def __init__(self, data):

        self._path = "."  # usually not needed to set explisit
        self._project = None  # pointing to  RMS project ID if any
        self._grid = None  # XTGeo Grid() instance
        self._grid_id = None  # A grid ID (to avoid reloading if already loaded)
        self._gridprops = None  # XTGeo GridProperties() for multiple props
        self._gridprops_id = None  # gridprops id
        self._wells = None  # XTGeo Wells() instance (multiple wells)
        self._surfaces = None  # XTGeo Surfaces() instance (in prep)

        self._reportfile = "default.csv"  # report file settings
        self._reportmode = "write"  # report file settings
        self._nametag = "unset_nametag"

        CMN.verbosity = data.get("verbosity", None)

        # TODO: validate dictionary that holds data
        self._data = data

        self.set_path()
        self.set_report()
        self.set_nametag()
        self.parse_project()
        gridalreadyloaded = self.read_grid()
        self.read_gridprops(gridalreadyloaded)
        self.read_wells()

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

    def set_path(self):
        """General path prefix settings"""
        self._path = self._data.get("path", ".")

    def set_report(self):
        """General report settings"""
        myreport = self._data.get("report", {"file": "default.yml", "mode": "write"})

        self._reportfile = myreport["file"]
        self._reportmode = myreport["mode"]

    def set_nametag(self):
        """General nametag settings"""
        self._nametag = self._data.get("nametag", {"file": "unset_nametag"})

    def parse_project(self):
        """Get the RoxarAPI project magics"""

        if "project" in self._data.keys() and self._data["project"]:
            rox = xtgeo.RoxUtils(self._data["project"])
            self._project = rox.project
        else:
            self._project = None

    def read_grid(self):
        """Read 3D grid (which is required), from file or RMS"""

        alreadyloaded = False

        if self._project is None:
            gridpath = join(self._path, self._data["grid"])

            if gridpath == self._grid_id:
                CMN.print_info("Grid is already loaded")
                alreadyloaded = True
            else:
                CMN.print_debug("GRIDPATH: {}".format(gridpath))
                self._grid = xtgeo.Grid(gridpath)
                self._grid_id = gridpath

        # read from RMS/ROXAPI
        else:
            gridname = self._data["grid"]

            if gridname == self._grid_id:
                CMN.print_info("Reuse grid...")
                alreadyloaded = True
            else:
                CMN.print_info("Reading grid...")
                CMN.print_debug("GRIDNAME: {}".format(gridname))
                self._grid = xtgeo.grid_from_roxar(self._project, gridname)
                self._grid_id = gridname

        return alreadyloaded

    def read_gridprops(self, gridalreadyloaded):
        """Read 3D grid props (required data), from file or RMS"""

        CMN.print_debug("Grid is alreay loaded: {}".format(gridalreadyloaded))

        gprops = []
        if self._project is None:

            # TODO check and handle if grid gridprops already loaded
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

    def read_wells(self):
        """Reading wells (required data)"""

        wdata = []
        if self._project is None:
            # fields may contain wildcards for "globbing"
            if isinstance(self._data["wells"], list):
                for welldata in self._data["wells"]:
                    abswelldata = join(self._path, welldata)
                    for wellentry in glob(abswelldata):
                        wdata.append(xtgeo.Well(wellentry))
                        CMN.print_debug(wellentry)

            self._wells = xtgeo.Wells()
            self._wells.wells = wdata

        else:

            # roxar API input:
            # wells: {"names": WELLS, "logrun": LOGRUN, "trajectory": TRAJ,
            #         "zonelog": ZONELOGNAME}

            wnames = self._data["wells"].get("names", None)
            wlogrun = self._data["wells"].get("logrun", "log")
            wtraj = self._data["wells"].get("trajectory", "Drilled trajectory")
            zlogname = self._data["wells"].get("zonelog", "Zonelog")

            rmswells = [wll.name for wll in self._project.wells]
            CMN.print_debug("All RMS wells: {}".format(rmswells))

            if not isinstance(self._data["wells"], list):
                raise ValueError("Wells input must be a list")

            CMN.print_debug("Data wells to match: {}".format(self._data["wells"]))

            for rmswell in rmswells:
                for wreg in wnames:
                    CMN.print_debug("Trying match {} vs re {}".format(rmswell, wreg))
                    if re.match(wreg, rmswell):
                        wdata.append(
                            xtgeo.well_from_roxar(
                                self._project,
                                rmswell,
                                logrun=wlogrun,
                                trajectory=wtraj,
                                lognames=[zlogname],
                            )
                        )
                        CMN.print_info(
                            "Regex match found, RMS well: {}".format(rmswell)
                        )

            self._wells = xtgeo.Wells()
            self._wells.wells = wdata
