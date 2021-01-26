#!/usr/bin/env python
"""
Example: generation of design matrix
"""

import os

from fmu.tools.sensitivities import DesignMatrix, excel2dict_design

os.chdir("../")

# design_configfile = './tests/data/sensitivities/config/config_design_input.yaml'
# with open(design_configfile) as input_file:
#    input_dict=yaml.load(input_file)

path = "./tests/data/sensitivities/config/"
prefix = "design_input_"
postfix = ".xlsx"
config = [
    "example1",
    "example2",
    "example_velocities",
    "singlereference",
    "singlereference_and_seed",
    "default_no_seed",
    "onebyone",
    "background_no_seed",
    "background_extseeds",
    "mc_with_correls",
    "montecarlo_full",
    "mc_corr_depend",
]

for input in range(len(config)):
    filename = path + prefix + config[input] + postfix
    print("Reading {}".format(filename))
    input_dict = excel2dict_design(filename)
    # input_dict.to_yaml(input_dict, 'examples/output/'+config[input]+'.yaml')
    design = DesignMatrix()
    design.generate(input_dict)
    design.to_xlsx("examples/output/design_" + config[input] + postfix)
    # if design.backgroundvalues is not None:
    # design.background_to_excel('examples/output/background.xlsx')
