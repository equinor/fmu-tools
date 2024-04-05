"""Example use cases for fmudesign"""

import pandas as pd
import pytest
from fmu.tools._common import preserve_cwd
from fmu.tools.sensitivities import DesignMatrix, excel2dict_design
from packaging import version


@preserve_cwd
@pytest.mark.skipif(
    version.parse(pd.__version__) < version.parse("0.25.0"),
    reason="Pandas 0.25.0 is required for fmudesign",
)
def test_prediction_rejection_sampled_ensemble(tmpdir):
    """Test making a design matrix for prediction realizations based on an
    ensemble made with manual history matching (rejection sampling).

    In the use-case this test is modelled on, the design matrix is used
    to set up a prediction ensemble where each DATA file points to another
    Eclipse run on disk which contains the history, identified by the
    realization index ("HMREAL") in the history match run.
    """
    tmpdir.chdir()
    general_input = pd.DataFrame(
        data=[
            ["designtype", "onebyone"],
            ["repeats", 3],  # This matches the number of HM-samples we have.
            ["rms_seeds", None],  # Geogrid from HM realization is used
            ["background", "hmrealizations.xlsx"],
            ["distribution_seed", None],
        ]
    )
    defaultvalues = pd.DataFrame(
        columns=["param_name", "default_value"],
        data=[
            # All background parameters must be mentioned in
            # DefaultValues (but these defaults are not used in
            # this particular test scenario)
            ["HMREAL", "-1"],
            ["ORAT", 6000],
            ["RESTARTPATH", "FOO"],
            ["HMITER", "-1"],
        ],
    )

    # Background to separate file, these define some history realizations that
    # all scenarios should run over:
    pd.DataFrame(
        columns=["RESTARTPATH", "HMREAL", "HMITER"],
        data=[
            ["/scratch/foo/2020a_hm3/", 31, 3],
            ["/scratch/foo/2020a_hm3/", 38, 3],
            ["/scratch/foo/2020a_hm3/", 54, 3],
        ],
    ).to_excel("hmrealizations.xlsx")

    writer = pd.ExcelWriter("designinput.xlsx", engine="openpyxl")
    general_input.to_excel(writer, sheet_name="general_input", index=False, header=None)
    pd.DataFrame(
        columns=[
            "sensname",
            "numreal",
            "type",
            "param_name",
            "dist_name",
            "dist_param1",
            "dist_param2",
        ],
        data=[
            ["ref", None, "background", None],
            ["oil_rate", None, "dist", "ORAT", "uniform", 5000, 9000],
        ],
    ).to_excel(writer, sheet_name="design_input", index=False)
    defaultvalues.to_excel(writer, sheet_name="defaultvalues", index=False)
    writer.close()

    dict_design = excel2dict_design("designinput.xlsx")
    design = DesignMatrix()
    design.generate(dict_design)

    assert set(design.designvalues["RESTARTPATH"]) == {"/scratch/foo/2020a_hm3/"}
    assert set(design.designvalues["HMITER"]) == {3}
    assert all(design.designvalues["REAL"] == [0, 1, 2, 3, 4, 5])
    assert all(
        design.designvalues["SENSNAME"]
        == [
            "ref",
            "ref",
            "ref",
            "oil_rate",
            "oil_rate",
            "oil_rate",
        ]
    )

    # This is the most important bit in this test function, that the realization
    # list in the background xlsx is repeated for each sensitivity:
    assert all(design.designvalues["HMREAL"] == [31, 38, 54, 31, 38, 54])
