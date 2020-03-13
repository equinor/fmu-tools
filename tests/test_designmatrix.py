"""Testing excel2dict"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import os
from collections import OrderedDict

import pandas as pd

from fmu.tools.sensitivities import DesignMatrix


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
