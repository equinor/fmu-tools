# -*- coding: utf-8 -*-
"""Module for generating design matrices that can be run by DESIGN2PARAMS
and DESIGN_KW in FMU/ERT.
"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
import pandas as pd
from fmu.tools.sensitivities import design_distributions as design_dist


class DesignMatrix(object):
    """Class for design matrix in FMU. Can contain a onebyone design
    or a full montecarlo design.

    Attributes:
        designvalues (DataFrame): design matrix on standard fmu format
            contains columns 'REAL' (realization number), and if a onebyone
            design also columns 'SENSNAME' and 'SENSCASE'
        defaultvalues (OrderedDictionary): default values for design
    """

    def __init__(self):
        """
        Placeholders for:
        designvalues: dataframe with parameters that varies
        defaultvalues: dictionary of default/base case values
        """
        self.designvalues = pd.DataFrame(columns=['REAL'])
        self.defaultvalues = dict()

    def set_defaultvalues(self, defaults):
        """ Set default values to use for sensitivities

        Args:
            defaults (dict): (key, value) is (parameter_name, value)
        """
        self.defaultvalues = defaults

    def add_sensitivity(self, sensitivity):
        """Adding a sensitivity to the design"""
        prior_values = self.designvalues.copy()
        self.designvalues = prior_values.append(sensitivity.sensvalues)
        for key in self.designvalues.keys():
            if key in self.defaultvalues.keys():
                self.designvalues[key].fillna(
                    self.defaultvalues[key], inplace=True)
            elif key not in ['REAL', 'SENSNAME', 'SENSCASE', 'RMS_SEED']:
                print('No defaultvalues given for {}'.format(key))

    def generate(self, inputdata):
        """Generating design matrix from input dictionary
        Looping through sensitivities and adding to design

        Args:
            inputdata (OrderedDict): input parameters for design
        """
        seedtype = inputdata['seeds']
        if inputdata['designtype'] == 'onebyone':
            counter = 0
            for key in inputdata['sensitivities'].keys():
                sens = inputdata['sensitivities'][key]
                if 'numreal' in sens.keys():
                    numreal = sens['numreal']
                else:
                    numreal = inputdata['repeats']

                if sens['senstype'] == 'scalar':
                    sensitivity = SingleSensitivity(key)
                    for casekey in sens['cases'].keys():
                        case = sens['cases'][casekey]
                        temp_case = SingleSensitivityCase(casekey)
                        temp_case.generate(
                            range(counter, counter+numreal),
                            case, seedtype)
                        sensitivity.add_case(temp_case)
                        counter = counter + numreal
                elif sens['senstype'] == 'mc':
                    sensitivity = MonteCarloSensitivity(key)
                    sensitivity.generate(
                        range(counter, counter + numreal),
                        sens['parameters'], seedtype)
                    counter = counter + numreal
                self.add_sensitivity(sensitivity)

    def to_xlsx(self, filename,
                designsheet='DesignSheet01',
                defaultsheet='DefaultValues'):
        """Writing design matrix to excel on standard fmu format
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
        print('Have written to xlsxfile')


class SingleSensitivity(object):
    """Each design can contain one or several single sensitivities.
    Each single sensitivity can contain 1-2 single sensitivity cases.
    This class is used for real single sensitivities where all
    realizatons in a case have identical values except the seed value.

    For monte carlo sensitivities where parameter values are varying within
    one case, use the MonteCarloSensitivity class instead.

    Attributes:
        case1 (SingleSensitivityCase): first case, typically 'low case'
        case2 (SingleSensitivityCase): second case, typically 'high case'
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
        Adds a SingleSensitivityCase instance to a SingleSensitivity object

        Args:
            senscase (SingleSensitivityCase)
        """
        if self.case1 is not None:  # Case 1 has been read, this is case2
            if (
                    'REAL' in senscase.casevalues.keys() and
                    'SENSCASE' in senscase.casevalues.keys()):
                self.case2 = senscase
                senscase.casevalues['SENSNAME'] = self.sensname
                self.sensvalues = pd.concat([
                    self.sensvalues, senscase.casevalues])
        else:  # This is the first case
            if (
                    'REAL' in senscase.casevalues.keys()
                    and 'SENSCASE' in senscase.casevalues.keys()):
                self.case1 = senscase
                self.sensvalues = senscase.casevalues.copy()
                self.sensvalues['SENSNAME'] = self.sensname


