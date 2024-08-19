from pathlib import Path

import pandas as pd
import pytest
from packaging import version

from fmu.tools.sensitivities import calc_tornadoinput, summarize_design

TESTDATA = Path(__file__).parent / "data"


@pytest.mark.skipif(
    version.parse(pd.__version__) < version.parse("0.25.0"),
    reason="Pandas 0.25.0 is required for fmudesign",
)
def test_designsummary():
    """Test import and summary of design matrix"""

    snorrebergdesign = summarize_design(
        TESTDATA / "distributions/design.xlsx", "DesignSheet01"
    )
    # checking dimensions and some values in summary of design matrix
    assert snorrebergdesign.shape == (7, 9)
    assert snorrebergdesign["sensname"][0] == "rms_seed"
    assert snorrebergdesign["startreal2"][6] == 100
    assert snorrebergdesign["endreal2"][6] == 109
    assert snorrebergdesign["endreal1"].sum() == 333

    # Test same also when design matrix is in .csv format
    designcsv = summarize_design(TESTDATA / "distributions/design.csv")

    # checking dimensions and some values in summary of design matrix
    assert designcsv.shape == (7, 9)
    assert designcsv["sensname"][0] == "rms_seed"
    assert designcsv["startreal2"][6] == 100
    assert designcsv["endreal2"][6] == 109
    assert designcsv["endreal1"].sum() == 333


def test_calc_tornadoinput():
    """Test calculating values for tornadoplot input"""
    # Read file with summary of design
    summary = pd.read_csv(TESTDATA / "distributions/designsummary.csv", na_values="nan")
    des_summary = summary.where(pd.notnull(summary), None)

    # Read resultfile for the test ensemble
    results = pd.read_csv(TESTDATA / "results/geovolumes_collected.csv")

    # Calculate and check results of one tornado calculation
    (tornadotable, ref_value) = calc_tornadoinput(
        des_summary,
        results,
        "STOIIP_OIL",
        ["ITER", "ZONE", "REGION"],
        [["iter-0"], ["Nansen", "Larsson"], ["oil_zone_Nansen_Larsson"]],
        "rms_seed",
        "percentage",
    )

    assert int(tornadotable["low"].sum()) == -21
    assert int(tornadotable["high"].sum()) == 11
    assert int(ref_value) == 9330662

    # Check summing over all zones and regions before calculations
    (tornadotable, ref_value) = calc_tornadoinput(
        des_summary,
        results,
        "STOIIP_OIL",
        ["ITER", "ZONE", "REGION"],
        [["all"], ["all"], ["all"]],
        "rms_seed",
        "absolute",
    )

    assert int(tornadotable["low"].sum()) == -2142167
    assert int(tornadotable["high"].sum()) == 1478053
    assert int(ref_value) == 12855200
