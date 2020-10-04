"""Module containing ....  """
from pathlib import Path
import pandas as pd
import numpy as np

from fmu.tools._common import _QCCommon
from fmu.tools.qcdata.qcdata import QCData

from fmu.tools.qcproperties._propstat_parameter_data import PropStatParameterData
from fmu.tools.qcproperties._property_dataframe import create_property_dataframe
from fmu.tools.qcproperties._utils import list_combinations, filter_df

QCC = _QCCommon()


class PropStat:
    """
    Class for extracting property statistics from Grids, Raw and Blocked wells.

    Statistics for multiple properties can be calculated simultaneosly, and
    selectors can be used to extract statistics per value in discrete
    properties/logs. Filters can be used to remove unwanted data from the datasets.

    Args:
            parameter_data (obj): An instance of PropStatParameterData() containing
                    parameters e.g. properties, selectors and filters.
            xtgeo_data (obj): An instance of QCData() containing XTGeo objects
            data (dict): The input data as a Python dictionary (see description of
                valid argument keys in documentation)
    """

    CALCULATIONS = ["Avg", "Stddev", "Min", "Max", "P10", "P90", "Avg_weighted"]

    def __init__(
        self,
        parameter_data: PropStatParameterData,
        xtgeo_data: QCData,
        data: dict,
    ):

        """Initiate instance"""
        QCC.verbosity = data.get("verbosity", 0)

        self._pdata = parameter_data
        self._xtgdata = xtgeo_data
        self._data = data
        self._dtype = data.get("dtype", None)
        self._name = data.get("name", None)
        self._selector_combos = data.get("selector_combos", True)
        self._codes = {}  # codenames for disc parameters
        self._prop_df_full = pd.DataFrame()  # dataframe containing all parameter values
        self._prop_df = pd.DataFrame()  # filtered dataframe as input to calculations
        self._dataframe = pd.DataFrame()  # dataframe with statistics

        self._set_source()

        # Get dataframe from the XTGeo objects
        self._prop_df_full = create_property_dataframe(
            self._pdata, self._xtgdata, self._dtype, verbosity=QCC.verbosity
        )
        self._dataframe = self.extract_statistics()

        if "csvfile" in data:
            self.to_csv(data["csvfile"])

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
    def pdata(self):
        """Returns the PropStatParameterData instance."""
        return self._pdata

    @pdata.setter
    def pdata(self, newdata):
        """Update the PropStatParameterData instance."""
        self._pdata = newdata

    @property
    def xtgdata(self):
        """Returns available and reusable XTGeo data."""
        return self._xtgdata

    @xtgdata.setter
    def xtgdata(self, newdata):
        """Update available XTGeo data."""
        self._xtgdata = newdata

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

    def _set_source(self):
        """Set source attribute"""
        if "source" in self._data:
            self._source = self._data["source"]
        else:
            self._source = self._dtype
            if self._dtype == "grid":
                self._source = Path(self._data["grid"]).stem
            elif self._dtype == "bwells" and self._data["project"] is not None:
                self._source = self._data["wells"].get("bwname", "BW")

        QCC.print_info(f"Source is set to: '{self._source}'")

    def _update_filters(self, filters, reuse=True):
        """
        Change filters and update  the unfiltered property dataframe if
        a new filter parameter is introduced.
        """

        pdata_upd = PropStatParameterData(
            properties=self.pdata.properties,
            selectors=self.pdata.selectors,
            filters=filters,
        )

        # extract new property dataframe if new parameters are added to filters
        if set(pdata_upd.params) == set(self.pdata.params):
            self.pdata = pdata_upd
            return
        else:
            self.pdata = pdata_upd
            if self._dtype == "grid":
                self._data["gridprops"] = self.pdata.params

            self.xtgdata.parse(
                project=self._data["project"],
                data=self._data,
                reuse=reuse,
                wells_settings=None
                if self._dtype == "grid"
                else {
                    "lognames": self.pdata.params,
                },
            )
            self._prop_df_full = create_property_dataframe(
                self._pdata, self._xtgdata, self._dtype, verbosity=QCC.verbosity
            )

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

    @staticmethod
    def aggregations(dframe=None, weight=None):
        """Statistical aggregations to extract from the data"""

        aggregations = (
            [
                ("Avg", np.mean),
                ("Stddev", np.std),
                ("P10", lambda x: np.nanpercentile(x, q=10)),
                ("P90", lambda x: np.nanpercentile(x, q=90)),
                ("Min", np.min),
                ("Max", np.max),
            ]
            if weight is None
            else [
                (
                    "Avg_weighted",
                    lambda x: np.average(x, weights=dframe.loc[x.index, weight]),
                )
            ]
        )
        return aggregations

    def _calculate_weighted_average(self, groups, group_total):
        """Calculate weighted average for each property where a weight is specified"""

        QCC.print_info("Calculating weighted avarage...")
        dframe = self.property_dataframe.copy()

        dfs = []
        for prop, weight in self.pdata.weights.items():
            df_prop = dframe[dframe[prop].notnull()].copy()
            # Extract statistics for combinations of selectors
            for group in groups:
                df_group = (
                    group[prop]
                    .agg(self.aggregations(df_prop, weight))
                    .reset_index()
                    .assign(PROPERTY=prop)
                )
                dfs.append(df_group)

            # Extract statistics for the total
            df_group = (
                group_total[prop]
                .agg(self.aggregations(df_prop, weight))
                .reset_index(drop=True)
                .assign(PROPERTY=prop)
            )
            dfs.append(df_group)

        return pd.concat(dfs)

    def _group_data_and_aggregate(self):
        """
        Calculate statistics for properties for a given set
        of combinations of discrete selector properties.
        Returns a pandas dataframe.
        """

        dframe = self.property_dataframe.copy()
        properties = list(self.pdata.properties.keys())
        selectors = list(self.pdata.selectors.keys())

        if selectors:
            if self._selector_combos:
                selector_combo_list = list_combinations(selectors)
            else:
                selector_combo_list = selectors if len(selectors) == 1 else [selectors]
            QCC.print_info(
                f"Extracting statistics for selector group in: {selector_combo_list}"
            )
        else:
            selector_combo_list = []
            QCC.print_info("No selectors, extracting statistics for the total")

        # Extract statistics for combinations of selectors
        dfs = []
        groups = []
        for combo in selector_combo_list:
            group = dframe.dropna(subset=combo).groupby(combo)
            groups.append(group)

            df_group = (
                group[properties]
                .agg(self.aggregations())
                .stack(0)
                .rename_axis(combo + ["PROPERTY"])
                .reset_index()
            )
            dfs.append(df_group)

        # Extract statistics for the total
        group_total = dframe.dropna(subset=selectors).groupby(lambda x: "Total")
        df_group = (
            group_total[properties]
            .agg(self.aggregations())
            .stack(0)
            .reset_index(level=0, drop=True)
            .rename_axis(["PROPERTY"])
            .reset_index()
        )
        dfs.append(df_group)
        dframe = pd.concat(dfs)

        # create a dataframe with weighted average if weights are present
        if self.pdata.weights:
            df_weighted = self._calculate_weighted_average(groups, group_total)
            dframe = dframe.merge(
                df_weighted, on=(selectors + ["PROPERTY"]), how="outer"
            )
        # empty values in selectors is filled with "Total"
        dframe[selectors] = dframe[selectors].fillna("Total")

        # return dataframe with specified columns order
        cols_first = ["PROPERTY"] + selectors
        return dframe[cols_first + [x for x in dframe.columns if x not in cols_first]]

    # ==================================================================================
    # Public class methods
    # ==================================================================================

    def extract_statistics(
        self, filters: dict = None, reuse: bool = True
    ) -> pd.DataFrame:
        """Filter the property dataframe and calculate statistics."""

        if filters:
            self._update_filters(filters, reuse)

        # Filter full property dataframe and rename column headers
        self._prop_df = (
            filter_df(self._prop_df_full, self.pdata.filters)
            if self.pdata.filters
            else self._prop_df_full
        )
        self._rename_prop_df_columns()

        # Compute and return dataframe with statistics
        dframe = self._group_data_and_aggregate()
        dframe["SOURCE"] = self._source
        dframe["ID"] = self._name

        return dframe

    def to_csv(self, csvfile: str = "../../share/results/tables/propstats.csv"):
        """ Write the property statistics dataframe to csv """
        self.dataframe.to_csv(csvfile, index=False)

    def get_value(
        self, prop, calculation: str = "Avg", conditions: dict = None
    ) -> float:
        """
        Retrive statistical value from the property statistics dataframe.

        Args:
            prop (str): name of property
            conditions (dict): A dictionary with selector conditions to look up
                    value for, e.g {"REGION": "EAST", "ZONE": "TOP_ZONE"}. If no
                    conditions are given, the value for the total will be returned.
            calculation (str): Name of column to retrieve value from.
        """

        if calculation not in PropStat.CALCULATIONS:
            raise KeyError(
                f"{calculation} is not a valid calculation. "
                f"Valid calculations are: {', '.join(PropStat.CALCULATIONS)}"
            )

        conditions = conditions if conditions is not None else {}

        dframe = self.dataframe[self.dataframe["PROPERTY"] == prop].copy()

        if self.pdata.selectors:
            if not all(x in self.pdata.selectors for x in conditions):
                raise ValueError("One or more condition properties are not a selector")

            missing_selectors = [x for x in self.pdata.selectors if x not in conditions]

            # Raise exception if selectors are missing in conditions and
            # self._=False as the result will be unambigous.
            # If selector_combos=True use value "Total" for missing selectors
            if not self._selector_combos and missing_selectors:
                raise ValueError("All selectors needs to be defined in conditions")
            for selector in missing_selectors:
                conditions[selector] = "Total"

            for selector, value in conditions.items():
                if value not in dframe[selector].unique():
                    raise ValueError(
                        f"{value} not found in column {selector}"
                        f"Valid options are {dframe[selector].unique()}"
                    )
                dframe = dframe[dframe[selector] == value]

        if len(dframe.index) > 1:
            print(dframe)
            raise Exception("Ambiguous result, multiple rows meet conditions")

        return dframe.iloc[0][calculation]
