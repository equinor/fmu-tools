"""The _qcforward module contains the base class"""
from __future__ import absolute_import, division, print_function  # PY2

from os.path import join

import yaml

from ._common import _QCCommon

# from . import _grid_statistics as _gstat
# from ._common import _QCCommon


QCC = _QCCommon()


class QCForward(object):
    """
    The QCforward base class which has a set of QC functions that can be ran from
    either RMS python, or on disk. The input `data` will be
    somewhat different for the two run environents.

    It should be easy to add new functions to this class. The idea is to reuse
    as much as possible, and principles are:

    * For the client (user), the calling scripts shall be lean

    * All methods shall have a rich documention with examples, i.e. it shall
      be possible for users with less skills in scripting to copy/paste and then modify
      to their needs.

    """

    def __init__(self):
        self._method = None
        self._data = None  # input data dictionary
        self._path = "."
        self._gdata = None  # QCForwardData instance, general data
        self._ldata = None  # special data instance, for local data parsed per method

    @property
    def gdata(self):
        return self._gdata

    @gdata.setter
    def gdata(self, data):
        self._gdata = data

    @property
    def ldata(self):
        return self._ldata

    @ldata.setter
    def ldata(self, data):
        self._ldata = data

    def handle_data(self, data, project):

        data_is_yaml = True

        # data may be a yaml file
        if isinstance(data, str):
            try:
                with open(data, "r") as stream:
                    xdata = yaml.safe_load(stream)
            except FileNotFoundError as err:
                raise RuntimeError(err)
            data_is_yaml = False
        else:
            xdata = data.copy()

        QCC.verbosity = xdata.get("verbosity", None)

        if data_is_yaml and "dump_yaml" in xdata and xdata["dump_yaml"]:
            xdata.pop("dump_yaml", None)
            with open(join(self._path, data["dump_yaml"]), "w") as stream:
                yaml.safe_dump(
                    xdata, stream, default_flow_style=None,
                )
            QCC.print_info("Dumped YAML to {}".format(data["dump_yaml"]))

        if project:
            xdata["project"] = project
            QCC.print_info("Project type is {}".format(type(project)))

        return xdata
