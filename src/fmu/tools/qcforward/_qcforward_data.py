"""
This private module in qcforward is used to parse data on a general level.

The resulting data will be stored as class instance attributes, e.g. self._grid

"""
from os.path import join
from glob import glob
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

        self.parse_project()
        gridalreadyloaded = self.read_grid()
        self.read_gridprops(gridalreadyloaded)
        self.read_wells()
        self.read_wells()
        self.set_report()
        self.set_nametag()

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

    def parse_project(self):
        """Get the RoxarAPI project magics"""

        if "project" in self._data.keys() and self._data["project"]:
            rox = xtgeo.RoxUtils(self._data["project"])
            self._project = rox.project
        else:
            self._project = None

    def read_grid(self):
        """Read 3D grid if requested, from file or RMS"""

        alreadyloaded = False
        if "grid" in self._data and self._project is None:
            gridpath = join(self._path, self._data["grid"])
            if gridpath == self._grid_id:
                CMN.print_info("Grid is already loaded")
                alreadyloaded = True
            else:
                CMN.print_debug("GRIDPATH: {}".format(gridpath))
                self._grid = xtgeo.Grid(gridpath)
                self._grid_id = gridpath

        # read from RMS/ROXAPI
        elif "grid" in self._data and self._project:
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
        """Read 3D grid props if requested, from file or RMS"""

        self._gridprops = xtgeo.GridProperties()

        CMN.print_debug("Grid is alreay loaded: {}".format(gridalreadyloaded))

        if "gridprops" in self._data.keys() and self._project is None:

            # todo, check and handle if grid gridprops already loaded
            for mytuple in self._data["gridprops"]:
                pname, pfile = mytuple

                gridproppath = join(self._path, pfile)
                current = xtgeo.gridproperty_from_file(
                    gridproppath, name=pname, grid=self.grid
                )
                print(current)
                self._gridprops.append_props([current])

        # elif "gridprops" in self._data.keys() and self._project:
        #     gridname = self._data["grid"]

    def read_wells(self):
        if "wells" in self._data.keys() and self._project is None:
            # fields may contain wildcards for "globbing"
            wdata = []
            if isinstance(self._data["wells"], list):
                for welldata in self._data["wells"]:
                    abswelldata = join(self._path, welldata)
                    for wellentry in glob(abswelldata):
                        wdata.append(xtgeo.Well(wellentry))
                        CMN.print_debug(wellentry)

            self._wells = xtgeo.Wells()
            self._wells.wells = wdata

    def set_report(self):
        """General report settings"""
        myreport = self._data.get("report", {"file": "default.yml", "mode": "write"})

        self._reportfile = myreport["file"]
        self._reportmode = myreport["mode"]

    def set_nametag(self):
        """General nametag settings"""
        self._nametag = self._data.get("nametag", {"file": "unset_nametag"})

    def set_path(self):
        """General path prefix settings"""
        self._path = self._data.get("path", ".")

    # if "wells" in data.keys():
    #     # wells area allowed to spesified by regular expressions, e.g.
    #     # ["55_33-[123]", "55_33-.*A.*"]

    #     if "zonelogname" in data:
    #         self._zonelogname = self._data["zonelogname"]

    #     wdata = []

    #     rmswells = [wll.name for wll in self._project.wells]
    #     self.print_debug("All RMS wells: {}".format(rmswells))
    #     if not isinstance(self._data["wells"], list):
    #         raise ValueError("Wells input must be a list")

    #     self.print_debug("Data wells to match: {}".format(self._data["wells"]))
    #     for rmswell in rmswells:
    #         for wreg in self._data["wells"]:
    #             self.print_debug("Trying match {} vs re {}".format(rmswell, wreg))
    #             if re.match(wreg, rmswell):
    #                 wdata.append(
    #                     xtgeo.well_from_roxar(
    #                         self._project,
    #                         rmswell,
    #                         logrun=self._wlogrun,
    #                         trajectory=self._wtrajectory,
    #                         lognames=[self._zonelogname],
    #                     )
    #                 )
    #                 self.print_info("Regex match found, RMS well: {}".format(rmswell))

    #     self._wells = xtgeo.Wells()
    #     self._wells.wells = wdata

    # if "zone" in data.keys():
    #     zonedict = self._data["zone"]
    #     zonename, zonefile = _unpack_dict1(zonedict)

    #     zonefile = join(self._path, zonefile)

    #     # since grid can be different but zonefile may the same (rare for files...)
    #     if reuse_grid and zonefile == self._gridzonename:
    #         self.print_info("Grid zone is already loaded")
    #     else:
    #         self._gridzone = xtgeo.GridProperty(zonefile, name=zonename)
    #         self._gridzonename = zonefile


# def _read_from_rms(self, data):
#     """Read data from inside RMS or via Roxar API"""

#     _get_verbosity(self, data)

#     self._project = self._data["project"]

#     reuse_grid = False
#     if "grid" in data.keys():


#     self.print_debug("Looking for zone...")
#     if "zone" in data.keys():
#         if reuse_grid and self._data["zone"] == self._gridzonename:
#             self.print_info("Grid zone is already loaded")
#         else:
#             self._gridzone = xtgeo.gridproperty_from_roxar(
#                 self._project, self._data["grid"], self._data["zone"]
#             )
#             self._gridzonename = self._data["zone"]
#             self.print_debug("GRIDZONE: {}".format(self._gridzonename))
