# -*- coding: utf-8 -*-
""" Module for summarizing design set up for
one by one sensitivities """
from __future__ import print_function, absolute_import
import pandas as pd


def summarize_design(filename, sheetname='DesignSheet01'):
    """
     Summarizes the design set up for one by one sensitivities
     specified in a design matrix on standard fmu format.

    :returns: A pandas dataframe with summary of sensitivities,
     corresponding realisation numbers, senstype('mc' or 'scalar')
     and senscase (name of high and low cases).
     Each row represents one sensitivity with 1-2 cases (low/high)
    :param filename: path to excel or csv file containting designmatrix
    :param sheetname: if excel input, name of sheet in excel workbook that
     contains the designmatrix
    """

    # Initialisation of dataframe to store results
    designsummary = pd.DataFrame(columns=['sensno', 'sensname',
                                          'senstype', 'casename1',
                                          'startreal1', 'endreal1',
                                          'casename2', 'startreal2',
                                          'endreal2'])
    sensno = 0
    startreal1 = 0
    endreal1 = 0

    # Read design matrix and find realisation numbers for each sensitivity
    if filename.endswith('.xlsx'):
        dgn = pd.read_excel(filename, sheetname)
    elif filename.endswith('.csv'):
        dgn = pd.read_csv(filename)
    else:
        raise ValueError(
            'Design matrix filename should be on Excel or csv format'
            ' and end with .xlsx or .csv')

    # Check whether realisation 0 is a seed P10_P90 realisation
    if (dgn.loc[0]['SENSNAME'] == 'seed' and
            dgn.loc[0]['SENSCASE'] == 'P10_P90'):
        sensname = 'seed'
        casename1 = 'P10_P90'
        senstype = 'mc'
    else:
        print('warning: did not find seed case at realization 0. \n')
        print('was expecting sensename "seed" and')
        print('senstype "P10_P90" as first sensitivity')
        sensname = dgn.loc[0]['SENSNAME']
        casename1 = dgn.loc[0]['SENSCASE']
        if casename1 == 'P10_P90':
            senstype = 'mc'
        else:
            senstype = 'scalar'

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
            if senstype != 'skip':
                if secondcase is True:
                    designsummary.loc[sensno] = [sensno, sensname, senstype,
                                                 casename1, startreal1,
                                                 endreal1, casename2,
                                                 startreal2, endreal2]
                    sensno += 1
                else:
                    designsummary.loc[sensno] = [sensno, sensname,
                                                 senstype, casename1,
                                                 startreal1, endreal1,
                                                 None, None, None]
                    sensno += 1
            secondcase = False
            startreal1 = row.REAL
            endreal1 = row.REAL

            casename1 = row.SENSCASE
            sensname = row.SENSNAME
            currentsenscase = casename1
            currentsensname = sensname
            if row.SENSCASE == 'P10_P90':
                senstype = 'mc'
            elif row.SENSCASE.lower() == 'skip':
                senstype = 'skip'
            else:
                senstype = 'scalar'

    # For last row
    if senstype != 'skip':
        if secondcase is True:
            designsummary.loc[sensno] = [sensno, sensname, senstype,
                                         casename1, startreal1, endreal1,
                                         casename2, startreal2, endreal2]
        else:
            designsummary.loc[sensno] = [sensno, sensname, senstype,
                                         casename1, startreal1, endreal1,
                                         None, None, None]

    return designsummary
