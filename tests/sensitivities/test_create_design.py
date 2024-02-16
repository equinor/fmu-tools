"""Testing code for generation of design matrices"""

from pathlib import Path

import pandas as pd
import pytest
from fmu.tools.sensitivities import DesignMatrix, excel2dict_design
from packaging import version

TESTDATA = Path(__file__).parent / "data"


@pytest.mark.skipif(
    version.parse(pd.__version__) < version.parse("0.25.0"),
    reason="Pandas 0.25.0 is required for fmudesign",
)
def test_generate_onebyone(tmpdir):
    """Test generation of onebyone design"""

    inputfile = TESTDATA / "config/design_input_example1.xlsx"
    input_dict = excel2dict_design(inputfile)

    design = DesignMatrix()
    design.generate(input_dict)
    # Checking dimensions of design matrix
    assert design.designvalues.shape == (80, 10)

    # Write to disk and check some validity
    tmpdir.chdir()
    design.to_xlsx("designmatrix.xlsx")
    assert Path("designmatrix.xlsx").exists
    diskdesign = pd.read_excel("designmatrix.xlsx", engine="openpyxl")
    assert "REAL" in diskdesign
    assert "SENSNAME" in diskdesign
    assert "SENSCASE" in diskdesign
    assert not diskdesign.empty

    diskdefaults = pd.read_excel(
        "designmatrix.xlsx", sheet_name="DefaultValues", engine="openpyxl"
    )
    assert not diskdefaults.empty
    assert len(diskdefaults.columns) == 2


@pytest.mark.skipif(
    version.parse(pd.__version__) < version.parse("0.25.0"),
    reason="Pandas 0.25.0 is required for fmudesign",
)
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
