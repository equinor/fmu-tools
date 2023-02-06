from typing import Any, List, Optional

import pandas as pd

from fmu.tools._common import _QCCommon
from fmu.tools.qcdata import QCData
from fmu.tools.qcproperties._config_parser import ConfigParser
from fmu.tools.qcproperties._utils import filter_df

QCC = _QCCommon()


class WellLogs2df:
    """
    Class responsible for generating a property dataframe from well logs, and
    providing control arguments for the statisics extraction using PropertyAggregation()
    """

    def __init__(
        self,
        project: Optional[object],
        data: dict,
        xtgdata: QCData,
        blockedwells: bool = False,
    ):
        """Initiate instance"""
        QCC.verbosity = data.get("verbosity", 0)

        self._xtgdata = xtgdata  # A QCData instance used for dataloading to XTGeo
        self._wells: List[Any] = []
        self._property_type: Optional[str] = None
        self._dataframe = pd.DataFrame()  # dataframe with property log data

        self._data_input_preparations(project, data, blockedwells)

        # Get dataframe from the XTGeo objects
        self._create_df_from_wells()

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

    def _data_input_preparations(
        self, project: Optional[object], data: dict, blockedwells: bool
    ):
        """
        Prepare the input parameter data for usage within QCProperties().
        Parameters are loaded to XTGeo and property types are checked.
        """
        data = data.copy()

        if blockedwells:
            data["bwells"] = data.pop("wells")

        controllers = ConfigParser(data)

        self._aggregation_controls = controllers.aggregation_controls
        self._controls = controllers.prop2df_controls

        # Load data to XTGeo
        self._xtgdata.parse(
            project=project,
            data=controllers.data_loading_input,
            reuse=True,
            wells_settings={"lognames": self._controls["unique_parameters"]},
        )

        self._set_wells(blockedwells)

        # Check which property type is input
        self._check_logs_and_set_property_type()

    def _set_wells(self, blockedwells: bool):
        """Set wells attribute"""
        self._wells = (
            self._xtgdata.wells.wells
            if not blockedwells
            else self._xtgdata.bwells.wells
        )
        self._validate_wells()

    def _validate_wells(self):
        """Remove wells where selector logs are missing"""
        selectors = self._controls["selectors_input_names"]
        removed_wells = []
        for xtg_well in self._wells:
            # skip well if selector logs are missing
            if not all(log in xtg_well.lognames for log in selectors):
                QCC.print_info(
                    f"Skipping {xtg_well.name} some selector logs are missing"
                )
                removed_wells.append(xtg_well)
                continue
        self._wells = [
            xtg_well for xtg_well in self._wells if xtg_well not in removed_wells
        ]

    def _check_logs_and_set_property_type(self):
        """
        Use XTGeo to check that selectors are discrete, and also
        check if input properties are continous or discrete.
        Raise errors if not desired format.
        """
        # check that all selectors are discrete
        selectors = self._controls["selectors_input_names"]
        if not all(self._wells[0].isdiscrete(log) for log in selectors):
            raise ValueError("Only discrete logs can be used as selectors")

        # check that all properties defined are of the same type
        properties = self._controls["properties_input_names"]
        if any(self._wells[0].isdiscrete(log) for log in properties) and not all(
            self._wells[0].isdiscrete(log) for log in properties
        ):
            raise TypeError(
                "Properties of different types (continuous/discrete) "
                "defined in the input."
            )

        # Set attribute used to control aggregation method
        discrete = self._wells[0].isdiscrete(properties[0])
        QCC.print_debug(
            f"{'Discrete' if discrete else 'Continous'} properties in input"
        )
        self._property_type = "DISC" if discrete else "CONT"

    def _codes_to_codenames(self):
        """Replace codes in dicrete parameters with codenames"""
        for param in self._controls["unique_parameters"]:
            if self._wells[0].isdiscrete(param):
                codes = self._wells[0].get_logrecord(param).copy()
                usercodes = self._controls["usercodes"].copy()

                # Update code names if user input
                if usercodes and param in usercodes:
                    codes.update(usercodes[param])

                # replace codes values in dataframe with code names
                self._dataframe[param] = self._dataframe[param].map(codes.get)

    def _create_df_from_wells(self):
        """
        Create a combined property dataframe for the input wells.
        Values for discrete logs will be replaced by their codename.
        """
        QCC.print_info("Creating property dataframe from well logs")
        # Loop through XTGeo wells and combine into one dataframe
        dfs = []
        for xtg_well in self._wells:
            # extract dataframe for well
            df_well = xtg_well.dataframe.copy()
            df_well["WELL"] = xtg_well.name
            dfs.append(df_well)

        dframe = pd.concat(dfs)

        # To avoid bias in statistics, drop duplicates to remove
        # cells penetrated by multiple wells.
        dframe = dframe.drop_duplicates(
            subset=[x for x in dframe.columns if x != "WELL"]
        )
        self._dataframe = dframe[self._controls["unique_parameters"]].copy()

        # replace codes values in dataframe with code names
        self._codes_to_codenames()

        # Filter property dataframe
        if self._controls["filters"]:
            self._dataframe = filter_df(self._dataframe, self._controls["filters"])

        # rename columns in dataframe
        self.dataframe.rename(columns=self._controls["name_mapping"], inplace=True)
