"""Testing excel2dict"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import os
import pytest

import pandas as pd

from fmu.tools.sensitivities import excel2dict_design, inputdict_to_yaml

MOCK_GENERAL_INPUT = pd.DataFrame(
    data=[
        ["designtype", "onebyone"],
        ["repeats", "10"],
        ["rms_seeds", "default"],
        ["background", "None"],
        ["distribution_seed", "None"],
    ]
)

MOCK_DESIGNINPUT = pd.DataFrame(
    data=[["sensname", "numreal", "type", "param_name"], ["rms_seed", "", "seed"]]
)


def test_excel2dict_design(tmpdir):
    """Test that we can convert an Excelfile to a dictionary"""
    tmpdir.chdir()
    defaultvalues = pd.DataFrame()
    # pylint: disable=abstract-class-instantiated
    writer = pd.ExcelWriter("designinput.xlsx")
    MOCK_GENERAL_INPUT.to_excel(
        writer, sheet_name="general_input", index=False, header=None
    )
    MOCK_DESIGNINPUT.to_excel(
        writer, sheet_name="designinput", index=False, header=None
    )
    defaultvalues.to_excel(writer, sheet_name="defaultvalues", index=False, header=None)
    writer.save()

    dict_design = excel2dict_design("designinput.xlsx")
    assert isinstance(dict_design, dict)
    assert dict_design["designtype"] == "onebyone"
    assert dict_design["distribution_seed"] is None
    assert "defaultvalues" in dict_design

    assert isinstance(dict_design["defaultvalues"], dict)
    assert not dict_design["defaultvalues"]  # (it is empty)

    assert isinstance(dict_design["sensitivities"], dict)

    sens = dict_design["sensitivities"]
    # This now contains a key for each sensitivity to make
    assert "rms_seed" in sens
    assert isinstance(sens["rms_seed"], dict)
    assert sens["rms_seed"]["seedname"] == "RMS_SEED"
    assert sens["rms_seed"]["senstype"] == "seed"  # upper-cased

    # Check that we can vary some strings
    writer = pd.ExcelWriter("designinput2.xlsx")
    MOCK_GENERAL_INPUT.to_excel(
        writer, sheet_name="Generalinput", index=False, header=None
    )
    MOCK_DESIGNINPUT.to_excel(
        writer, sheet_name="Design_input", index=False, header=None
    )
    defaultvalues.to_excel(writer, sheet_name="DefaultValues", index=False, header=None)
    writer.save()

    dict_design = excel2dict_design("designinput2.xlsx")
    assert isinstance(dict_design, dict)
    assert dict_design["sensitivities"]["rms_seed"]["senstype"] == "seed"

    # Dump to yaml:
    inputdict_to_yaml(dict_design, "dictdesign.yaml")
    assert os.path.exists("dictdesign.yaml")
    assert "RMS_SEED" in "".join(open("dictdesign.yaml").readlines())


def test_duplicate_sensname_exception(tmpdir):
    mock_erroneous_designinput = pd.DataFrame(
        data=[
            ["sensname", "numreal", "type", "param_name"],
            ["rms_seed", "", "seed"],
            ["rms_seed", "", "seed"],
        ]
    )
    tmpdir.chdir()
    defaultvalues = pd.DataFrame()

    writer = pd.ExcelWriter("designinput3.xlsx")
    MOCK_GENERAL_INPUT.to_excel(
        writer, sheet_name="general_input", index=False, header=None
    )
    mock_erroneous_designinput.to_excel(
        writer, sheet_name="designinput", index=False, header=None
    )
    defaultvalues.to_excel(writer, sheet_name="defaultvalues", index=False, header=None)
    writer.save()

    with pytest.raises(
        ValueError, match="Two sensitivities can not share the same sensname"
    ):
        dict_design = excel2dict_design("designinput3.xlsx")


def test_mixed_senstype_exception(tmpdir):
    mock_erroneous_designinput = pd.DataFrame(
        data=[
            ["sensname", "numreal", "type", "param_name"],
            ["rms_seed", "", "seed"],
            ["", "", "dist"],
        ]
    )
    tmpdir.chdir()
    defaultvalues = pd.DataFrame()

    writer = pd.ExcelWriter("designinput4.xlsx")
    MOCK_GENERAL_INPUT.to_excel(
        writer, sheet_name="general_input", index=False, header=None
    )
    mock_erroneous_designinput.to_excel(
        writer, sheet_name="designinput", index=False, header=None
    )
    defaultvalues.to_excel(writer, sheet_name="defaultvalues", index=False, header=None)
    writer.save()

    with pytest.raises(ValueError, match="contains more than one sensitivity type"):
        dict_design = excel2dict_design("designinput4.xlsx")
