"""Testing code for generation of design matrices"""

from pathlib import Path

import numpy as np
import pandas as pd

from fmu.tools.sensitivities import DesignMatrix, excel2dict_design

TESTDATA = Path(__file__).parent / "data"


def test_generate_onebyone(tmpdir):
    """Test generation of onebyone design"""

    inputfile = TESTDATA / "config/design_input_example1.xlsx"

    input_dict = excel2dict_design(inputfile)

    # Note that repeats are set to 10 in general_input sheet.
    # So, there are 10 rows for each senscase of type seed and scenario.
    # However, there are 20 rows for multz because numreal is set to 20 in designinput.
    rows_in_design_matrix = 80

    design = DesignMatrix()
    design.generate(input_dict)
    # Checking dimensions of design matrix
    assert design.designvalues.shape == (rows_in_design_matrix, 10)

    # Write to disk and check some validity
    tmpdir.chdir()
    design.to_xlsx("designmatrix.xlsx")
    assert Path("designmatrix.xlsx").exists
    diskdesign = pd.read_excel("designmatrix.xlsx", engine="openpyxl")

    assert (
        diskdesign.columns
        == [
            "REAL",
            "SENSNAME",
            "SENSCASE",
            "RMS_SEED",
            "FAULT_POSITION",
            "DC_MODEL",
            "OWC1",
            "OWC2",
            "OWC3",
            "MULTZ_ILE",
        ]
    ).all()
    assert (diskdesign["REAL"].values == np.arange(rows_in_design_matrix)).all()
    ensemble_size = 10
    sensname = (
        ["rms_seed"] * ensemble_size
        + ["faults"] * 2 * ensemble_size  # 2 senscases, east and west
        + ["velmodel"] * ensemble_size
        + ["contacts"] * 2 * ensemble_size  # 2 contacts, shallow and deep
        + ["multz"] * 20
    )
    assert (diskdesign["SENSNAME"] == sensname).all()
    # Sensitivites of type seed like rms_seed automatically get senscase p10_p90,
    # so that P10/P90 is calculated for the tornado plot.
    assert (
        diskdesign[diskdesign["SENSNAME"] == "rms_seed"]["SENSCASE"] == "p10_p90"
    ).all()
    assert (
        diskdesign[diskdesign["SENSNAME"] == "faults"]["SENSCASE"]
        == ["east"] * ensemble_size + ["west"] * ensemble_size
    ).all()
    assert (
        diskdesign[diskdesign["SENSNAME"] == "velmodel"]["SENSCASE"] == "alternative"
    ).all()
    assert (
        diskdesign[diskdesign["SENSNAME"] == "contacts"]["SENSCASE"]
        == ["shallow"] * ensemble_size + ["deep"] * ensemble_size
    ).all()
    assert (
        diskdesign[diskdesign["SENSNAME"] == "multz"]["SENSCASE"] == ["p10_p90"] * 20
    ).all()

    # When rms_seed is set to default it means that RMS_SEED numbers
    # 1000, 1001,... are used.
    # Note that for most senscases, RMS_SEED goes from 1000 to 1009,
    # but that it goes from 1000 to 1019 for multz because numreal
    # is set to 20 in the designinput sheet.
    assert (
        diskdesign["RMS_SEED"]
        == list(range(1000, 1000 + ensemble_size)) * 6 + list(range(1000, 1000 + 20))
    ).all()

    diskdefaults = pd.read_excel(
        "designmatrix.xlsx", sheet_name="DefaultValues", header=None, engine="openpyxl"
    )
    assert (diskdefaults.columns == [0, 1]).all()
    assert (
        diskdefaults.iloc[:, 0]
        == [
            "RMS_SEED",
            "FAULT_POSITION",
            "DC_MODEL",
            "OWC1",
            "OWC2",
            "OWC3",
            "MULTZ_ILE",
            "PARAM1",
            "PARAM2",
            "PARAM3",
            "PARAM4",
        ]
    ).all()

    diskdefaults = diskdefaults.set_index(0)

    # FAULT_POSITION has two senscases, east with value -1 and west with value 1,
    # so we expect ensemble_size number of rows with -1s and ensemble_size rows with 1s.
    # We expect the remaining rows to be set to the base value
    # set in the defaultvalues sheet.
    fault_position_base = diskdefaults.loc["FAULT_POSITION"].to_list()
    fault_position = (
        fault_position_base * ensemble_size
        + [-1] * ensemble_size
        + [1] * ensemble_size
        + fault_position_base * (rows_in_design_matrix - 3 * ensemble_size)
    )
    assert (diskdesign["FAULT_POSITION"] == fault_position).all()

    dc_model_base = diskdefaults.loc["DC_MODEL"].to_list()
    dc_model = (
        dc_model_base * 3 * ensemble_size
        + ["alternative"] * ensemble_size
        + dc_model_base * (rows_in_design_matrix - 4 * ensemble_size)
    )
    assert (diskdesign["DC_MODEL"] == dc_model).all()

    owc1_base = diskdefaults.loc["OWC1"].to_list()
    owc1 = (
        owc1_base * 4 * ensemble_size
        + [2600] * ensemble_size
        + [2700] * ensemble_size
        + owc1_base * (rows_in_design_matrix - 6 * ensemble_size)
    )
    assert (diskdesign["OWC1"] == owc1).all()

    owc2_base = diskdefaults.loc["OWC2"].to_list()
    owc2 = (
        owc2_base * 4 * ensemble_size
        + [2700] * ensemble_size
        + [2800] * ensemble_size
        + owc2_base * (rows_in_design_matrix - 6 * ensemble_size)
    )
    assert (diskdesign["OWC2"] == owc2).all()

    owc3_base = diskdefaults.loc["OWC3"].to_list()
    owc3 = (
        owc3_base * 4 * ensemble_size
        + [2800] * ensemble_size
        + [2900] * ensemble_size
        + owc3_base * (rows_in_design_matrix - 6 * ensemble_size)
    )
    assert (diskdesign["OWC3"] == owc3).all()

    # MULTZ_ILE contains random numbers so we won't test it here.


def test_generate_full_mc(tmpdir):
    """Test generation of full monte carlo"""
    inputfile = TESTDATA / "config/design_input_mc_with_correls.xlsx"
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
    assert Path("designmatrix.xlsx").exists
    diskdesign = pd.read_excel(
        "designmatrix.xlsx", sheet_name="DesignSheet01", engine="openpyxl"
    )
    assert "REAL" in diskdesign
    assert "SENSNAME" in diskdesign
    assert "SENSCASE" in diskdesign
    assert not diskdesign.empty

    diskdefaults = pd.read_excel(
        "designmatrix.xlsx", sheet_name="DefaultValues", engine="openpyxl"
    )
    assert not diskdefaults.empty
    assert len(diskdefaults.columns) == 2
