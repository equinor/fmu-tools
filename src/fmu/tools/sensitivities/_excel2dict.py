# -*- coding: utf-8 -*-
"""Module for reading excel file with input for generation of
a design matrix and converting to an OrderedDict that can be
read by fmu.tools.DesignMatrix.generate
"""
from collections import OrderedDict
import numpy as np
import pandas as pd
from fmu.config import oyaml as yaml


def excel2dict_design(input_filename):
    """Read excel file with input to design setup
    Currently only specification of
    onebyone design is implemented

    Args:
        input_filename (str): Name of excel input file

    Returns:
        OrderedDict on formate for DesignMatrix.generate
    """
    generalinput = pd.read_excel(
        input_filename,
        'general_input',
        header=None,
        index_col=0)

    if str(generalinput[1]['designtype']) == 'onebyone':
        returndict = _excel2dict_onebyone(input_filename)
    else:
        raise ValueError('Generation of DesignMatrix only '
                         'implemented for type onebyone '
                         'In general_input designtype was '
                         'set to {}'.format(str(
                             generalinput[1]['designtype'])))
    return returndict


def inputdict_to_yaml(inputdict, filename):
    """Write inputdict to yaml format

    Args:
        inputdict (OrderedDict)
        filename (str): path for where to write file
    """
    stream = file(filename, 'w')
    yaml.dump(inputdict, stream)


def _excel2dict_onebyone(input_filename):
    """Reads spesification for onebyone design

    Args:
        input_filename(path): path to excel workbook

    Returns:
        OrderedDict on format for DesignMatrix.generate
    """

    inputdict = OrderedDict()

    # Read general input
    generalinput = pd.read_excel(
        input_filename,
        'general_input',
        header=None,
        index_col=0)

    inputdict['designtype'] = generalinput[1]['designtype']
    inputdict['seeds'] = generalinput[1]['seeds']
    inputdict['repeats'] = generalinput[1]['repeats']

    # Read background
    if 'background' in generalinput.index:
        inputdict['background'] = OrderedDict()
        if (
                generalinput[1]['background'].endswith('csv') or
                generalinput[1]['background'].endswith('xlsx')
        ):
            inputdict['background']['extern'] = generalinput[1]['background']
        elif str(generalinput[1]['background']) == 'None':
            inputdict['background'] = None
        else:
            inputdict['background'] = _read_background(
                input_filename, generalinput[1]['background'])
    else:
        inputdict['background'] = None

    # Read default values
    inputdict['defaultvalues'] = _read_defaultvalues(
        input_filename, 'defaultvalues')

    # Read input for sensitivities
    inputdict['sensitivities'] = OrderedDict()
    designinput = pd.read_excel(
        input_filename,
        'designinput')
    designinput['sensname'].fillna(method='ffill', inplace=True)

    # Read decimals
    if 'decimals' in designinput.keys():
        decimals = OrderedDict()
        for row in designinput.itertuples():
            if _has_value(row.decimals) and _is_int(row.decimals):
                decimals[row.param_name] = int(row.decimals)
        inputdict['decimals'] = decimals

    grouped = designinput.groupby('sensname', sort=False)
    # Read each sensitivity
    for sensname, group in grouped:

        sensdict = OrderedDict()

        if group['type'].iloc[0] == 'seed':
            sensdict['parametername'] = str(group['param_name'].iloc[0])
            sensdict['senstype'] = 'seed'

        elif group['type'].iloc[0] == 'scenario':
            sensdict = _read_scenario_sensitivity(group)
            sensdict['senstype'] = 'scenario'

        elif group['type'].iloc[0] == 'dist':
            sensdict['parameters'] = _read_dist_sensitivity(group)
            sensdict['senstype'] = 'dist'

        elif group['type'].iloc[0] == 'extern':
            sensdict['extern_file'] = str(group['extern_file'].iloc[0])
            sensdict['senstype'] = 'extern'
            sensdict['parameters'] = list(group['param_name'])

        else:
            raise ValueError(
                'Sensitivity {} does not have a valid sensitivity type'
                .format(sensname))

        if 'numreal' in group.keys():
            if _has_value(group['numreal'].iloc[0]):
                # Using default number of realisations:
                # 'repeats' from general_input sheet
                sensdict['numreal'] = int(group['numreal'].iloc[0])

        inputdict['sensitivities'][str(sensname)] = sensdict

    return inputdict


