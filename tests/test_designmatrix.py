"""Testing excel2dict"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import sys
import os
import shutil

import pandas as pd

from fmu.tools.sensitivities import DesignMatrix, fmudesignrunner


def valid_designmatrix(dframe):
    """Performs general checks on a design matrix, that should always be valid"""
    assert "REAL" in dframe

    # REAL always starts at 0 and is consecutive
    assert dframe["REAL"][0] == 0
    assert dframe["REAL"].diff().dropna().unique() == 1

    assert "SENSNAME" in dframe.columns
    assert "SENSCASE" in dframe.columns

    # There should be no empty cells in the dataframe:
    assert not dframe.isna().sum().sum()


def test_designmatrix():
    """Test the DesignMatrix class"""

    design = DesignMatrix()

    mock_dict = dict(
        designtype="onebyone",
        seeds="default",
        repeats=10,
        defaultvalues=dict(),
        sensitivities=dict(
            rms_seed=dict(seedname="RMS_SEED", senstype="seed", parameters=None)
        ),
    )

    design.generate(mock_dict)
    valid_designmatrix(design.designvalues)
    assert len(design.designvalues) == 10
    assert isinstance(design.defaultvalues, dict)


def test_endpoint(tmpdir):
    """Test the installed endpoint

    Will write generated design matrices to the pytest tmpdir directory,
    usually /tmp/pytest-of-<username>/
    """
    testdatadir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "data/sensitivities/config/"
    )
    designfile = "design_input_onebyone.xlsx"

    # The xlsx file contains a relative path, relative to the input design sheet:
    dependency = (
        pd.read_excel(os.path.join(testdatadir, designfile), header=None)
        .set_index([0])[1]
        .to_dict()["background"]
    )
    tmpdir.chdir()
    # Copy over input files:
    shutil.copy(os.path.join(testdatadir, designfile), ".")
    shutil.copy(os.path.join(testdatadir, dependency), ".")
    sys.argv = ["fmudesign", designfile]
    fmudesignrunner.main()
    assert os.path.exists("generateddesignmatrix.xlsx")  # Default output file
    valid_designmatrix(pd.read_excel("generateddesignmatrix.xlsx"))

    sys.argv = ["fmudesign", designfile, "anotheroutput.xlsx"]
    fmudesignrunner.main()
    assert os.path.exists("anotheroutput.xlsx")
