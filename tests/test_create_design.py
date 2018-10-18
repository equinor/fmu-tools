# -*- coding: utf-8 -*-
"""Testing code for generation of design matrices"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import os

from fmu import config
from fmu.config import oyaml as yaml
from fmu.tools.sensitivities import DesignMatrix

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
            'config_design_input.yaml') as input_file:
        input_dict = yaml.load(input_file)

    design = DesignMatrix()
    design.set_defaultvalues(input_dict['defaultvalues'])
    design.generate(input_dict)

    # Checking dimensions of design matrix
    assert design.designvalues.shape == (100, 16)

    # Add more tests...
