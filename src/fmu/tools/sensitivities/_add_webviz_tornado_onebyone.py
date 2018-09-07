# -*- coding: utf-8 -*-
""" Module for generating a set of TornadoPlots
for webviz on webviz Pages. """

from __future__ import division, print_function, absolute_import
import os.path
import copy
import sys
from collections import OrderedDict
import pandas as pd
sys.path.insert(0, "/project/res/webviz_multiuse") # noqa
import yaml
from webportal import SubMenu, Page
import webportal.visualisations as webvis
from fmu import ensemble
from fmu.tools.sensitivities import summarize_design
from fmu.tools.sensitivities import calc_tornadoinput, find_combinations


def yconfig(inputfile):
    """Read from YAML file."""
    with open(inputfile, 'r') as stream:
        config = yaml.load(stream)
    print('Input config YAML file <{}> is read...'.format(inputfile))
    return config


def yconfig_set_defaults(config):
    """Override the YAML config with defaults where missing input."""
    newconfig = copy.deepcopy(config)

    # some defaults if data is missing
    if 'webvizname' not in newconfig['tornadooptions']:
        newconfig['tornadooptions']['webvizname'] = 'webviz_tornado'

    if 'reference' not in newconfig['tornadooptions']:
        newconfig['tornadooptions']['reference'] = '0'

    if 'scale' not in newconfig['tornadooptions']:
        newconfig['tornadooptions']['scale'] = 'absolute'

    if 'cutbyseed' not in newconfig['tornadooptions']:
        newconfig['tornadooptions']['scale'] = 'No'

    if 'designsheet' not in newconfig['design']:
        newconfig['design']['designsheet'] = 'DesignSheet01'

    if 'gatherresults' not in newconfig['results']:
        newconfig['results']['gatherresults'] = False

    if 'printresultfile' not in newconfig['results']:
        newconfig['results']['printresult'] = False

    if 'renamecolumns' not in newconfig['results']:
        newconfig['results']['renamecolumns'] = False

    if 'menuprefix' not in newconfig['calculations']:
        newconfig['calculations']['menuprefix'] = ''

    return newconfig


def make_xlabel(ref_value, scale='percentage', reference='seed'):
    """ Makes xlabel for tornadoplot from input """
    label = scale.capitalize()+' change compared to ref value '
    label += "{:.2e}".format(ref_value)+'.   '
    if reference.isdigit():
        label += '   Reference is realisation ' + str(reference)
    else:
        label += '   Reference is sensititivity ' + reference
    return label


def gatherresults(config):
    """ Gathers .csv files from different realisations into one"""
    ensemblepaths = config['results']['ensemblepaths']
    print(ensemblepaths)
    print(type(ensemblepaths))
    singleresultfile = config['results']['singleresultfile']
    print(singleresultfile)

    doe_ensemble = ensemble.ScratchEnsemble('doe_ensemble', ensemblepaths)
    results = doe_ensemble.from_csv(singleresultfile)

    if config['results']['writeresultfile']:
        outdir = config['results']['exportdir']
        outfilename = config['results']['exportfilename']
        if not os.path.exists(outdir):
            os.mkdir(outdir)
        fullname = os.path.join(outdir, outfilename)
        results.to_csv(fullname, index=False)

    return results


def add_webviz_tornadoplots(web, configfile):
    """
     Generating a set of TornadoPlots for webviz on webviz Pages

    :returns: webviz SubMenu with set of tornado plot on webviz Pages
    :param web: webportal where submenu should be added
    :param configfile: yaml configuration file for tornado calculations
    """

    yamlfile = configfile

    # input
    inputfile = yconfig(yamlfile)
    config = yconfig_set_defaults(inputfile)

    # assign parameters from config
    designpath = config['design']['designpath']
    designname = config['design']['designname']
    designsheet = config['design']['designsheet']

    response = config['calculations']['responses']

    selections = OrderedDict(config['calculations']['selections'])
    selectors = selections.keys()

    reference = str(config['tornadooptions']['reference'])
    scale = config['tornadooptions']['scale']
    cutbyseed = config['tornadooptions']['cutbyseed']
    menuprefix = config['calculations']['menuprefix']

    # Option: results from single realisation csv files needs gathering first
    if config['results']['gatherresults']:
        results = gatherresults(config)

    # Default: concatenated result file already exists as csv
    if not config['results']['gatherresults']:
        resultpath = config['results']['resultpath']
        resultname = config['results']['resultname']
        resultfile = os.path.join(resultpath, resultname)
        results = pd.read_csv(resultfile)

    # Option: renaming of columns in resultfile, e.g. from CSV_EXPORT1
    if config['results']['renamecolumns']:
        results.rename(columns=config['results']['renaming'], inplace=True)

    # Read design matrix and find realisation numbers for each sensitivity
    designname = os.path.join(designpath, designname)
    designtable = summarize_design(designname, designsheet)
    print('Summary of design matrix:')
    with pd.option_context('expand_frame_repr', False):
        print(designtable)

    # Find all combinations of selections to generate plots for
    comb = find_combinations(selections)

    # Grouping calculation of tornado plots per response.
    # One list of plots under each response
    for res in response:
        smn = SubMenu(menuprefix+' '+res)
        for cmb in comb:
            pagetitle = res
            for ksel in range(len(selections)):
                pagetitle += ' ,  ' + str(selections.keys()[ksel])
                pagetitle += '  =  '+str(cmb[ksel]).strip("[]")
            pge = Page(pagetitle)
            (tornadotable, ref_value) = calc_tornadoinput(
                designtable,
                results, res,
                selectors, cmb,
                reference, scale, cutbyseed)
            print('For response and selections: ')
            print(pagetitle)
            print('reference average: ', ref_value)
            print('Calculation settings: ', scale, ', Cut by seed: ',
                  cutbyseed, ',  Reference: ', reference)
            with pd.option_context('expand_frame_repr', False):
                print(tornadotable)
            print('\n')
            xlabel = make_xlabel(ref_value, scale, reference)
            tornado_plot = webvis.TornadoPlot(tornadotable, xlabel, pagetitle)
            pge.add_content(tornado_plot)
            smn.add_page(pge)

        web.add(smn)
