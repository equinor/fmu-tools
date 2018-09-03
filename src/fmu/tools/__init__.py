# -*- coding: utf-8 -*-

"""Top-level package for fmu_config"""

from ._version import get_versions
__version__ = get_versions()['version']

del get_versions

from .tools import Tools  # noqa
from .parsers import RmsVolumeFileParser
from .coviz import SpatialFileNameCollection
from .coviz import DataArray
from .coviz import StatisticsArray
from .coviz import CovizModel