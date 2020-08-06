"""
This private module in qcforward is used to parse data
"""
from os.path import join
from glob import glob
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


def _read_from_rms(self, data):
    """Read data inside RMS"""

    _get_verbosity(self, data)

    self._project = data["project"]

    if "grid" in data.keys():

        gridname = data["grid"]
        self.print_debug("GRIDPATH: {}".format(gridname))
        self._grid = xtgeo.grid_from_roxar(self._project, gridname)

    if "zone" in data.keys():
        self._gridzone = xtgeo.gridproperty_from_roxar(
            self._project, data["grid"], data["zone"]
        )

    if "wells" in data.keys():
        if isinstance(data["wells"], list):
            for welldata in data["wells"]:
                for wellentry in glob(abswelldata):
                    wdata.append(xtgeo.well_from_roxar(self._project, wll))
                    self.print_debug(wellentry)

        self._wells = xtgeo.Wells()
        self._wells.wells = wdata


def _read_from_disk(self, data):

    _get_verbosity(self, data)

    if "path" in data.keys():

        self.print_debug("PATH: {}".format(data["path"]))
        self._path = data["path"]

    if "grid" in data.keys():

        gridpath = join(self._path, data["grid"])
        self.print_debug("GRIDPATH: {}".format(gridpath))
        self._grid = xtgeo.Grid(gridpath)

    if "zone" in data.keys():
        zonedict = data["zone"]
        zonename, zonefile = _unpack_dict1(zonedict)

        zonefile = join(self._path, zonefile)
        self._gridzone = xtgeo.GridProperty(zonefile, name=zonename)

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
