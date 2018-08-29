# -*- coding: utf-8 -*-
"""Module for some stuff...
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from fmu.config import etc

xfmu = etc.Interaction()
logger = xfmu.functionlogger(__name__)


# not sure if having a class name Tools is a good idea...
class Tools(object):
    """Class for some stuff"""

    def __init__(self):
        self._ditt = {}
        self._datt = None
        logger.debug('Ran __init__')

    @property
    def ditt(self):
        """Get the current ditt as a Python dictionary (read only)."""
        return self._ditt
