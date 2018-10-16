#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Example: generation of design matrix
"""
from __future__ import division, print_function, absolute_import
from fmu.tools.sensitivities import DesignMatrix
from fmu.config import oyaml as yaml

design_configfile = '../tests/data/sensitivities/config/config_design_input.yaml'

with open(design_configfile) as input_file:
    input_dict=yaml.load(input_file)

design1 = DesignMatrix()
design1.generate(input_dict)
print(design1.designvalues)
design1.to_xlsx('design.xlsx')
