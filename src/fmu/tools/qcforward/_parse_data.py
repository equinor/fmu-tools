"""
This private module in qcforward is used to parse data
"""
from os.path import join
from glob import glob
import re
import xtgeo


def parse(self, data):
    if "project" in data.keys():
        _read_from_rms(self, data)
    else:
        _read_from_disk(self, data)


def _unpack_dict1(mydict):
    """Unpack elements from a dict with one pair"""
    if len(mydict) != 1 or not isinstance(mydict, dict):
        raise ValueError("Incorrect input to _unpack_dict1")

    key = list(mydict.keys())[0]
    value = list(mydict.values())[0]
    return key, value


def _get_verbosity(self, data):
    """Parse verbosity level"""

    if "verbosity" in data.keys():
        verb = data["verbosity"]
        if isinstance(verb, str) and verb == "info":
            self._verbosity = 1
        elif isinstance(verb, str) and verb == "debug":
            self._verbosity = 2
        elif isinstance(verb, int) and -1 <= verb <= 2:
            self._verbosity = verb
        else:
            self._verbosity = 0


def _read_from_disk(self, data):

    _get_verbosity(self, data)

    if "path" in data.keys():

        self.print_debug("PATH: {}".format(data["path"]))
        self._path = data["path"]

    reuse_grid = False
    if "grid" in data.keys():

        gridpath = join(self._path, data["grid"])
        if gridpath == self._gridname:
            self.print_info("Grid is already loaded")
            reuse_grid = True
        else:
            self.print_debug("GRIDPATH: {}".format(gridpath))
            self._grid = xtgeo.Grid(gridpath)
            self._gridname = gridpath

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

    if "wells" in data.keys():
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


def _read_from_rms(self, data):
    """Read data from inside RMS or via Roxar API"""

    _get_verbosity(self, data)

    self._project = data["project"]

    reuse_grid = False
    if "grid" in data.keys():

        gridname = data["grid"]

        if gridname == self._gridname:
            self.print_info("Grid is already loaded")
            reuse_grid = True  # grid is already loaded
        else:
            self.print_info("Reading grid...")
            self.print_debug("GRIDNAME: {}".format(gridname))
            self._grid = xtgeo.grid_from_roxar(self._project, gridname)
            self._gridname = gridname

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
