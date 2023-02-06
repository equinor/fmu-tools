from typing import Optional

import pandas as pd

from fmu.tools._common import _QCCommon
from fmu.tools.qcdata import QCData
from fmu.tools.qcproperties._config_parser import ConfigParser
from fmu.tools.qcproperties._utils import filter_df

QCC = _QCCommon()


class GridProps2df:
    """
    Class responsible for generating a property dataframe from grid prperties, and
    providing control arguments for the statisics extraction using PropertyAggregation()
    """

    def __init__(self, project: Optional[object], data: dict, xtgdata: QCData):
        """Initiate instance"""
        QCC.verbosity = data.get("verbosity", 0)

        self._xtgdata = xtgdata  # A QCData instance used for dataloading to XTGeo
        self._property_type: Optional[str] = None
        self._dataframe = pd.DataFrame()  # dataframe with property data

        self._data_input_preparations(project, data)

        # Create dataframe from grid properties
        self._create_df_from_grid_props()

    # ==================================================================================
    # Class properties
    # ==================================================================================

    @property
    def dataframe(self) -> pd.DataFrame:
        """Dataframe with property statistics."""
        return self._dataframe

    @property
    def property_type(self) -> Optional[str]:
        """Property type (continous/discrete)"""
        return self._property_type

    @property
    def aggregation_controls(self) -> dict:
        """Attribute to use for statistics aggregation"""
        return self._aggregation_controls

    # ==================================================================================
    # Hidden class methods
    # ==================================================================================

    def _data_input_preparations(self, project: Optional[object], data: dict):
        """
        Prepare the input parameter data for usage within QCProperties().
        Parameters are loaded to XTGeo and property types are checked.
        """
        data = data.copy()
        controllers = ConfigParser(data)

        self._aggregation_controls = controllers.aggregation_controls
        self._controls = controllers.prop2df_controls

        xtg_input = controllers.data_loading_input

        # set gridprops argument format for dataloading with QCData()
        if not xtg_input["pfiles"]:
            xtg_input["gridprops"] = self._controls["unique_parameters"]
        else:
            xtg_input["gridprops"] = [
                [param, xtg_input["pfiles"][param]]
                if param in xtg_input["pfiles"]
                else param
                for param in self._controls["unique_parameters"]
            ]

        # Load data to XTGeo
        self._xtgdata.parse(
            project=project,
            data=xtg_input,
            reuse=True,
        )
        # Load data to XTGeo
        self._check_and_set_property_type()

    def _create_df_from_grid_props(self):
        """
        Extract a combined property dataframe for the input properties.
        Values for discrete logs will be replaced by their codename.
        """
        QCC.print_info("Creating property dataframe from grid properties")

        self._dataframe = self._xtgdata.gridprops.get_dataframe().copy().dropna()

        # replace codes values in dataframe with code names
        self._codes_to_codenames()

        # Filter property dataframe
        if self._controls["filters"]:
            self._dataframe = filter_df(self._dataframe, self._controls["filters"])

        # rename columns in dataframe
        self.dataframe.rename(columns=self._controls["name_mapping"], inplace=True)

    def _check_and_set_property_type(self):
        """
        Use XTGeo to check that selectors are discrete, and also
        check if input properties are continous or discrete.
        Raise errors if not desired format.
        """
        # check that all selectors are discrete
        selectors = self._controls["selectors_input_names"]
        xtgprops = [
            self._xtgdata.gridprops.get_prop_by_name(prop) for prop in selectors
        ]
        if not all(prop.isdiscrete for prop in xtgprops):
            raise ValueError("Only discrete properties can be used as selectors")

        # check that all properties defined are of the same type
        properties = self._controls["properties_input_names"]
        xtgprops = [
            self._xtgdata.gridprops.get_prop_by_name(prop) for prop in properties
        ]
        if any(prop.isdiscrete for prop in xtgprops) and not all(
            prop.isdiscrete for prop in xtgprops
        ):
            raise TypeError(
                "Properties of different types (continuous/discrete) "
                "defined in the input."
            )

        # Set attribute used to control aggregation method
        discrete = xtgprops[0].isdiscrete
        QCC.print_debug(
            f"{'Discrete' if discrete else 'Continous'} properties in input"
        )
        self._property_type = "DISC" if discrete else "CONT"

    def _codes_to_codenames(self):
        """Replace codes in dicrete parameters with codenames"""
        for param in self._controls["unique_parameters"]:
            xtg_prop = self._xtgdata.gridprops.get_prop_by_name(param)

            if xtg_prop.isdiscrete:
                codes = xtg_prop.codes.copy()
                usercodes = self._controls["usercodes"].copy()

                # Update code names if user input
                if usercodes and param in usercodes:
                    codes.update(usercodes[param])

                # replace codes values in dataframe with code names
                self._dataframe[param] = self._dataframe[param].map(codes.get)
