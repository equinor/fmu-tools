#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Example: generation of design matrix
"""
from __future__ import division, print_function, absolute_import
from fmu.tools.sensitivities import DesignMatrix, excel2dict_design, inputdict_to_yaml
from fmu.config import oyaml as yaml
import os

os.chdir('../')

# design_configfile = './tests/data/sensitivities/config/config_design_input.yaml'
#with open(design_configfile) as input_file:
#    input_dict=yaml.load(input_file)


# design_configfile = './tests/data/sensitivities/config/fossekall_design.xlsx'
design_configfile = './tests/data/sensitivities/config/design_input_onebyone.xlsx'

input_dict = excel2dict_design(design_configfile)
inputdict_to_yaml(input_dict, 'examples/output/design_inut_dict_dumped.yaml')

design1 = DesignMatrix()
design1.generate(input_dict)
design1.to_xlsx('examples/output/design.xlsx')
if design1.backgroundvalues is not None:
    design1.background_to_excel('examples/output/background.xlsx')
