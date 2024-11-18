"""Module for summarizing design set up for one by one sensitivities"""

import pandas as pd


def _get_sensitivity_type(senscase: str) -> str:
    """Determine sensitivity type based on the case name"""
    sensitivity_types = {"p10_p90": "mc", "ref": "ref", "skip": "skip"}
    return sensitivity_types.get(senscase.lower(), "scalar")


def summarize_design(filename, sheetname="DesignSheet01"):
    """
     Summarizes the design set up for one by one sensitivities
     specified in a design matrix on standard fmu format.

    Args:
        filename (str): Path to excel or csv file containting designmatrix
            for one by one sensitivities on standard FMU format.
        sheetname (str): Name of sheet in excel workbook which
            contains the designmatrix (only for excel input). Defaults to
            'DesignSheet01'.

    Returns:
        pd.DataFrame: Summary of sensitivities,
        corresponding realisation numbers,
        senstype('mc' or 'scalar')
        and senscase (name of high and low cases).
        Each row represents one sensitivity
        with 1-2 cases (low/high).
        Column names are ['sensno', 'sensname',
        'senstype', 'casename1', 'startreal1', 'endreal1',
        'casename2', 'startreal2', 'endreal2']

    Example::
        >>> from fmu.tools.sensitivities import summarize_design
        >>> designname = 'design_filename.xlsx'
        >>> designsheet = 'DesignSheet01'
        >>> designtable = summarize_design(designname, designsheet)

    """

    # Read design matrix
    if str(filename).endswith(".xlsx"):
        dgn = pd.read_excel(filename, sheetname, engine="openpyxl")
        # Drop empty rows or columns that have been read in
        # due to having background colour/formatting
        dgn.dropna(axis=0, how="all", inplace=True)
        dgn = dgn.loc[:, ~dgn.columns.str.contains("^Unnamed")]
    elif str(filename).endswith(".csv"):
        dgn = pd.read_csv(filename)
    else:
        raise ValueError(
            "Design matrix must be on Excel or csv format"
            " and filename must end with .xlsx or .csv"
        )

    # Initialize results DataFrame with same columns
    designsummary = pd.DataFrame(
        columns=[
            "sensno",
            "sensname",
            "senstype",
            "casename1",
            "startreal1",
            "endreal1",
            "casename2",
            "startreal2",
            "endreal2",
        ]
    )

    # Get unique sensitivity names in order of appearance
    sensnames = dgn["SENSNAME"].unique()

    sensno = 0
    for sensname in sensnames:
        sens_group = dgn[dgn["SENSNAME"] == sensname].copy()
        # Get cases in order of appearance
        cases = sens_group.drop_duplicates("SENSCASE")[["SENSCASE"]].values.flatten()

        # Skip if first case type is 'skip'
        # The "skip" option was added when creating tornado plots
        # with calc_tornadoinput.
        # It allowed manual exclusion of sensitivities from tornado plots by changing
        # SENSCASE to "skip" in the design matrix after running the experiment.
        # This would exclude the sensitivity from both the
        # *designsummary table and the tornado plot.
        # calc_tornadoinput is deprecated so this can be removed once
        # calc_tornadoinput is removed.
        senstype = _get_sensitivity_type(cases[0])
        if senstype == "skip":
            continue

        # First case
        case1_data = sens_group[sens_group["SENSCASE"] == cases[0]]
        casename1 = cases[0]
        startreal1 = case1_data["REAL"].min()
        endreal1 = case1_data["REAL"].max()

        # Handle second case if it exists
        if len(cases) > 1:
            case2_data = sens_group[sens_group["SENSCASE"] == cases[1]]
            casename2 = cases[1]
            startreal2 = case2_data["REAL"].min()
            endreal2 = case2_data["REAL"].max()
        else:
            casename2 = None
            startreal2 = None
            endreal2 = None

        # Add row to results
        designsummary.loc[sensno] = [
            sensno,
            sensname,
            senstype,
            casename1,
            startreal1,
            endreal1,
            casename2,
            startreal2,
            endreal2,
        ]

        sensno += 1

    return designsummary
