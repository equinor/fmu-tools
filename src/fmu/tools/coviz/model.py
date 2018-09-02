# -*- coding: utf-8 -*-
"""This module is used by Coviz"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
import os
import json
from uuid import uuid4
import glob
import pandas as pd
from fmu.config import etc

xfmu = etc.Interaction()
logger = xfmu.functionlogger(__name__)


class CovizModel(object):
    """Class to extract data from a ScratchEnsemble
    for use in Coviz"""

    def __init__(self, ensemble_set_path):
        self.path = ensemble_set_path
        self.name = '--'.join(ensemble_set_path.split('/')[-2:])
        self.id = hash(self.name)
        self.ensembles = []
        self.spatial_collection = []
        logger.debug('Ran __init__')

    def __repr__(self):
        config = {
            "name": self.name,
            "path": self.path,
            "id": self.id,
            "ensembles": self.ensembles,
            "spatial_collection": self.spatial_collection
        }
        json_string = json.dumps(config)
        json_string = json_string.replace(str('NaN'), 'null')
        return json_string

    def set_spatial_collection(self, collection):
        """Adds a collection of file names with
        spatial data to the model

        Args:
            collection: A spatial collection
        """
        self.spatial_collection = collection

    def add_ensemble(self, name, realizations, data):
        """Adds an ensemble with data to the model

        Args:
            name: Name of the ensemble
            realizations: Realizations array
            data: Data array
        """
        self.ensembles.append({
            "name": name,
            "id": str(uuid4()),
            "realizations": realizations,
            "data": data
        })

    def to_json(self, file_name=None):
        """Stores the model as a json file for
        use in Coviz

        Args:
            file_name: Optional filename
        """
        if file_name is None:
            file_name = self.path.split('/')[-1]

        config = {
            "name": self.name,
            "path": self.path,
            "id": self.id,
            "ensembles": self.ensembles,
            "spatial_collection": self.spatial_collection
        }
        json_string = json.dumps(config)
        json_string = json_string.replace(str('NaN'), 'null')
        to_json = json.loads(json_string)

        with open(file_name, 'w') as coviz_file:
            json.dump(to_json, coviz_file)


class SpatialFileNameCollection(object):
    """Class to create a collection for all file names
    containing spatial data from a ScratchRealization.

    Each file is split up into 'file bases',

    The class expects these files bases to be:
    name, attribute and date(optional) separated by a
    delimiter.
    E.g. the file 'EclipseGrid--SWAT--2010' will be split
    into ['EclipseGrid', 'SWAT', 2010].

    Each set of file bases are then aggregated if they
    share bases.

    E.g:

    {EclipseGrid: ['SWAT', 'SOIL'], [2010, 2011, 2012]}

    This class is not perfected.

    """

    def __init__(self, base_path):

        self.base_path = base_path
        self.delimiter = '--'
        self.spatial_files = []
        self.max_bases = 2
        self.file_types = [
            {
                'filesuffix': 'gri',
                'path': 'share/results/maps'
            },
            {
                'filesuffix': 'roff',
                'path': 'share/results/grids'
            },
            {
                'filesuffix': 'pol',
                'path': 'share/results/pol'
            }
        ]
        self.name = 'spatialFileNameCollection'
        self.type = 'spatialFileNameCollection'
        self.keys = ['base0', 'base1', 'base2']
        self.spatial_collection = self.get_spatial_collection()
        self.hash = hash(str(self.spatial_collection))

    def get_spatial_file_name(self, file_name, suffix):
        """Splits a single file into file bases
        Currently the first two bases are switched
        for surface and polygon data. This is because
        it makes more sense to organize the data by
        attribute(e.g poro) instead of name(e.g. TopReek)

        Args:
            file_name: Name of the base path of the file
            suffix: File suffix
        """
        meta = {}
        basename = os.path.basename(file_name)
        tmp = basename.split('.')[0]
        base = tmp.split(self.delimiter)
        count = 0
        for index in range(0, self.max_bases+1):
            count += 1
            try:
                meta['base' + str(index)] = base[index]
            except IndexError:
                meta['base' + str(index)] = None
        meta['basecount'] = count
        meta['filetype'] = suffix

        if suffix == 'gri' or suffix == 'pol':
            tmp = meta['base0']
            meta['base0'] = meta['base1']
            meta['base1'] = tmp
        return meta

    def get_all_spatial_file_names(self):
        """Gets all file names in a folder

        Returns:
            Dataframe of file names
        """

        for filetype in self.file_types:
            files = glob.glob(os.path.join(self.base_path, os.path.join(
                filetype['path'], '*.' + filetype['filesuffix'])))

            files.sort(key=os.path.getmtime)
            for file_name in files:
                self.spatial_files.append(
                    self.get_spatial_file_name(file_name, filetype['filesuffix']))

            return pd.DataFrame(self.spatial_files)

    def get_spatial_collection(self):
        """Aggregates all files"""
        logger.info('Getting spatial collection')

        self.all_file_names = self.get_all_spatial_file_names()

        spatial_collection = []

        # Generalize this
        if not 'filetype' in self.all_file_names.columns:
            return []
            #raise KeyError('Not spatial files found.')

        for filetype in self.all_file_names['filetype'].unique():

            df_filter = self.all_file_names.loc[self.all_file_names['filetype'] == filetype]
            df_hasbase2 = df_filter[df_filter['base2'].notnull()]
            df_hasnotbase2 = df_filter[df_filter['base2'].isnull()]

            for key in df_hasnotbase2['base0'].unique():
                df2 = df_hasnotbase2.loc[df_hasnotbase2['base0'] == key]
                base1 = df2['base1'].unique().tolist()

                base1 = [x for x in base1 if x != None]

                if base1 == None:
                    continue
                basecount = df2['basecount'].unique().tolist()
                if len(basecount) != 1:
                    continue
                f_type = df2['filetype'].unique().tolist()

                if len(f_type) != 1:
                    continue

                spatial_collection.append(
                    {'base0': key, 'base1': base1, 'base2': None, 'basecount': basecount[0], 'filetype': f_type[0]})

            for key in df_hasbase2['base0'].unique():
                df2 = df_hasbase2.loc[df_hasbase2['base0'] == key]
                base1 = df2['base1'].unique().tolist()
                base2 = df2['base2'].unique().tolist()
                basecount = df2['basecount'].unique().tolist()
                if len(basecount) != 1:
                    continue
                filetype = df2['filetype'].unique().tolist()

                if len(filetype) != 1:
                    continue
                spatial_collection.append(
                    {'base0': key, 'base1': base1, 'base2': base2, 'basecount': basecount[0], 'filetype': f_type[0]})
        return spatial_collection

    @property
    def as_dict(self):
        """Return collection as dictionary"""
        return (
            {
                "name": self.name,
                "type": self.type,
                "values": self.spatial_collection,
                "hash": self.hash,
                "keys": self.keys
            }
        )


class DataArray(object):
    """A class containing a summable data frame,
    the pandas correlation of that data frame and
    keys in the data frame the data can be summed over

    TODO: Add groupby column
    """

    def __init__(self, data, name, keys=[{'REAL': 'REAL'}]):
        self.name = name
        self.type = 'dataArray'
        self.data = data.to_dict(orient='records')
        self.hash = hash(data.values.tobytes())
        self.keys = keys
        self.corr_data = data.corr()
        self.corr_values = self.corr_data.values.tolist()
        self.corr_columns = self.corr_data.columns.tolist()

    @property
    def as_dict(self):
        """Return as dictionary"""
        return (
            {
                "name": self.name,
                "type": self.type,
                "values": self.data,
                "hash": self.hash,
                "correlations": self.corr_values,
                "corr_columns": self.corr_columns,
                "keys": self.keys
            }
        )


class StatisticsArray(object):
    """A class containing a summed data frame
    and a column key

    TODO: Add groupby column
    """

    def __init__(self, data, name, keys=[{'REAL': 'REAL'}]):
        self.name = name
        self.type = 'statisticsArray'
        self.data = data.to_dict(orient='records')
        self.keys = keys
        self.hash = hash(data.values.tobytes())
        self.keys = keys

    @property
    def as_dict(self):
        """Return as dictionary"""
        return (
            {
                "name": self.name,
                "type": self.type,
                "values": self.data,
                "hash": self.hash,
                "keys": self.keys
            }
        )
