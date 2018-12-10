# -*- coding: utf-8 -*-
"""Module for generating design matrices that can be run by DESIGN2PARAMS
and DESIGN_KW in FMU/ERT.
"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from collections import OrderedDict
import pandas as pd
from fmu.tools.sensitivities import design_distributions as design_dist


class DesignMatrix(object):
    """Class for design matrix in FMU. Can contain a onebyone design
    or a full montecarlo design.

    Attributes:
        designvalues (DataFrame): design matrix on standard fmu format
            contains columns 'REAL' (realization number), and if a onebyone
            design, also columns 'SENSNAME' and 'SENSCASE'
        defaultvalues (OrderedDictionary): default values for design
        backgroundvalues (DataFrame): Used when background parameters are
            not constant. Either a set is sampled from specified distributions
            or they are read from a file.
    """

    def __init__(self):
        """
        Placeholders for:
        designvalues: dataframe with parameters that varies
        defaultvalues: dictionary of default/base case values
        backgroundvalues: dataframe with background parameters
        """
        self.designvalues = pd.DataFrame(columns=['REAL'])
        self.defaultvalues = OrderedDict()
        self.backgroundvalues = None

    def generate(self, inputdict):
        """Generating design matrix from input dictionary in specific
        format. Adding default values and background values if existing.
        Looping through sensitivities and adding them to designvalues.

        Args:
            inputdict (OrderedDict): input parameters for design
        """
        seedtype = inputdict['seeds']
        default_dict = inputdict['defaultvalues']
        self.set_defaultvalues(default_dict)

        # If background values used - read or generate
        if 'background' in inputdict.keys():
            max_background_values = inputdict['repeats']
            for key in inputdict['sensitivities'].keys():
                sens = inputdict['sensitivities'][key]
                if 'numreal' in sens.keys():
                    max_background_values = max(
                        sens['numreal'], max_background_values)
            self.add_background(
                inputdict['background'], max_background_values)

        if inputdict['designtype'] == 'onebyone':
            self.designvalues['SENSNAME'] = None
            self.designvalues['SENSCASE'] = None
            counter = 0
            for key in inputdict['sensitivities'].keys():
                sens = inputdict['sensitivities'][key]
                if 'numreal' in sens.keys():
                    numreal = sens['numreal']
                else:
                    numreal = inputdict['repeats']
                if sens['senstype'] == 'ref':
                    sensitivity = SingleRealisationReference(key)
                    sensitivity.generate(
                        range(counter, counter + numreal))
                    counter += numreal
                    self._add_sensitivity(sensitivity)
                elif sens['senstype'] == 'background':
                    sensitivity = BackgroundSensitivity(key)
                    sensitivity.generate(
                        range(counter, counter + numreal))
                    counter += numreal
                    self._add_sensitivity(sensitivity)
                elif sens['senstype'] == 'seed':
                    sensitivity = SeedSensitivity(key)
                    sensitivity.generate(
                        range(counter, counter + numreal),
                        sens['seedname'], seedtype,
                        sens['parameters'])
                    counter += numreal
                    self._add_sensitivity(sensitivity)
                elif sens['senstype'] == 'scenario':
                    sensitivity = ScenarioSensitivity(key)
                    for casekey in sens['cases'].keys():
                        case = sens['cases'][casekey]
                        temp_case = ScenarioSensitivityCase(casekey)
                        temp_case.generate(
                            range(counter, counter+numreal),
                            case, seedtype)
                        sensitivity.add_case(temp_case)
                        counter += numreal
                    self._add_sensitivity(sensitivity)
                elif sens['senstype'] == 'dist':
                    if 'correlations' not in sens.keys():
                        sens['correlations'] = None
                    if sens['correlations'] is not None:
                        correlations = design_dist.read_correlations(
                            sens['correlations'])
                    else:
                        correlations = None
                    sensitivity = MonteCarloSensitivity(key)
                    sensitivity.generate(
                        range(counter, counter + numreal),
                        sens['parameters'], seedtype, correlations)
                    counter += numreal
                    self._add_sensitivity(sensitivity)
                elif sens['senstype'] == 'extern':
                    sensitivity = ExternSensitivity(key)
                    sensitivity.generate(
                        range(counter, counter + numreal),
                        sens['extern_file'],
                        sens['parameters'], seedtype)
                    counter += numreal
                    self._add_sensitivity(sensitivity)
                print('Added sensitivity :', sensitivity.sensname)
            if 'background' in inputdict.keys():
                self._fill_with_background_values()
            self._fill_with_defaultvalues()
            if 'decimals' in inputdict.keys():
                self._set_decimals(inputdict['decimals'])
        else:
            raise ValueError('Generation of DesignMatrix only'
                             'implemented for type onebyone'
                             'In general_input designtype is'
                             'set to {}'.format(inputdict['designtype']))

    def to_xlsx(self, filename,
                designsheet='DesignSheet01',
                defaultsheet='DefaultValues'):
        """Writing design matrix to excel workfbook on standard fmu format
        to be used in FMU/ERT by DESIGN2PARAMS and DESIGN_KW

        Args:
            filename (string): output filename (extension .xlsx)
            designsheet (string): name of excel sheet containing design matrix
                (optional, defaults to 'DesignSheet01')
            defaultsheet (string): name of excel sheet containing default
                values (optional, defaults to 'DefaultValues')
        """
        xlsxwriter = pd.ExcelWriter(filename)
        self.designvalues.to_excel(
            xlsxwriter, sheet_name=designsheet, index=False, header=True)
        # Default values from OrderdDictionay to pandas dataframe
        defaults = pd.DataFrame(columns=['defaultparameters', 'defaultvalue'])
        defaults['defaultparameters'] = self.defaultvalues.keys()
        defaults['defaultvalue'] = self.defaultvalues.values()
        defaults.to_excel(xlsxwriter, sheet_name=defaultsheet,
                          index=False, header=False)
        xlsxwriter.save()
        print('Designmatrix written to {}'.format(filename))

    def set_defaultvalues(self, defaults):
        """ Add default values

        Args:
            defaults (OrderedDict): (key, value) is (parameter_name, value)
        """
        self.defaultvalues = defaults

    def add_background(self, back_dict, max_values):
        """Adding background as specified in dictionary.
        Either from external file or from distributions in background
        dictionary

        Args:
            back_dict (OrderedDict): how to generate background values
            max_values (int): number of background values to generate
        """
        if back_dict is None:
            self.backgroundvalues = None
        elif 'extern' in back_dict.keys():
            self.backgroundvalues = _parameters_from_extern(
                back_dict['extern'])
        elif 'parameters' in back_dict.keys():
            self._add_dist_background(back_dict, max_values)

    def background_to_excel(self, filename,
                            backgroundsheet='Background'):
        """Writing background values to an Excel spreadsheet

        Args:
            filename (string): output filename (extension .xlsx)
            backgroundsheet (string): name of excel sheet
        """
        xlsxwriter = pd.ExcelWriter(filename)
        self.backgroundvalues.to_excel(
            xlsxwriter, sheet_name=backgroundsheet, index=False, header=True)
        xlsxwriter.save()
        print('Backgroundvalues written to {}'.format(filename))

    def _add_sensitivity(self, sensitivity):
        """Adding a sensitivity to the design

        Args:
            sensitivity of class Scenario, MonteCarlo or Extern
        """
        existing_values = self.designvalues.copy()
        self.designvalues = existing_values.append(
            sensitivity.sensvalues, sort=False)

    def _fill_with_background_values(self):
        """Substituting NaNs with background values if existing.
        background values not in design are added as separate colums
        """
        if self.backgroundvalues is not None:
            grouped = self.designvalues.groupby(
                ['SENSNAME', 'SENSCASE'], sort=False)
            result_values = pd.DataFrame()
            for sensname, case in grouped:
                temp_df = case.reset_index()
                temp_df.fillna(self.backgroundvalues, inplace=True)
                temp_df.set_index('index')
                for key in self.backgroundvalues.keys():
                    if key not in case.keys():
                        temp_df[key] = self.backgroundvalues[key]
                        if len(temp_df) > len(self.backgroundvalues):
                            raise ValueError(
                                'Provided number of background values '
                                '{} is smaller than number'
                                ' of realisations for sensitivity {}'
                                .format(len(self.backgroundvalues), sensname))
                    else:
                        if len(temp_df) > len(self.backgroundvalues):
                            print(
                                'Provided number of background values '
                                '({}) is smaller than number'
                                ' of realisations for sensitivity {}'
                                ' and parameter {}. '
                                'Will be filled with default values.'
                                .format(
                                    len(self.backgroundvalues),
                                    sensname,
                                    key))
                existing_values = result_values.copy()
                result_values = existing_values.append(
                    temp_df, sort=False)

            result_values = result_values.drop(['index'], axis=1)
            self.designvalues = result_values

    def _fill_with_defaultvalues(self):
        """Filling NaNs with default values"""
        for key in self.designvalues.keys():
            if key in self.defaultvalues.keys():
                self.designvalues[key].fillna(
                    self.defaultvalues[key], inplace=True)
            elif key not in ['REAL', 'SENSNAME', 'SENSCASE', 'RMS_SEED']:
                print('No defaultvalues given for {}'.format(key))

    def _add_dist_background(self, back_dict, numreal):
        """Drawing background values from distributions
        specified in dictionary

        Args:
            back_dict (OrderedDict): parameters and distributions
            numreal (int): Number of samples to generate
        """
        if back_dict['correlations'] is not None:
            correlations = design_dist.read_correlations(
                back_dict['correlations'])
        else:
            correlations = None
        mc_background = MonteCarloSensitivity('background')
        mc_background.generate(
            range(numreal),
            back_dict['parameters'], 'None', correlations)
        mc_backgroundvalues = mc_background.sensvalues

        # Rounding of background values as specified
        if 'decimals' in back_dict.keys():
            for key in back_dict['decimals'].keys():
                if design_dist.is_number(
                        mc_backgroundvalues[key].iloc[0]):
                    mc_backgroundvalues[key] = (
                        mc_backgroundvalues[key].astype(float).
                        round(int(back_dict['decimals'][key])))
                else:
                    raise ValueError('Cannot round a string parameter')
        self.backgroundvalues = mc_backgroundvalues.copy()

    def _set_decimals(self, dict_decimals):
        """Rounding to specified number of decimals

        Args:
            dict_decimals (dictionary): (key, value)s are (param, decimals)
        """
        for key in self.designvalues.keys():
            if key in dict_decimals.keys():
                if design_dist.is_number(
                        self.designvalues[key].iloc[0]):
                    self.designvalues[key] = (
                        self.designvalues[key].astype(float).
                        round(int(dict_decimals[key])))
                else:
                    raise ValueError(
                        'Cannot round a string parameter {}'.format(key))


class SeedSensitivity(object):
    """
    A seed sensitivity is normally the reference for one by one sensitivities
    It contains a list of seeds to be repeated for each sensitivity
    The parameter name is hardcoded to RMS_SEED
    It will be assigned the sensname 'p10_p90' which will be written to
    the SENSCASE column in the output.

    Attributes:
        sensname (str): name of sensitivity
        sensvalues (dataframe):  design values for the sensitivity

    """

    def __init__(self, sensname):
        """Args:
                sensname (str): Name of sensitivity.
                    Defines SENSNAME in design matrix
        """
        self.sensname = sensname
        self.sensvalues = None

    def generate(self, realnums, seedname, seeds, parameters):
        """Generates parameter values for a seed sensitivity

        Args:
            realnums (list): list of intergers with realization numbers
            param_name (str):
            seeds (str): default or xtern
        """
        self.sensvalues = pd.DataFrame(index=realnums)
        if seeds.lower() == 'default':
            seed_numbers = [nmr + 1000 - realnums[0] for nmr in realnums]
            self.sensvalues[seedname] = seed_numbers
        elif seeds.lower() == 'extern':
            print('TO DO: Implement read from external seeds')
        else:
            raise ValueError(
                'Only default and extern are valid choices for a'
                'seed sensitivity. Specified "{}" cannot be used'
                .format(seeds))
        if parameters is not None:
            for key in parameters.keys():
                dist_name = parameters[key][0].lower()
                constant = parameters[key][1]
                if dist_name != 'const':
                    raise ValueError(
                        'A sensitivity of type "seed" can only have '
                        'additional parameters where dist_name is '
                        '"const". Check sensitivity {}"'
                        .format(self.sensname))
                else:
                    self.sensvalues[key] = constant

        self.sensvalues['REAL'] = realnums
        self.sensvalues['SENSNAME'] = self.sensname
        self.sensvalues['SENSCASE'] = 'p10_p90'


class SingleRealisationReference(object):
    """
    The class is used in set-ups where one wants a single realisation
    containing only default values as a reference, but the realisation
    itself is not included in a sensitivity.
    Typically used when RMS_SEED is not a parameter.
    SENSCASE will be set to 'ref' in design matrix, to flag that it should be
    excluded as a sensitivity in the plot.

    Attributes:
        sensname (str): name of sensitivity
        sensvalues (dataframe):  design values for the sensitivity

    """

    def __init__(self, sensname):
        """Args:
                sensname (str): Name of sensitivity.
                    Defines SENSNAME in design matrix
        """
        self.sensname = sensname
        self.sensvalues = None

    def generate(self, realnums):
        """Generates realisation number only

        Args:
            realnums (list): list of intergers with realization numbers
        """
        self.sensvalues = pd.DataFrame(index=realnums)
        self.sensvalues['REAL'] = realnums
        self.sensvalues['SENSNAME'] = self.sensname
        self.sensvalues['SENSCASE'] = 'ref'


class BackgroundSensitivity(object):
    """
    The class is used in set-ups where one sensitivities
    are run on top of varying background parameters.
    Typically used when RMS_SEED is not a parameter, so the reference
    for tornadoplots will be the realisations with all parameters
    at their default values except the background parameters.
    SENSCASE will be set to 'p10_p90' in design matrix.

    Attributes:
        sensname (str): name of sensitivity
        sensvalues (dataframe):  design values for the sensitivity

    """

    def __init__(self, sensname):
        """Args:
                sensname (str): Name of sensitivity.
                    Defines SENSNAME in design matrix
        """
        self.sensname = sensname
        self.sensvalues = None

    def generate(self, realnums):
        """Generates realisation number only

        Args:
            realnums (list): list of intergers with realization numbers
        """
        self.sensvalues = pd.DataFrame(index=realnums)
        self.sensvalues['REAL'] = realnums
        self.sensvalues['SENSNAME'] = self.sensname
        self.sensvalues['SENSCASE'] = 'p10_p90'


class ScenarioSensitivity(object):
    """Each design can contain one or several single sensitivities of type
    Seed, MonteCarlo or Scenario.
    Each ScenarioSensitivity can contain 1-2 ScenarioSensitivityCases.

    The ScenarioSensitivity class is used for sensitivities where all
    realizatons in a ScenarioSensitivityCase have identical values
    but one or more parameter has a different values from the other
    ScenarioSensitivityCase.

    Exception is the seed value and the special case where
    varying background parameters are specified. Then these are varying
    within the case.

    Attributes:
        case1 (ScenarioSensitivityCase): first case, e.g. 'low case'
        case2 (ScenarioSensitivityCase): second case, e.g. 'high case'
        sensvalues(DataFrame): design values for the sensitivity, containing
           1-2 cases
    """

    def __init__(self, sensname):
        """
        Args:
            sensname (str): Name of sensitivity.
                Equals SENSNAME in design matrix
        """
        self.sensname = sensname
        self.case1 = None
        self.case2 = None
        self.sensvalues = None

    def add_case(self, senscase):
        """
        Adds a ScenarioSensitivityCase instance
        to a ScenarioSensitivity object.

        Args:
            senscase (ScenarioSensitivityCase):
                Equals SENSCASE in design matrix.
        """
        if self.case1 is not None:  # Case 1 has been read, this is case2
            if (
                    'REAL' in senscase.casevalues.keys() and
                    'SENSCASE' in senscase.casevalues.keys()):
                self.case2 = senscase
                senscase.casevalues['SENSNAME'] = self.sensname
                self.sensvalues = pd.concat([
                    self.sensvalues, senscase.casevalues],
                                            sort=True)
        else:  # This is the first case
            if (
                    'REAL' in senscase.casevalues.keys()
                    and 'SENSCASE' in senscase.casevalues.keys()):
                self.case1 = senscase
                self.sensvalues = senscase.casevalues.copy()
                self.sensvalues['SENSNAME'] = self.sensname


class ScenarioSensitivityCase(object):
    """Each ScenarioSensitivity can contain one or
    two ScenarioSensitivityCases.

    The 1-2 cases are typically 'low' and 'high' cases for one or
    a set of  parameters, where all realisatons in
    the case have identical values except the seed value
    and in special cases specified background values which may
    vary within the case.

    One or two ScenarioSensitivityCase instances can be added to each
    ScenarioSensitivity object.

    TO DO: Add possibility to provide external list of seeds.

    Attributes:
        casename (str): name of the sensitivity case,
                        equals SENSCASE in design matrix
        casevalues (pandas Dataframe): parameters and values
            for the sensitivity
            with realisation numbers as index.

    """

    def __init__(self, casename):
        self.casename = casename
        self.casevalues = None

    def generate(self, realnums, parameters, seeds):
        """Generate casevalues for the ScenarioSensitivityCase

            Args:
                realnums (list): list of realizaton numbers for the case
                parameters (OrderedDict):
                    dictionary with parameter names and values
                seeds (str): default or None
        """

        self.casevalues = pd.DataFrame(
            columns=parameters.keys(), index=realnums)
        for key in parameters.keys():
            self.casevalues[key] = parameters[key]
        self.casevalues['REAL'] = realnums
        self.casevalues['SENSCASE'] = self.casename
        self._add_seeds(realnums, seeds)

    def _add_seeds(self, realnums, seeds, seedstart=1000):
        """ When running sensitivities with repeating seeds
        the same list of seed numbers are used for all cases.
        Here RMS_SEED is generated and added as a column in  casevalues

        Args:
            realnums (list): list of realization numbers
                for the sensitivity case
            seeds (str): chose between 'default' 1000-1001-1002-...
                'None' (No seed added) or 'extern'
            seedstart (int): First seed value
        """

        if seeds != 'None':
            if seeds.lower() == 'default':
                seed_numbers = [nmr + seedstart - realnums[0]
                                for nmr in realnums]
                self.casevalues['RMS_SEED'] = seed_numbers
            elif seeds.lower() == 'extern':
                print('TO DO: Reed from external seeds')
            else:
                raise ValueError(
                    'Only "default" and "extern" or None are valid choices'
                    'for seeds in general_input. Given value was {}'
                    .format(seeds))


class MonteCarloSensitivity(object):
    """
    For a MonteCarloSensitivity one or several parameters
    are drawn from specified distributions with or without correlations.
    A MonteCarloSensitivity can only contain
    one case, where the name SENSCASE is automatically set to 'p10_p90' in the
    design matrix to flag that p10_p90 should be calculated in TornadoPlot.

    Attributes:
        sensname (string):  name for the sensitivity.
            Equals SENSNAME in design matrix.
        sensvalues (DataFrame):  parameters and values for the sensitivity
            with realisation numbers as index.
    """

    def __init__(self, sensname):
        self.sensname = sensname
        self.sensvalues = None

    def generate(self, realnums, parameters,
                 seeds, correlations=None):
        """Generates parameter values by drawing from
        defined distributions.

        Args:
            realnums (list): list of intergers with realization numbers
            parameters (OrderedDict):
                dictionary of parameters and distributions
            seeds (str): default or None
            correlations: matrix with correlations.
        """
        self.sensvalues = pd.DataFrame(
            columns=parameters.keys(), index=realnums)
        if correlations is None:
            for key in parameters.keys():
                dist_name = parameters[key][0].lower()
                dist_params = parameters[key][1]
                if dist_name == 'const':
                    mc_values = [dist_params[0]] * len(realnums)
                elif dist_name == 'discrete':
                    mc_values = design_dist.sample_discrete(
                        dist_params, len(realnums))
                else:
                    distribution = design_dist.prepare_distribution(
                        dist_name, dist_params)
                    mc_values = design_dist.generate_mcvalues(
                        distribution, len(realnums))
                    if dist_name == 'logunif':  # not in scipy, uses unif
                        mc_values = 10**mc_values
                self.sensvalues[key] = mc_values
        else:
            numreals = len(realnums)  # number of realizations
            self.sensvalues = design_dist.mc_correlated(
                parameters, correlations, numreals)

        if self.sensname != 'background':
            self.sensvalues['REAL'] = realnums
            self.sensvalues['SENSNAME'] = self.sensname
            self.sensvalues['SENSCASE'] = 'p10_p90'
            self._add_seeds(realnums, seeds)

    def _add_seeds(self, realnums, seeds, seedstart=1000):
        """Add RMS_SEED as column.

        TO DO: Add option to read seeds from external file

        Args:
            realnums (list): list of realization numbers
                for the sensitivity case
            seeds (str): chose between 'default' 1000-1001-1002-...
                'None' (No seed added) or 'extern'
            seedstart (int): First seed value
        """

        if seeds != 'None':
            if seeds.lower() == 'default':
                seed_numbers = [nmr + seedstart - realnums[0]
                                for nmr in realnums]
                self.sensvalues['RMS_SEED'] = seed_numbers
            elif seeds.lower() == 'extern':
                print('TO DO: Read from external seeds')
            else:
                raise ValueError(
                    'Only "default", "extern" or None are valid choices'
                    'for seeds in general_input. Given value was {}'
                    .format(seeds))


class ExternSensitivity(object):
    """
    Used when reading parameter values from a file
    Assumed to be used with monte carlo type sensitivities and
    will hence write 'p10_p90' as SENSCASE in output designmatrix

    Attributes:
        sensname (str): Name of sensitivity.
            Defines SENSNAME in design matrix
        sensvalues (dataframe):  design values for the sensitivity

    """

    def __init__(self, sensname):
        self.sensname = sensname
        self.sensvalues = None

    def generate(self, realnums, filename, parameters,
                 seeds):
        """Reads parameter values for a monte carlo sensitivity
        from file

        Args:
            realnums (list): list of intergers with realization numbers
            filename (string): path where to read values from
            parameters (list): list with parameter names
            seeds (str): default or None
        """
        self.sensvalues = pd.DataFrame(
            columns=parameters, index=realnums)
        extern_values = _parameters_from_extern(filename)
        if len(realnums) > len(extern_values):
            raise ValueError(
                'Number of realisations {} specified for '
                'sensitivity {} is larger than rows in '
                'file {}'.format(
                    len(realnums), self.sensname, filename))
        for param in parameters:
            if param in extern_values.keys():
                self.sensvalues[param] = list(
                    extern_values[param][:len(realnums)])
            else:
                raise ValueError(
                    'Parameter {} not in external file'
                    .format(param))
        self.sensvalues['REAL'] = realnums
        self.sensvalues['SENSNAME'] = self.sensname
        self.sensvalues['SENSCASE'] = 'p10_p90'
        self._add_seeds(realnums, seeds)

    def _add_seeds(self, realnums, seeds, seedstart=1000):
        """Add RMS_SEED as column.

        TO DO: Add option to read seeds from external file

        Args:
            realnums (list): list of realization numbers
                for the sensitivity case
            seeds (str): chose between 'default' 1000-1001-1002-...
                'None' (No seed added) or 'extern'
            seedstart (int): First seed value
        """

        if seeds != 'None':
            if seeds.lower() == 'default':
                seed_numbers = [nmr + seedstart - realnums[0]
                                for nmr in realnums]
                self.sensvalues['RMS_SEED'] = seed_numbers
            elif seeds.lower() == 'extern':
                print('TO DO: Read from external seeds')
            else:
                raise ValueError(
                    'Only "default", "extern" or None are valid choices'
                    'for seeds in general_input. Given value was {}'
                    .format(seeds))


# Support functions used with several classes


def _parameters_from_extern(filename):
    """ Read parameter values or background values
    from specified file. Format either Excel ('xlsx')
    or csv.

    Args:
        filename (str): path to file
    """
    if filename.endswith('.xlsx'):
        parameters = pd.read_excel(filename)
    elif filename.endswith('.csv'):
        parameters = pd.read_csv(filename)
    else:
        raise ValueError(
            'External file with parameter values should '
            'be on Excel or csv format '
            'and end with .xlsx or .csv')
    return parameters
