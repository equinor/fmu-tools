# -*- coding: utf-8 -*-
"""Testing fmu-tools."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import fmu.config as config
from fmu.tools.coviz import CovizModel, SpatialFileNameCollection, DataArray
import pandas as pd
import os
import json

fmux = config.etc.Interaction()
logger = fmux.basiclogger(__name__)

# always this statement
if not fmux.testsetup():
    raise SystemExit()


def get_reals_iters(scratchdir, realprefix = 'realization-', iterprefix = 'iter-'):

    reals = []
    iters = []

    #List realization folders at scratchdir
    for real in os.listdir(scratchdir):
        if real.startswith(realprefix):
            reals.append(int(real[len(realprefix):]))

    #Sort by number
    reals.sort()
    
    #List iteration folders in first realization folder
    for iteration in os.listdir(scratchdir + '/' + realprefix + str(reals[0])):
        if iteration.startswith(iterprefix):
            iters.append(int(iteration[len(iterprefix):]))

    #Sort by number
    iters.sort()

    #Add prefix back to iteration name
    for i, iteration in enumerate(iters):
        iters[i] = iterprefix+str(iteration)
    #iters.append("iter-0")
    return(reals, iters)

#Collect volume csv files to dataframe
def collect_volfiles(scratchdir, ensemble, reals):
    
    volfolder = 'share/results/volumes/'
    files = ['geogrid_vol_oil.csv', 'simgrid_vol_oil.csv']
    
    
    dfs = []
    for f in files:
        dfs_grid = []

        for real in reals:
            try:
                path = os.path.join(scratchdir, 'realization-' + str(real), ensemble, volfolder, f)
                df = pd.read_csv(path)
                df['REAL'] = real
                df['GRID'] = f[0:7]
                df['ENSEMBLE'] = ensemble
                dfs_grid.append(df)
            except(IOError):
                print('File %s does not exist' % path)
        df = pd.concat(dfs_grid)
        dfs.append(df)
        
  
    
    return pd.concat(dfs)


def test_very_basics():
    """Test basic behaviour"""

    coviz = CovizModel('/scratch/fmu/sago/3_r001_reek_seismatch')

    assert isinstance(coviz, CovizModel)

def test_model():
    scratchdir = '/scratch/fmu/sago/3_r001_reek_seismatch'
    
    #Some output not stored on scratch
    seismatchdir = '/project/fmu/tutorial/reek/resmod/ff/2018a/r001/share/coviz/d3'
    
    #hack
    reals, iters = get_reals_iters(scratchdir)
    
    firstReal = os.path.join(scratchdir, 'realization-' + str(reals[0]), iters[0])
    
    coviz = CovizModel(scratchdir)
    spatial_collection = SpatialFileNameCollection(firstReal).as_dict
    

    scol = spatial_collection['values'][0]
    assert scol['base0'] == 'ds_extracted_horizons'
    assert scol['base1'] == ['topupperreek', 'topmidreek', 'toplowerreek', 'baselowerreek']
    assert scol['base2'] == None
    
    scol = spatial_collection['values'][-1]
    assert scol['base0'] == 'seismatch_rms'
    assert scol['base1'] == ['topmidreek']
    assert scol['base2'] == ['20000101', '20010601_20000101', '20030101_20000101', '20030101_20010601']
    
    coviz.set_spatial_collection(spatial_collection)
    for ensemble in iters:
        data = []
        vol_df = collect_volfiles(scratchdir, ensemble, reals)
        sim_df = pd.read_json(os.path.join(seismatchdir,ensemble+'.json'), orient='records')
    
        volume_data = DataArray(vol_df, 'volume_data', keys=[{'REAL':'REAL', 'GRID':'GRID'}]).as_dict
        similarity = DataArray(sim_df, 'similarity', keys = [{'REAL':'REAL'}]).as_dict
    
        data.append(volume_data)
        data.append(similarity)
    
        #df2 = collect_avg_properties(scratchdir, reals, iters, 'geogrid_avg_values.csv')
        #avg_grid_bw = df2.to_dict(orient='records')
        
        coviz.add_ensemble(ensemble, reals, data)
        
    data = json.loads(coviz.__repr__())

    assert data['id'] == 6181126438477286346
    ensdata = data['ensembles'][0]['data'][0]
    assert ensdata['name'] == 'volume_data'
    assert ensdata['values'][0]['BULK_OIL'] == 324035109.87
    assert ensdata['correlations'][0][0] == 1.0
    assert ensdata['corr_columns'][0] == 'REGION'

    scol = data['spatial_collection']['values']
    assert scol[0]['base0'] == 'ds_extracted_horizons'
    assert scol[0]['base1'] == ['topupperreek', 'topmidreek', 'toplowerreek', 'baselowerreek']
    assert scol[0]['base2'] == None
    assert scol[-1]['base0'] == 'seismatch_rms'
    assert scol[-1]['base1'] == ['topmidreek']
    assert scol[-1]['base2'] == ['20000101', '20010601_20000101', '20030101_20000101', '20030101_20010601']
