# -*- coding: utf-8 -*-
"""Classes/functions to parse obscure files
    into pandas dataframes"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
import os
import pandas as pd


class RmsVolumeFileParser(object):
    """
    Parser for RMS volumes exported as ASCII

    Args:
        file_name: Full path to volume file
    Returns:
        Dataframe with standardized column names
    """

    def __init__(self, file_name):

        self.columntypes = {
            'ZONE': 'object',
            'REGION': 'object',
            'FACIES': 'object',
            'LICENSE': 'object',
            'BULK_OIL': 'float64',
            'NET_OIL': 'float64',
            'PORV_OIL': 'float64',
            'HCPV_OIL': 'float64',
            'STOIIP_OIL': 'float64',
            'ASSOCIATEDGAS_OIL': 'float64',
            'BULK_GAS': 'float64',
            'NET_GAS': 'float64',
            'PORV_GAS': 'float64',
            'HCPV_GAS': 'float64',
            'GIIP_GAS': 'float64',
            'ASSOCIATEDOIL_GAS': 'float64',
            'BULK_TOTAL': 'float64',
            'NET_TOTAL': 'float64',
            'PORV_TOTAL': 'float64'
        }
        self.columns = {'Zone': 'ZONE',
                        'Region_index': 'REGION',
                        'Facies': 'FACIES',
                        'License_boundaries': 'LICENSE'}

        self.oilcolumns = {'Bulk': 'BULK_OIL',
                           'Net': 'NET_OIL',
                           'Pore': 'PORV_OIL',
                           'Hcpv': 'HCPV_OIL',
                           'Stoiip': 'STOIIP_OIL',
                           'Assoc.Gas': 'ASSOCIATEDGAS_OIL'}

        self.gascolumns = {'Bulk': 'BULK_GAS',
                           'Net': 'NET_GAS',
                           'Pore': 'PORV_GAS',
                           'Hcpv': 'HCPV_GAS',
                           'Giip': 'GIIP_GAS',
                           'Assoc.Liquid': 'ASSOCIATEDOIL_GAS'}

        self.totalcolumns = {'Bulk': 'BULK_TOTAL',
                             'Net': 'NET_TOTAL',
                             'Pore': 'PORV_TOTAL'}
        self.file_name = file_name
        self.data = self.parse_rms_volume_file(self.file_name)

    @property
    def as_df(self):
        return self.data

    def find_header_line(self, lines):
        """Find first line in file containg a known column key"""
        headerline = -1
        for line in lines:
            headerline += 1
            for key, value in self.columns.iteritems():

                if key in line:
                    return headerline
        raise IOError("Header line not found.")

    def parse_rms_volume_file(self, file_name):
        """Parses the file"""
        if not os.path.exists(file_name):
            raise IOError("Volume report file does not exist {}".format(file_name))

        volfile = open(file_name, 'r')
        lines = volfile.readlines()
        lines = [line.replace('Region index', 'Region_index')
                 for line in lines]
        lines = [line.replace('License boundaries',
                              'License_boundaries') for line in lines]
        headerline = self.find_header_line(lines)
        header = lines[headerline]
        header = header.split()
        usedcolumns = self.columns
        usedcolumntypes = {}
        # Makes columnlist. It will either be oil, gas or totals
        if 'Stoiip' in header:
            usedcolumns.update(self.oilcolumns)
        elif 'Giip' in header:
            usedcolumns.update(self.gascolumns)
        else:
            usedcolumns.update(self.totalcolumns)
        # Checks which columns to use and pick up column dtypes to use
        for index, data in enumerate(header):
            for key, value in usedcolumns.iteritems():
                if key in data:
                    header[index] = data.replace(key, usedcolumns[key])
                    usedcolumntypes[usedcolumns[key]
                                   ] = self.columntypes[usedcolumns[key]]
        df = pd.DataFrame(columns=header)
        # Remove all lines with 'Totals'
        for i in range(headerline + 1, len(lines)):
            if not 'Totals' in lines[i]:
                values = lines[i].split()
                line = pd.Series(values, header)
                df = df.append(line, ignore_index=True)
        # Set column dtypes
        df = df.astype(usedcolumntypes)
        volfile.close()
        return df
