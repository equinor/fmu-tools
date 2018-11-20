=====
Usage
=====

fmu-tools is designed for use in several scenarios:

* Part of an ERT workflow, typically as a pre or postprocessing workflow
  used by HOOK_WORKFLOW PRE_SIMULATION (preprocessing) or POST_SIMULATION (postprocessing)
* Part of other scripts or utilities, either for analysis or preparations
  for visualization such as webviz.
* It can also be used interactively, e.g. in the (i)python interpreter  or a Jupyter notebook.

The current functionallity is:

* Automatic generation of design matrices to be run with DESIGN2PARAMS and DESIGN_KW in ERT
* Post processing of onebyone sensitivities and plotting in TornadoPlot in webviz


Generation of a design matrix can be run with a script::

    fmudesign <design_input.xlsx> <output_matrix.xlsx>

where <design_input.xlsx> is the path to the input for generating the design matrix
and <output_matrix.xlsx> is the path to the output design matrix.
Study the examples for how to configure the input for the design matrix

Post processing of onebyone sensitivities will be run from a python script
using fmu.tools.sensitivities
Study the examples to learn how to use it.

 
