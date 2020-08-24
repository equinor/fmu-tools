"""Module containing ....  """

from typing import Union

import pandas as pd
import xtgeo

from fmu.tools.qcproperties._propstat_parameter_data import PropStatParameterData
from fmu.tools.qcproperties._create_property_df import create_property_dataframe
from fmu.tools.qcproperties._create_propstat_df import compute_statistics_df
from fmu.tools.qcproperties._utils import filter_df


class PropStat:
    """
    Class for extracting property statistics from Grids, Raw and Blocked wells.

    Statistics for multiple properties can be calculated simultaneosly, and
    selectors can be used to extract statistics per value in discrete
    properties/logs. Filters can be used to remove unwanted data from the datasets.

    Input parameter data (properties, selectors, filters etc.) is required as an
    instance of _PropStatParameterData().

    XTGeo is being utilized to get a dataframe from the input parameter data.
    The input must be either an instance of xtgeo.GridProperties, xtgeo.Wells
    or xtgeo.BlockedWells.

    Args:
            xtgeo_object (obj): An instance of XTGeo GridProperties(), XTGeo Wells()
                    or a XTGeo BlockedWells().
            parameter_data (obj): An instance of PropStatParameterData() containing
                    parameters e.g. properties, selectors and filters.
            selector_combos (bool): Calculate statistics for every combination of
                    selectors. Depending on number of selectors and size of grid,
                    this process may be time consuming. Default is True.
            source (str): Source string for the propstat instance
            name (str): ID string for the propstat instance
            csvfile (str): Path to output csvfile. A csv-file will only be written,
                    if argument is provided.
            autocompute (bool): Auto calculate statistics upon initialization.
                    Default is True.
    """

    CALCULATIONS = ["Avg", "Stddev", "Min", "Max", "P10", "P90", "Avg_weighted"]

    def __init__(
        self,
        xtgeo_object: Union[xtgeo.GridProperties, xtgeo.Wells, xtgeo.BlockedWells],
        parameter_data: PropStatParameterData,
        selector_combos: bool = True,
        name: str = None,
        source: str = None,
        csvfile: str = None,
        autocompute: bool = True,
    ):

        """Initiate instance"""
        if isinstance(parameter_data, PropStatParameterData):
            self.pdata = parameter_data
        else:
            raise TypeError(
                "Argument 'parameter_data', needs to be an "
                " PropStatParameterData instance"
            )

        self._source = source
        self._name = name
        self._csvfile = csvfile
        self._selector_combos = selector_combos
        self._wells = []
        self._gridprops = None
        self._codes = {}

        self._prop_df_full = pd.DataFrame()  # dataframe containing all parameter values
        self._prop_df = pd.DataFrame()  # filtered dataframe as input to calculations
        self._dataframe = pd.DataFrame()  # dataframe with statistics

        # check if the input data source are grid properties, wells or blocked wells
        dtype = self._establish_input_source(xtgeo_object)

        # get dataframe from XTGeo objects
        create_property_dataframe(self, dtype)

        if autocompute:
            self._dataframe = self._extract_property_statistics()

            if self._csvfile is not None:
                self.to_csv(self._csvfile)

    # ==================================================================================
    # Class properties
    # ==================================================================================

    @property
    def dataframe(self):
        """Returns the Pandas dataframe object containing statistics."""
        return self._dataframe

    @property
    def property_dataframe(self):
        """Returns the Pandas dataframe object used as input to statistics."""
        return self._prop_df

    @property
    def name(self):
        """Returns name used as ID column in dataframe."""
        return self._name

    @name.setter
    def name(self, newname):
        """Set name used as ID column in dataframe."""
        self._name = newname

    @property
    def source(self):
        """Returns the source string."""
        return self._source

    @property
    def codes(self):
        """Returns the codenames used for discrete properties."""
        return self._codes

    # ==================================================================================
    # Hidden class methods
    # ==================================================================================

    def _establish_input_source(self, xtgeo_object):
        """
        Check instance of XTGeo input object.
        Set source, and return string either 'grid or 'wells'.

        The returned value will be used to determine what function to
        run when extracting a property dataframe from the XTGeo instance.
        """

        if isinstance(xtgeo_object, xtgeo.GridProperties):
            dtype = "grid"
            self._gridprops = xtgeo_object

            if self._source is None:
                self._source = dtype

        if isinstance(xtgeo_object, (xtgeo.Wells, xtgeo.BlockedWells)):
            dtype = "wells"
            self._wells = xtgeo_object.wells

            if self._source is None:
                self._source = (
                    dtype if isinstance(xtgeo_object, xtgeo.Wells) else "blocked_wells"
                )

        if not isinstance(
            xtgeo_object, (xtgeo.GridProperties, xtgeo.Wells, xtgeo.BlockedWells)
        ):
            raise TypeError(
                "Argument 'xtgeo_object' must be either an instance of"
                "xtgeo.GridProperties, xtgeo.Wells or xtgeo.BlockedWells"
            )
        return dtype

    def _rename_prop_df_columns(self):
        """
        Rename the columns of the property dataframe.
        From 'name' value to key value in properties and selectors.
        """

        rename_dict = {
            values["name"]: name for name, values in self.pdata.properties.items()
        }
        rename_dict.update(
            {values["name"]: name for name, values in self.pdata.selectors.items()}
        )

        return self.property_dataframe.rename(columns=rename_dict, inplace=True)

    def _extract_property_statistics(self):
        """
        Filter the property dataframe and calculate statistics.
        Returns: A pandas dataframe
        """

        # Filter full property dataframe and rename column headers
        self._prop_df = (
            filter_df(self._prop_df_full, self.pdata.filters)
            if self.pdata.filters
            else self._prop_df_full
        )
        self._rename_prop_df_columns()

        # Compute and return dataframe with statistics
        dframe = compute_statistics_df(self)

        return dframe

    # ==================================================================================
    # Public class methods
    # ==================================================================================

    def to_csv(self, csvfile: str = "../../share/results/tables/propstats.csv"):
        """ Write the property statistics dataframe to csv """
        self.dataframe.to_csv(csvfile, index=False)

    def get_value(self, prop, calculation: str = "Avg", conditions: dict = None):
        """
        Retrive statistical value from property statistics dataframe.

        Args:
            prop (str): name of property
            conditions (dict): A dictionary with selector conditions to look up
                    value for, e.g {"REGION": "EAST", "ZONE": "TOP_ZONE"}. If no
                    conditions are given, the value for the total will be returned.
            calculation (str): Name of column to retrieve value from.

        Returns: float
        """

        if calculation not in PropStat.CALCULATIONS:
            raise KeyError(
                f"{calculation} is not a valid calculation. "
                f"Valid calculations are: {', '.join(PropStat.CALCULATIONS)}"
            )

        conditions = conditions if conditions is not None else {}

        dframe = self.dataframe[self.dataframe["PROPERTY"] == prop]

        if self.pdata.selectors:
            if not all(x in self.pdata.selectors for x in conditions):
                raise ValueError("One or more condition properties are not a selector")

            missing_selectors = [x for x in self.pdata.selectors if x not in conditions]

            # Raise exception if selectors are missing in conditions and
            # selector_combos=False as the result will be unambigous.
            # If selector_combos=True use value "Total" for missing selectors
            if not self._selector_combos and missing_selectors:
                raise ValueError("All selectors needs to be defined in conditions")
            for selector in missing_selectors:
                conditions[selector] = "Total"

            for selector, value in conditions.items():
                dframe = dframe[dframe[selector] == value]

        if len(dframe.index) > 1:
            print(dframe)
            raise Exception("Ambiguous result, multiple rows meet conditions")

        return dframe.iloc[0][calculation]
