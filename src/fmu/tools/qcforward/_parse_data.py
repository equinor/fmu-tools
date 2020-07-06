"""
This private module in qcforward is used to parse data
"""
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


def _read_from_rms(self, data):
    self._grid = None


def _read_from_disk(self, data):

    if "grid" in data.keys():

        print("XXXX", data["grid"])
        self._grid = xtgeo.Grid(data["grid"])

    if "zone" in data.keys():
        zonedict = data["zone"]
        zonename, zonefile = _unpack_dict1(zonedict)

        self._gridzone = xtgeo.GridProperty(zonefile, name=zonename)

    if "wells" in data.keys():
        # fields may contain wildcards for "globbing"
        wdata = []
        if isinstance(data["wells"], list):
            for welldata in data["wells"]:
                for wellentry in glob(welldata):
                    wdata.append(xtgeo.Well(wellentry))

        self._wells = xtgeo.Wells()
        self._wells.wells = wdata
