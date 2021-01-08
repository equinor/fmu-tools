""" Module for summarizing design set up for one by one sensitivities """
import pandas as pd


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

    # Initialisation of dataframe to store results
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
    sensno = 0
    startreal1 = 0
    endreal1 = 0

    # Read design matrix and find realisation numbers for each sensitivity
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
    sensname = dgn.loc[0]["SENSNAME"]
    casename1 = dgn.loc[0]["SENSCASE"]
    if casename1.lower() == "p10_p90":
        senstype = "mc"
    elif casename1.lower() == "ref":
        senstype = "ref"
    else:
        senstype = "scalar"

    currentsensname = sensname
    currentsenscase = casename1
    # starting with first case
    secondcase = False
    casename2 = None
    startreal2 = None
    endreal2 = None

    for row in dgn.itertuples():
        if row.SENSNAME == currentsensname and row.SENSCASE == currentsenscase:
            if secondcase is True:
                endreal2 = row.REAL
            else:
                endreal1 = row.REAL
        elif row.SENSNAME == currentsensname:
            secondcase = True
            startreal2 = row.REAL
            endreal2 = row.REAL
            casename2 = row.SENSCASE
            currentsensname = row.SENSNAME
            currentsenscase = casename2
        else:
            if senstype != "skip":
                if secondcase is True:
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
                else:
                    designsummary.loc[sensno] = [
                        sensno,
                        sensname,
                        senstype,
                        casename1,
                        startreal1,
                        endreal1,
                        None,
                        None,
                        None,
                    ]
                    sensno += 1
            secondcase = False
            startreal1 = row.REAL
            endreal1 = row.REAL

            casename1 = row.SENSCASE
            sensname = row.SENSNAME
            currentsenscase = casename1
            currentsensname = sensname
            if row.SENSCASE.lower() == "p10_p90":
                senstype = "mc"
            elif row.SENSCASE.lower() == "skip":
                senstype = "skip"
            else:
                senstype = "scalar"

    # For last row
    if senstype != "skip":
        if secondcase is True:
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
        else:
            designsummary.loc[sensno] = [
                sensno,
                sensname,
                senstype,
                casename1,
                startreal1,
                endreal1,
                None,
                None,
                None,
            ]

    return designsummary
