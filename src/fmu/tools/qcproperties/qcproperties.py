"""The qcproperties module"""

import pandas as pd
import yaml

from fmu.tools._common import _QCCommon
from fmu.tools.qcdata import QCData

from fmu.tools.qcproperties._combine_propstats import combine_property_statistics
from fmu.tools.qcproperties._propstat_parameter_data import PropStatParameterData
from fmu.tools.qcproperties._propstat import PropStat

QCC = _QCCommon()


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

        self._propstats = []  # list of PropStat() instances
        self._dataframe = pd.DataFrame()  # merged dataframe with continous stats
        self._dataframe_disc = pd.DataFrame()  # merged dataframe with discrete stats
        self._xtgdata = QCData()  # QCData instance, general XTGeo data

    # Properties:
    # ==================================================================================

    @property
    def dataframe(self):
        """A merged dataframe from all the PropStat() instances"""
        self._dataframe = self._create_dataframe(self._dataframe)
        return self._dataframe

    @property
    def dataframe_disc(self):
        """A merged dataframe from all the PropStat() instances"""
        self._dataframe_disc = self._create_dataframe(
            self._dataframe_disc, discrete=True
        )
        return self._dataframe_disc

    @property
    def xtgdata(self):
        """The QCData instance"""
        return self._xtgdata

    # Hidden methods:
    # ==================================================================================

    def _input_preparations(self, project, data, reuse, dtype, qcdata=None):
        """
        Prepare the input parameter data for use with a PropStat() instance.
        Parameters are loaded to XTGeo and can be reused in the instance.
        """

        data = data.copy()
        data["dtype"] = dtype
        data["project"] = project
        if dtype == "bwells":
            data["bwells"] = data.pop("wells")

        pdata = PropStatParameterData(
            properties=data["properties"],
            selectors=data.get("selectors", {}),
            filters=data.get("filters", None),
            verbosity=data.get("verbosity", 0),
        )

        if dtype == "grid":
            pfiles = {}
            for elem in ["properties", "selectors", "filters"]:
                if elem in data and isinstance(data[elem], dict):
                    for values in data[elem].values():
                        if "pfile" in values:
                            pfiles[values["name"]] = values["pfile"]

            data["gridprops"] = [
                [param, pfiles[param]] if param in pfiles else ["unknown", param]
                for param in pdata.params
            ]

        if qcdata is not None:
            self._xtgdata = qcdata

        self._xtgdata.parse(
            project=data["project"],
            data=data,
            reuse=reuse,
            wells_settings=None
            if dtype == "grid"
            else {
                "lognames": pdata.params,
            },
        )

        return pdata, data

    def _dataload_and_calculation(self, project, data, reuse, dtype, qcdata=None):
        """ Load data to XTGeo and xtract statistics. Can be  """
        # create PropStatParameterData() instance and load parameters to xtgeo
        pdata, data = self._input_preparations(project, data, reuse, dtype, qcdata)

        QCC.print_info("Extracting property statistics...")
        # compute statistics
        propstat = PropStat(parameter_data=pdata, xtgeo_data=self._xtgdata, data=data)

        self._propstats.append(propstat)
        return propstat

    def _extract_statistics(self, project, data, reuse, dtype, qcdata):
        """
        Single statistics extraction, or multiple if multiple filters are defined.
        All PropStat() instances will be appended to the self._propstats list and
        are used to create a merged dataframe for the instance.

        Returns: A single PropStat() instance or a list of PropStat() intances if
                 multiple filters are used.
        """
        QCC.verbosity = data.get("verbosity", 0)

        if "multiple_filters" in data:
            propstats = []
            for name, filters in data["multiple_filters"].items():
                QCC.print_info(
                    f"Starting run with name '{name}', " f"using filters {filters}"
                )
                usedata = data.copy()
                usedata["filters"] = filters
                usedata["name"] = name
                pstat = self._dataload_and_calculation(
                    project, data=usedata, reuse=True, dtype=dtype, qcdata=qcdata
                )
                propstats.append(pstat)
            return propstats
        else:
            return self._dataload_and_calculation(project, data, reuse, dtype, qcdata)

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

    def _create_dataframe(self, dframe, discrete=False):
        """
        Combine dataframe from all PropStat() instances. Update dataframe if
        out of sync with self._propstats
        """
        if (self._propstats and dframe.empty) or (
            len(self._propstats) != len(dframe["ID"].unique())
        ):
            dframe = combine_property_statistics(
                self._propstats, discrete=discrete, verbosity=QCC.verbosity
            )
        return dframe

    # QC methods:
    # ==================================================================================

    def get_grid_statistics(
        self,
        data: dict,
        project: object = None,
        reuse: bool = False,
        qcdata: QCData = None,
    ) -> PropStat:
        """Extract property statistics from 3D Grid"""
        return self._extract_statistics(
            project, data, reuse, dtype="grid", qcdata=qcdata
        )

    def get_well_statistics(
        self,
        data: dict,
        project: object = None,
        reuse: bool = False,
        qcdata: QCData = None,
    ) -> PropStat:
        """Extract property statistics from wells """
        return self._extract_statistics(
            project, data, reuse, dtype="wells", qcdata=qcdata
        )

    def get_bwell_statistics(
        self,
        data: dict,
        project: object = None,
        reuse: bool = False,
        qcdata: QCData = None,
    ) -> PropStat:
        """Extract property statistics from blocked wells """
        return self._extract_statistics(
            project, data, reuse, dtype="bwells", qcdata=qcdata
        )

    def from_yaml(self, cfg: str, project: object = None, reuse: bool = False):
        """ Use yaml-configuration file to run the statistics extractions methods."""
        self._initiate_from_config(cfg, project, reuse)

    def to_csv(self, csvfile: str, disc: bool = False):
        """ Write combined dataframe to csv """
        dframe = self.dataframe if not disc else self.dataframe_disc
        dframe.to_csv(csvfile, index=False)

        QCC.print_info(f"Dataframe with {'discrete' if disc else 'continous'} ")
        QCC.print_info(f"property statistics written to {csvfile}")
