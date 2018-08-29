# -*- coding: utf-8 -*-
"""Testing fmu-tools."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import fmu.config as config
import fmu.tools as tools

fmux = config.etc.Interaction()
logger = fmux.basiclogger(__name__)

# always this statement
if not fmux.testsetup():
    raise SystemExit()


def test_very_basics():
    """Test basic behaviour"""

    mytools = tools.Tools()

    assert isinstance(mytools, tools.Tools)
