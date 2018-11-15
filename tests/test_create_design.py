# -*- coding: utf-8 -*-
"""Testing code for generation of design matrices"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import os

from fmu import config
from fmu.tools.sensitivities import DesignMatrix, excel2dict_design

fmux = config.etc.Interaction()
logger = fmux.basiclogger(__name__)

if not fmux.testsetup():
    raise SystemExit()


def test_generate_onebyone():
    """Test generation of onebyone design"""

    if '__file__' in globals():
        # Easen up copying test code into interactive sessions
        testdir = os.path.dirname(os.path.abspath(__file__))
    else:
        testdir = os.path.abspath('.')

    with open(
            testdir +
            '/data/sensitivities/config/' +
            'design_input_example1.xlsx') as input_file:
        input_dict = excel2dict_design(input_file)

    design = DesignMatrix()
    design.generate(input_dict)

    # Checking dimensions of design matrix
    assert design.designvalues.shape == (80, 10)

    # Add more tests...
