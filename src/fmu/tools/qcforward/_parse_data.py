"""
This private module in qcforward is used to parse data on a general level.

The resulting data will be stored as class instance attributes, e.g. self._grid

"""
from os.path import join
from glob import glob
import re
import xtgeo


class _QCForwardData(object):
    """
    This is a local class which parse/reads and stores some common data
    like 3D grids, maps etc for all QCForward methods

    By having it as a class one can store different datasets and compare them later
    if needed. E.g. if one need to compare two grid models, they will be members
    of two different instances of the _QCForwardData()


    """

    def __init__(self, data):

        self._verbosity = 0
        self._path = "."
        self._project = None  # pointing to  RMS project ID if any
        self._grid = None  # XTGeo Grid() instance
        self._gridid = None  # An ID (name of grid or file path)
        self._wells = None  # XTGeo Wells() instance (multiple wells)
        self._gridprops = None  # XTGeo GridProperties() for multiple props
        self._gridpropsid = {},  # a dictionary for property names ID, cf _gridid

        verbosity = data.get("verbosity", None)
        if verbosity == "info":
            self._verbosity = 1
        elif verbosity == "debug":
            self._verbosity = 2

        self._path = data.get("path", ".")

        # todo: validate dictionary that holds data
        self._data = data

        self.parse_project()
        self.grid_grid()
        self.read_gridprops()
        self.read_wells()

    @property
    def grid(self):
        """Grid attribute as XTGeo Grid() instance"""
        return self._grid

    @property
    def gridprops(self):
        """GridProperties attribute as XTGeo GridProperties() instance"""
        return self._gridprops

    @staticmethod
    def _unpack_dict1(mydict):
        """Unpack elements from a dict with one pair"""
        if len(mydict) != 1 or not isinstance(mydict, dict):
            raise ValueError("Incorrect input to _unpack_dict1")

        key = list(mydict.keys())[0]
        value = list(mydict.values())[0]
        return key, value

    def print_info(self, string):
        """Do print based on verbosity level >= 1"""
        if self._verbosity > 0:
            print("INFO  >>", string)

    def print_debug(self, string):
        """Do debug print based on verbosity level >= 2"""
        if self._verbosity > 1:
            print("DEBUG >>", string)

    def read_grid(self):
        """Read 3D grid if requested, from file or RMS"""

        if "grid" in self._data and self._project is None:
            gridpath = join(self._path, data["grid"])
            if gridpath == self._gridid:
                self.print_info("Grid is already loaded")
                reuse_grid = True
            else:
                self.print_debug("GRIDPATH: {}".format(gridpath))
                self._grid = xtgeo.Grid(gridpath)
                self._gridid = gridpath

        # read from RMS/ROXAPI
        elif "grid" in self._data and self._project:
            gridname = data["grid"]

            if gridname == self._gridid:
                self.print_info("Reuse grid...")
                reusegrid = True
            else:
                self.print_info("Reading grid...")
                self.print_debug("GRIDNAME: {}".format(gridname))
                self._grid = xtgeo.grid_from_roxar(self._project, gridname)
                self._gridid = gridname

    def read_gridprops(self):
        """Read 3D grid if requested, from file or RMS"""

        gridname = data["grid"]

        reusegrid = False
        if gridname == self._gridid:
            reusegrid = True

        if "gridprops" in self._data.keys() and self._project:
            gridname = data["grid"]

            if gridname == self._gridid:
                self.print_info("Reuse grid...")
            else:
                self.print_info("Reading grid...")
                self.print_debug("GRIDNAME: {}".format(gridname))
                self._grid = xtgeo.grid_from_roxar(self._project, gridname)
                self._gridid = gridname

        elif "gridprops" in self._data.keys() and self._project is None:
            gridpath = join(self._path, data["grid"])
            if gridpath == self._gridid:
                self.print_info("Grid is already loaded")
                reuse_grid = True
            else:
                self.print_debug("GRIDPATH: {}".format(gridpath))
                self._grid = xtgeo.Grid(gridpath)
                self._gridid = gridpath


    def read_wells():
        if "wells" in self._data.keys() and self._project is None:
            # fields may contain wildcards for "globbing"
            wdata = []
            if isinstance(data["wells"], list):
                for welldata in data["wells"]:
                    abswelldata = join(self._path, welldata)
                    for wellentry in glob(abswelldata):
                        wdata.append(xtgeo.Well(wellentry))
                        self.print_debug(wellentry)

            self._wells = xtgeo.Wells()
            self._wells.wells = wdata

    if "wells" in data.keys():
        # wells area allowed to spesified by regular expressions, e.g.
        # ["55_33-[123]", "55_33-.*A.*"]

        if "zonelogname" in data:
            self._zonelogname = data["zonelogname"]

        wdata = []

        rmswells = [wll.name for wll in self._project.wells]
        self.print_debug("All RMS wells: {}".format(rmswells))
        if not isinstance(data["wells"], list):
            raise ValueError("Wells input must be a list")

        self.print_debug("Data wells to match: {}".format(data["wells"]))
        for rmswell in rmswells:
            for wreg in data["wells"]:
                self.print_debug("Trying match {} vs re {}".format(rmswell, wreg))
                if re.match(wreg, rmswell):
                    wdata.append(
                        xtgeo.well_from_roxar(
                            self._project,
                            rmswell,
                            logrun=self._wlogrun,
                            trajectory=self._wtrajectory,
                            lognames=[self._zonelogname],
                        )
                    )
                    self.print_info("Regex match found, RMS well: {}".format(rmswell))

        self._wells = xtgeo.Wells()
        self._wells.wells = wdata



    if "zone" in data.keys():
        zonedict = data["zone"]
        zonename, zonefile = _unpack_dict1(zonedict)

        zonefile = join(self._path, zonefile)

        # since grid can be different but zonefile may the same (rare for files...)
        if reuse_grid and zonefile == self._gridzonename:
            self.print_info("Grid zone is already loaded")
        else:
            self._gridzone = xtgeo.GridProperty(zonefile, name=zonename)
            self._gridzonename = zonefile


def _read_from_rms(self, data):
    """Read data from inside RMS or via Roxar API"""

    _get_verbosity(self, data)

    self._project = data["project"]

    reuse_grid = False
    if "grid" in data.keys():


    self.print_debug("Looking for zone...")
    if "zone" in data.keys():
        if reuse_grid and data["zone"] == self._gridzonename:
            self.print_info("Grid zone is already loaded")
        else:
            self._gridzone = xtgeo.gridproperty_from_roxar(
                self._project, data["grid"], data["zone"]
            )
            self._gridzonename = data["zone"]
            self.print_debug("GRIDZONE: {}".format(self._gridzonename))

