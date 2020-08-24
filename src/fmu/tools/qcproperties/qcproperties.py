"""The qcproperties module"""
from pathlib import Path

import pandas as pd
import yaml

from fmu.tools.qcforward._qcforward_data import _QCForwardData

from fmu.tools.qcproperties._combine_propstats import combine_property_statistics
from fmu.tools.qcproperties._propstat_parameter_data import PropStatParameterData
from fmu.tools.qcproperties._propstat import PropStat


class QCProperties:
    """
    The QCProperties class consists of a set of methods for extracting
    property statistics from 3D Grids, Raw and Blocked wells.

    The methods for statistics extraction can be run individually, or a
    yaml-configuration file can be used to enable an automatic run of the
    methods. See the method 'from_yaml'.

    When several methods of statistics extraction has been run within the instance,
    a merged dataframe is available through the 'dataframe' property.

    All methods can be run from either RMS python, or from files.

    XTGeo is being utilized to get a dataframe from the input parameter data.
    XTGeo data is reused in the instance to increase performance.


    Methods for extracting statistics from 3D Grids, Raw and Blocked wells:

        Args:
            data (dict): The input data as a Python dictionary (see description of
                valid argument keys in documentation)
            reuse (bool or list): If True, then grid and gridprops will be reused
                as default. Alternatively it can be a list for more
                fine grained control, e.g. ["grid", "gridprops", "wells"]
            project (obj or str): For usage inside RMS

        Returns:
            A PropStat() instance

    """

    def __init__(self):
        self._gdata = None  # QCForwardData instance, general data
        self._propstats = []  # list of PropStat() instances
        self._dataframe = pd.DataFrame()  # merged dataframe of all statsistics data

    # Properties:
    # ==================================================================================

    @property
    def dataframe(self):
        """A merged dataframe from all the PropStat() instances"""

        # auto update dataframe if out of sync with self._propstats
        if (self._propstats and self._dataframe.empty) or (
            len(self._propstats) != len(self._dataframe["ID"].unique())
        ):
            self._dataframe = combine_property_statistics(self)

        return self._dataframe

    @property
    def gdata(self):
        """Returns the genarel data attribute as string."""
        return self._gdata

    @gdata.setter
    def gdata(self, data):
        """Set the global data attribute."""
        self._gdata = data

    # Hidden methods:
    # ==================================================================================

    @staticmethod
    def _combine_parameter_data(data):
        """
        Initialize a PropStatParameterData instance that groups the parameter
        data from the different data sources into class attributes
        """

        return PropStatParameterData(
            properties=data["properties"],
            selectors=data.get("selectors", {}),
            additional_filters=data.get("additional_filters", None),
        )

    def _parse_data(self, data, reuse, wells_settings=None):
        """Prepare and parse data (load to xtgeo) """

        if isinstance(self.gdata, _QCForwardData):
            self.gdata.parse(data, reuse=reuse, wells_settings=wells_settings)
        else:
            self.gdata = _QCForwardData()
            self.gdata.parse(data, wells_settings=wells_settings)

    def _initiate_from_config(self, cfg, project=None, reuse=False):
        """ Run methods for statistics extraction based on entries in yaml-config"""

        with open(cfg, "r") as stream:
            data = yaml.safe_load(stream)

        if "grid" in data:
            for item in data["grid"]:
                self.get_grid_statistics(data=item, project=project, reuse=reuse)

        if "wells" in data:
            for item in data["wells"]:
                self.get_well_statistics(data=item, project=project, reuse=reuse)

        if "blockedwells" in data:
            for item in data["blockedwells"]:
                self.get_bwell_statistics(data=item, project=project, reuse=reuse)

    # QC methods:
    # ==================================================================================

    def get_grid_statistics(
        self, data: dict, project: object = None, reuse: bool = False
    ):
        """Extract property statistics from 3D Grid"""

        data = data.copy()

        if project:
            data["project"] = project

        # create _PropStatParameterData() instance
        pdata = self._combine_parameter_data(data)

        # Parse data to initialize a XTGeo GridProperties() instance
        if project:
            data["project"] = project
            data["gridprops"] = pdata.params
        else:
            data["gridprops"] = [[None, param] for param in pdata.params]

        self._parse_data(data, reuse)

        # compute statistics
        propstat = PropStat(
            parameter_data=pdata,
            xtgeo_object=self.gdata.gridprops,
            selector_combos=data.get("selector_combos", True),
            name=data.get("name", None),
            source=Path(data["grid"]).stem,
            csvfile=data.get("csvfile", None),
        )

        self._propstats.append(propstat)

        return propstat

    def get_well_statistics(
        self, data: dict, project: object = None, reuse: bool = False
    ):
        """Extract property statistics from wells """

        data = data.copy()

        if "wells" not in data.keys():
            raise ValueError("Key 'wells' not found in data")

        if project:
            data["project"] = project

        # create _PropStatParameterData() instance
        pdata = self._combine_parameter_data(data)

        # Parse data to initialize a XTGeo Wells() instance
        wsettings = {
            "lognames": pdata.params,
        }
        self._parse_data(data, reuse, wells_settings=wsettings)

        # compute statistics
        propstat = PropStat(
            parameter_data=pdata,
            xtgeo_object=self.gdata.wells,
            selector_combos=data.get("selector_combos", True),
            name=data.get("name", None),
            source="wells",
            csvfile=data.get("csvfile", None),
        )

        self._propstats.append(propstat)

        return propstat

    def get_bwell_statistics(
        self, data: dict, project: object = None, reuse: bool = False
    ):
        """Extract property statistics from blocked wells """

        data = data.copy()

        if "wells" not in data.keys():
            raise ValueError("Key 'wells' not found in data")

        if project:
            data["project"] = project

        # create _PropStatParameterData() instance
        pdata = self._combine_parameter_data(data)

        # Parse data to initialize a XTGeo BlockedWells() instance
        data["bwells"] = data.pop("wells")
        wsettings = {
            "lognames": pdata.params,
        }
        self._parse_data(data, reuse, wells_settings=wsettings)

        # compute statistics
        propstat = PropStat(
            parameter_data=pdata,
            xtgeo_object=self.gdata.bwells,
            selector_combos=data.get("selector_combos", True),
            name=data.get("name", None),
            source=(
                "blockedwells"
                if project is None
                else data["bwells"].get("bwname", "BW")
            ),
            csvfile=data.get("csvfile", None),
        )

        self._propstats.append(propstat)

        return propstat

    def from_yaml(self, cfg: str, project: object = None, reuse: bool = False):
        """ Use yaml-configuration file to run the statistics extractions methods."""
        self._initiate_from_config(cfg, project, reuse)

    def to_csv(self, csvfile: str):
        """ Write combined dataframe to csv """
        self.dataframe.to_csv(csvfile, index=False)
