# -*- coding: utf-8 -*-
"""Testing code for generation of design matrices"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import os
import pandas as pd

from fmu.tools.sensitivities import DesignMatrix, excel2dict_design


def test_generate_onebyone(tmpdir):
    """Test generation of onebyone design"""

    if "__file__" in globals():
        # Easen up copying test code into interactive sessions
        testdir = os.path.dirname(os.path.abspath(__file__))
    else:
        testdir = os.path.abspath(".")

    inputfile = testdir + "/data/sensitivities/config/" + "design_input_example1.xlsx"
    input_dict = excel2dict_design(inputfile)

    design = DesignMatrix()
    design.generate(input_dict)
    # Checking dimensions of design matrix
    assert design.designvalues.shape == (80, 10)

    # Write to disk and check some validity
    tmpdir.chdir()
    design.to_xlsx("designmatrix.xlsx")
    assert os.path.exists("designmatrix.xlsx")
    diskdesign = pd.read_excel("designmatrix.xlsx")
    assert "REAL" in diskdesign
    assert "SENSNAME" in diskdesign
    assert "SENSCASE" in diskdesign
    assert not diskdesign.empty

    diskdefaults = pd.read_excel("designmatrix.xlsx", sheet_name="DefaultValues")
    assert not diskdefaults.empty
    assert len(diskdefaults.columns) == 2


def test_generate_full_mc(tmpdir):
    """Test generation of full monte carlo"""
    if "__file__" in globals():
        # Easen up copying test code into interactive sessions
        testdir = os.path.dirname(os.path.abspath(__file__))
    else:
        testdir = os.path.abspath(".")

    inputfile = (
        testdir + "/data/sensitivities/config/" + "design_input_mc_with_correls.xlsx"
    )
    input_dict = excel2dict_design(inputfile)

    design = DesignMatrix()
    design.generate(input_dict)

    # Checking dimensions of design matrix
    assert design.designvalues.shape == (500, 16)

    # Checking reproducibility from distribution_seed
    assert design.designvalues["PARAM1"].sum() == 17.419

    # Write to disk and check some validity
    tmpdir.chdir()
    design.to_xlsx("designmatrix.xlsx")
    assert os.path.exists("designmatrix.xlsx")
    diskdesign = pd.read_excel("designmatrix.xlsx", sheet_name="DesignSheet01")
    assert "REAL" in diskdesign
    assert "SENSNAME" in diskdesign
    assert "SENSCASE" in diskdesign
    assert not diskdesign.empty

    diskdefaults = pd.read_excel("designmatrix.xlsx", sheet_name="DefaultValues")
    assert not diskdefaults.empty
    assert len(diskdefaults.columns) == 2


if __name__ == "__main__":
    # This is relevant when run in clean Komodo environment where pytest is missing
    test_generate_onebyone()
    test_generate_full_mc()
