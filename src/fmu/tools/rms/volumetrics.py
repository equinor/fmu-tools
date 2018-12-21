# -*- coding: utf-8 -*-
"""Module for handling volumetrics text files from RMS""
from __future__ import print_function
"""

import os

import pandas as pd


def rmsvolumetrics_txt2df(txtfile, columnrenamer=None, phase=None,
                          outfile=None,
                          regionrenamer=None,
                          zonerenamer=None):
    """Parse the volumetrics txt file from RMS as Pandas dataframe

    Columns will be renamed according to FMU standard,
    https://wiki.statoil.no/wiki/index.php/FMU_standards

    Args:
        txtfile - string with path to file emitted by RMS Volumetrics job
        columnrenamer - dictionary for renaming column. Will be merged
            with a default renaming dictionary (anything specified here will
            override any defaults)
        phase - string stating typically 'GAS', 'OIL' or 'TOTAL', signifying
            which part of the reservoir model is included
        outfile - string with filename to write CSV data to.
            If directory does not exist, it will be made.
        regionrenamer - a function that when applied on strings, return a
            new string. If used, will be applied to every region value,
            using pandas.Series.apply()
        zonerenamer - ditto for the zone column

    The renamer functions could be defined like this

    def myregionrenamer(s):
        return s.replace('Equilibrium_region_', '')
    or the same using a lambda expression.

    Return:
        pandas.DataFrame
    """
    # First find out which row the data starts at:
    headerline = 0  # 0 is the first line
    with open(txtfile) as volfile:
        for line in volfile:
            if 'Zone' in line or 'Region' in line or 'Facies' in line:
                break
            else:
                headerline = headerline + 1
    vol_df = pd.read_table(txtfile, sep=r'\s\s+', skiprows=headerline,
                           engine='python')

    # Enforce FMU standard:
    # https://wiki.statoil.no/wiki/index.php/FMU_standards
    # on column names

    # The Real column from RMS is not real.. Ignore it.
    if 'Real' in vol_df.columns:
        vol_df.drop('Real', axis=1, inplace=True)

    if not phase:
        if 'oil' in txtfile:
            phase = 'OIL'
        elif 'gas' in txtfile:
            phase = 'GAS'
        elif 'total' in txtfile:
            phase = 'TOTAL'
        else:
            raise ValueError('You must supply phase for volumetrics-parsing')

    columns = {'Zone': 'ZONE', 'Region index': 'REGION',
               'Facies': 'FACIES', 'License boundaries': 'LICENSE',
               'Bulk': 'BULK_' + phase,
               'Net': 'NET_' + phase,
               'Hcpv': 'HCPV_' + phase,
               'Pore': 'PORE_' + phase,
               'Stoiip': 'STOIIP_' + phase,
               'Giip': 'GIIP_' + phase,
               'Assoc.Liquid': 'ASSOCIATEDOIL_' + phase,
               'Assoc.Gas': 'ASSOCIATEDGAS_' + phase}
    if columnrenamer:
        # Overwrite with user supplied column conversion
        columns.update(columnrenamer)
    vol_df.rename(columns, axis=1, inplace=True)

    # Work on the data itself:
    if regionrenamer:
        vol_df['REGION'] = vol_df['REGION'].apply(regionrenamer)
    if zonerenamer:
        vol_df['ZONE'] = vol_df['ZONE'].apply(zonerenamer)

    # Remove the Totals rows in case they are present.
    #  (todo: do this for all columns that are not not of numeric type)
    checkfortotals = ['ZONE', 'REGION', 'LICENSE', 'FACIES']

    totalsrows = pd.Series([False] * len(vol_df))
    for col in checkfortotals:
        if col in vol_df.columns:
            totalsrows = totalsrows | (vol_df[col] == 'Totals')
    vol_df = vol_df[~totalsrows].reset_index(drop=True)

    if outfile:
        if not os.path.exists(os.path.dirname(outfile)):
            os.makedirs(os.path.dirname(outfile))
        vol_df.to_csv(outfile, index=False)

    return vol_df
