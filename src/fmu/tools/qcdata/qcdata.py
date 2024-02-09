"""
This private module in qcforward is used to parse data on a general level.

The resulting data will be stored as class instance attributes, e.g. self._grid

"""

import re
from glob import glob
from os.path import join

import xtgeo

from fmu.tools._common import _QCCommon

CMN = _QCCommon()


class QCData(object):
    """
    This is a class which parse/reads and stores some common data
    like 3D grids, maps etc.

    It shall be semi-agnostic to where data comes from, i.e. accept both files
    and RMS input.

    By having it as a class one can store different datasets and compare them later
    if needed. E.g. if one need to compare two grid models, they will be members
    of two different instances of the QCData()
    """

    def __init__(self):
        self._reuse = []
        self._xtgdata = {}  # All XTGeo data, to be reused
        self._path = "."  # usually not needed to set explisit
        self._project = None  # pointing to  RMS project ID if any
        self._grid = None  # A XTGeo Grid()
        self._gridprops = None  # XTGeo GridProperties() for multiple props
        self._wells = None  # XTGeo Wells() instance (multiple wells)
        self._bwells = None
        self._surfaces = None  # XTGeo Surfaces() instance (in prep)

        self._set_xtgdata_keys()

    # Properties
    # ==================================================================================

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
    def bwells(self):
        """Wells attribute as XTGeo BlockedWells() instance"""
        return self._bwells

    @property
    def xtgdata(self):
        """All xtgeo based data as a dictionay"""
        return self._xtgdata

    # Class methods:
    # ==================================================================================

    def _set_xtgdata_keys(self):
        self._xtgdata["grid"] = {}
        self._xtgdata["gridprops"] = {}
        self._xtgdata["wells"] = {}
        self._xtgdata["bwells"] = {}

    def parse(
        self,
        data=None,
        project=None,
        reuse=False,
        wells_settings=None,
    ):
        """Parse the actual data, such as grids, gridprops etc.

        Args:
            data (dict): The input data dictionary
                fine grained control, e.g. ["grid", "gridprops", "wells"]
            project (obj or str): For usage inside RMS
            reuse (bool or list): If True, do not reread grid and gridprops. Can also be
                a list referring to key names.
            wells_settings (dict): More granular settings for wells which may speed
                up reading and/or execution. If set, this is a dictionary with keys
                ``lognames``, ``depthrange``, ``resample``

        """

        CMN.verbosity = data.get("verbosity")

        if isinstance(reuse, bool):
            reuse = ["grid", "gridprops", "wells"] if reuse else []

        self.set_path(data.get("path"))
        self.parse_project(project)

        if "grid" in data:
            self.read_grid(data["grid"], reuse)

        if "gridprops" in data:
            self.read_gridprops(data["gridprops"], data.get("grid"), reuse)

        for welltype in ["wells", "bwells"]:
            if welltype in data:
                self.read_wells(data[welltype], welltype, wells_settings, reuse)

    def set_path(self, path):
        """General path prefix settings"""
        self._path = path

    def parse_project(self, project=None):
        """Get the RoxarAPI project magics"""

        if project is not None:
            rox = xtgeo.RoxUtils(project)
            self._project = rox.project
        else:
            self._project = None

    def read_grid(self, gridname, reuse):
        """Read 3D grid (which is required), from file or RMS"""

        gridname = gridname if self._project is not None else join(self._path, gridname)
        CMN.print_debug(f"GRIDNAME: {gridname}")

        CMN.print_info("Reading grid geometry...")
        if ("grid" not in reuse) or (gridname not in self._xtgdata["grid"]):
            self._grid = (
                xtgeo.grid_from_file(gridname)
                if self._project is None
                else xtgeo.grid_from_roxar(self._project, gridname)
            )
            self._xtgdata["grid"][gridname] = self._grid
            self._xtgdata["gridprops"][gridname] = {}
        else:
            CMN.print_info(f"Reusing grid {gridname}")
            self._grid = self._xtgdata["grid"][gridname]

    def read_gridprops(self, gridprops, gridname=None, reuse=None):
        """Read 3D grid props, from file or RMS."""

        gridname = gridname if self._project is not None else join(self._path, gridname)

        CMN.print_info("Reading grid properties...")
        gprops = []
        if "gridprops" in reuse:
            reused_gprops, gridprops = self._reuse_gridprops(gridprops, gridname)
            gprops = reused_gprops

        if self._project is None:
            for gprop in gridprops:
                if isinstance(gprop, list):
                    pname, pfile = gprop
                else:
                    pfile = gprop
                    pname = None

                gridproppath = join(self._path, pfile)

                xtg_gprop = xtgeo.gridproperty_from_file(
                    gridproppath, name=pname, grid=self.grid
                )
                xtg_gprop.name = pname if pname is not None else pfile
                gprops.append(xtg_gprop)
                if isinstance(gprop, list):
                    self._xtgdata["gridprops"][gridname][tuple(gprop)] = xtg_gprop
                else:
                    self._xtgdata["gridprops"][gridname][gprop] = xtg_gprop
        else:
            # read from RMS/ROXAPI
            for pname in gridprops:
                xtg_gprop = xtgeo.gridproperty_from_roxar(
                    self._project, gridname, pname
                )
                gprops.append(xtg_gprop)
                self._xtgdata["gridprops"][gridname][pname] = xtg_gprop

        self._gridprops = xtgeo.GridProperties()
        self._gridprops.append_props(gprops)

    def _well_preparations(self, wells):
        """Account for wildcards and regex in wellist"""

        input_wells = []
        if self._project is None:
            for welldata in wells:
                # fields may contain wildcards for "globbing"
                for wellentry in glob(join(self._path, welldata)):
                    input_wells.append(wellentry)
        else:
            # roxar API input:
            wnames = wells.get("names", [".*$"])
            rmswells = [wll.name for wll in self._project.wells]

            CMN.print_debug(f"All RMS wells: {rmswells}")
            CMN.print_debug(f"Data wells to match: {wnames}")

            for rmswell in rmswells:
                if any(re.match(wreg + "$", rmswell) for wreg in wnames):
                    input_wells.append(rmswell)

        return input_wells

    def read_wells(self, wells, welltype="wells", settings=False, reuse=None):
        """Reading wells"""

        settings = settings if settings else {}
        wellist = self._well_preparations(wells)

        CMN.print_info("Reading wells...")
        xtg_wells = []
        if "wells" in reuse:
            reused_wells, wellist = self._reuse_wells(wellist, welltype)
            xtg_wells = reused_wells

        for well in wellist:
            try:
                if welltype == "wells":
                    mywell = (
                        xtgeo.well_from_file(
                            well, lognames=settings.get("lognames", "all")
                        )
                        if self._project is None
                        else xtgeo.well_from_roxar(
                            project=self._project,
                            name=well,
                            lognames=settings.get("lognames", "all"),
                            logrun=wells.get("logrun", "log"),
                            trajectory=wells.get("trajectory", "Drilled trajectory"),
                        )
                    )
                else:
                    mywell = (
                        xtgeo.blockedwell_from_file(well)
                        if self._project is None
                        else xtgeo.blockedwell_from_roxar(
                            project=self._project,
                            gname=wells.get("grid", "Geogrid"),
                            bwname=wells.get("bwname", "BW"),
                            wname=well,
                            lognames=settings.get("lognames", "all"),
                        )
                    )
                xtg_wells.append(mywell)
                self._xtgdata[welltype][well] = mywell

            except ValueError as verr:
                print(f"Could not read well {well}: {verr}")

        CMN.print_debug(f"All valid welldata: {xtg_wells}")

        for mywell in xtg_wells:
            if "depthrange" in settings and settings["depthrange"] is not None:
                tmin, tmax = settings["depthrange"]
                mywell.limit_tvd(tmin, tmax)
            if "rescale" in settings and settings["rescale"] is not None:
                mywell.rescale(settings["rescale"])

        if xtg_wells:
            if welltype == "wells":
                self._wells = xtgeo.Wells()
                self._wells.wells = xtg_wells
            else:
                self._bwells = xtgeo.BlockedWells()
                self._bwells.wells = xtg_wells
        else:
            raise RuntimeError("No wells read, wrong settings?")

    def _reuse_gridprops(self, gridprops, gridname):
        """
        Identify which gridprops are available for reusing, reusable
        gridprops and new gridprops are returned in separate lists
        """
        new_gprops = []
        reused_gprops = []

        for elem in gridprops:
            if isinstance(elem, list):
                if tuple(elem) not in self._xtgdata["gridprops"][gridname]:
                    new_gprops.append(elem)
                reused_gprops = [
                    value
                    for key, value in self._xtgdata["gridprops"][gridname].items()
                    if list(key) in gridprops
                ]
            else:
                if elem not in self._xtgdata["gridprops"][gridname]:
                    new_gprops.append(elem)
                reused_gprops = [
                    value
                    for key, value in self._xtgdata["gridprops"][gridname].items()
                    if key in gridprops
                ]

        CMN.print_info(f"Reusing gridprops: {[x.name for x in reused_gprops]}")
        CMN.print_info(f"New gridprops: {new_gprops}")

        return reused_gprops, new_gprops

    def _reuse_wells(self, wells, welltype):
        """
        Identify which wells are available for reusing, reusable
        wells and new wells are returned in separate lists
        """

        new_wells = []
        reused_wells = []
        for well in wells:
            if well not in self._xtgdata[welltype]:
                new_wells.append(well)

        reused_wells = [
            value for key, value in self._xtgdata[welltype].items() if key in wells
        ]

        CMN.print_info(f"Reused wells: {[x.name for x in reused_wells]}")
        CMN.print_info(f"New wells: {new_wells}")

        return reused_wells, new_wells