class SingleSensitivityCase(object):
    """Each single sensitivity can contain one or
    two single sensitivity cases.

    For real single sensitivities the 1-2 cases are
    typically 'low' and 'high' cases for one or
    a set of  parameters, where all realisatons in
    the case have identical values except the seed value.

    One or two SingleSensitivityCase instances can be added to each
    SingleSensitivity object.

    TO DO: Add possibility to provide external list of seeds.

    TO DO: Handling of expections.

    Attributes:
        casename (str): name of the sensitivity case,
                        equals SENSCASE in design matrix
        casevalues (pandas Dataframe): contains parameter names and
            values for the case

    """

    def __init__(self, casename):
        self.casename = casename
        self.casevalues = None

    def add_seeds(self, realnums, seeds, seedstart=1000):
        """ When running sensitivities with repeating seeds
        the same list of seed numbers are used for all cases.
        Here RMS_SEED is generated and added as a column in  casevalues

        Args:
            realnums (list): list of realization numbers
                for the sensitivity case
            seeds (str): chose between 'default' 1000-1001-1002-...
                and 'None' (No seed added)
        """

        if seeds != 'None':
            if seeds == 'default':
                seed_numbers = [nmr + seedstart - realnums[0]
                                for nmr in realnums]
                self.casevalues['RMS_SEED'] = seed_numbers
            elif seeds == 'xtern':
                print('TO DO: Reed from xternal seeds')
            else:
                print('TO DO: Inform only "default" and "xtern" valid choices')

    def generate(self, realnums, parameters, seeds):
        """Generate real dataframe with case values for a real
            single sensitivity case where all parameters within the
            case are kept constant, except the seed value.
            Adding these to the case in DataFrame casevalues

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
        self.add_seeds(realnums, seeds)


class MonteCarloSensitivity(object):
    """
    A single sensitivity can be a monte carlo
    sensitivity where parameters for one or several parameters
    are drawn from a distribution. Such sensitivities can only contain
    one case, where the case is automatically named 'p10_p90'.

    Attributes:
        sensvalues (dataframe):  design values for the sensitivity

    """

    def __init__(self, sensname):
        """Args:
                sensname (str): Name of sensitivity.
                    Defines SENSNAME in design matrix
        """
        self.sensname = sensname
        self.sensvalues = None

    def add_seeds(self, realnums, seeds):
        """Add RMS_SEED as column.

        TO DO: Add option to read seeds from external file

        Args:
            seeds (str): 'None' (not adding seeds) or 'default' (adding
                seeds 1000-1001-1002..)
        """

        if seeds != 'None':
            if seeds == 'default':
                seed_numbers = [nmr + 1000 - realnums[0] for nmr in realnums]
                self.sensvalues['RMS_SEED'] = seed_numbers
            elif seeds == 'xtern':
                print('TO DO: Read from xternal seeds')
            else:
                print('TO DO: Only "None", "default" and "xtern"')

    def generate(self, realnums, parameters, seeds, correlations=None):
        """Generates parameter values for a monte carlo sensitivity
        by drawing from defined distributions

        TO DO: Implement monte carlo values with correlation matrix

        Args:
            realnums (list): list of intergers with realization numbers
            parameters (OrderedDict):
                dictionary of parameters and distributions
            seeds (str): default or None
            correlations: matrix with correlations. Not implemented yet
        """
        self.sensvalues = pd.DataFrame(
            columns=parameters.keys(), index=realnums)
        if not correlations:
            for key in parameters.keys():
                dist_name = parameters[key][0]
                dist_params = parameters[key][1]
                # print(realnums,key, dist_name, dist_params)
                distribution = design_dist.prepare_distribution(
                    dist_name, dist_params)
                mc_values = design_dist.generate_mcvalues(
                    distribution, len(realnums))
                if dist_name == 'logunif':  # not in scipy, uses unif
                    mc_values == 10**mc_values
                self.sensvalues[key] = mc_values
        else:
            print('TO DO: Implement with correlations')
        self.sensvalues['REAL'] = realnums
        self.sensvalues['SENSNAME'] = self.sensname
        self.sensvalues['SENSCASE'] = 'p10_p90'
        self.add_seeds(realnums, seeds)