def _read_defaultvalues(filename, sheetname):
    """Reads defaultvalues, also used as values for
    reference/base case

    Args:
        filename(path): path to excel file
        sheetname (string): name of defaultsheet

    Returns:
        OrderedDict with defaultvalues (parameter, value)
    """
    default_dict = OrderedDict()
    default_df = pd.read_excel(
        filename,
        sheetname,
        header=0,
        index_col=0)
    for row in default_df.itertuples():
        default_dict[str(row[0])] = row[1]
    return default_dict


def _read_background(inp_filename, bck_sheet):
    """Reads excel sheet with background parameters and distributions

    Args:
        inp_filename (path): path to Excel workbook
        bck_sheet (str): name of sheet with background parameters

    Returns:
        OrderedDict with parameter names and distributions
    """
    backdict = OrderedDict()
    paramdict = OrderedDict()
    bck_input = pd.read_excel(
        inp_filename,
        bck_sheet)

    for row in bck_input.itertuples():
        distparams = [item for item in [
            row.dist_param1, row.dist_param2, row.dist_param3]
                      if _has_value(item)]
        paramdict[str(row.param_name)] = [str(row.dist_name), distparams]
    backdict['parameters'] = paramdict

    if ('corr_sheet' in bck_input.keys() and _has_value(
            bck_input['corr_sheet'][1])):
        backdict['correlations'] = bck_input['corr_sheet'][1]
    else:
        backdict['correlations'] = None

    if 'decimals' in bck_input.keys():
        decimals = OrderedDict()
        for row in bck_input.itertuples():
            if _has_value(row.decimals) and _is_int(row.decimals):
                decimals[row.param_name] = int(row.decimals)
        backdict['decimals'] = decimals

    return backdict


def _read_scenario_sensitivity(sensgroup):
    """Reads parameters and values
    for scenario sensitivities
    """
    sdict = OrderedDict()
    sdict['cases'] = OrderedDict()
    casedict1 = OrderedDict()
    casedict2 = OrderedDict()
    for row in sensgroup.itertuples():
        casedict1[str(row.param_name)] = row.value1
    if _has_value(sensgroup['senscase2'].iloc[0]):
        for row in sensgroup.itertuples():
            casedict2[str(row.param_name)] = row.value2
        sdict['cases'][
            str(sensgroup['senscase1'].iloc[0])] = casedict1
        sdict['cases'][
            str(sensgroup['senscase2'].iloc[0])] = casedict2
    else:
        sdict['cases'][
            str(sensgroup['senscase1'].iloc[0])] = casedict1
    return sdict


def _read_dist_sensitivity(sensgroup):
    """Reads parameters and distributions
    for monte carlo sensitivities
    """
    if 'dist_param1' not in sensgroup.columns.values:
        sensgroup['dist_param1'] = float('NaN')
    if 'dist_param2' not in sensgroup.columns.values:
        sensgroup['dist_param2'] = float('NaN')
    if 'dist_param3' not in sensgroup.columns.values:
        sensgroup['dist_param3'] = float('NaN')
    if 'dist_param4' not in sensgroup.columns.values:
        sensgroup['dist_param4'] = float('NaN')
    paramdict = OrderedDict()
    for row in sensgroup.itertuples():
        if not _has_value(row.dist_param1):
            raise ValueError('Parameter {} has been input '
                             'as type "dist" but with empty '
                             'first distribution parameter '
                             .format(row.param_name))
        if not _has_value(row.dist_param2) and _has_value(row.dist_param3):
            raise ValueError('Parameter {} has been input with '
                             'value for "dist_param3" while '
                             '"dist_param2" is empty. This is not '
                             'allowed'.format(row.param_name))
        if not _has_value(row.dist_param3) and _has_value(row.dist_param4):
            raise ValueError('Parameter {} has been input with '
                             'value for "dist_param4" while '
                             '"dist_param3" is empty. This is not '
                             'allowed'.format(row.param_name))
        distparams = [item for item in [
            row.dist_param1, row.dist_param2, row.dist_param3, row.dist_param4]
                      if _has_value(item)]
        paramdict[str(row.param_name)] = [str(row.dist_name), distparams]
    return paramdict


def _has_value(value):
    """Returns False if NaN"""
    return bool(value == value)


def _is_int(teststring):
    """ Test if a string can be parsed as a float"""
    try:
        if not np.isnan(int(teststring)):
            if (float(teststring) % 1) == 0:
                return True
            return False
        return False  # It was a "number", but it was NaN.
    except ValueError:
        return False
