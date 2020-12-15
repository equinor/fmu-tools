"""Module containing ....  """
from pathlib import Path
import pandas as pd
import numpy as np

from fmu.tools._common import _QCCommon
from fmu.tools.qcdata import QCData

from fmu.tools.qcproperties._propstat_parameter_data import PropStatParameterData

# from fmu.tools.qcproperties._property_dataframe import create_property_dataframe
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

    CALCULATIONS = [
        "Avg",
        "Stddev",
        "Min",
        "Max",
        "P10",
        "P90",
        "Avg_weighted",
        "Percent",
        "Percent_weighted",
    ]

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
        self._dataframe_disc = pd.DataFrame()  # dataframe with percentages

        self._set_source()
        self._set_wells()
        self._check_properties()

        # Get dataframe from the XTGeo objects
        self._prop_df_full = (
            self._create_prop_df_from_grid_props()
            if self._dtype == "grid"
            else self._create_prop_df_from_wells()
        )
        # Get dataframe from the XTGeo objects
        self.extract_statistics()

        if "csvfile" in data:
            self.to_csv(data["csvfile"])

    # ==================================================================================
    # Class properties
    # ==================================================================================

    @property
    def dataframe(self):
        """Returns the dataframe with continous property statistics."""
        return self._dataframe

    @property
    def property_dataframe(self):
        """Returns the Pandas dataframe object used as input to statistics."""
        return self._prop_df

    @property
    def dataframe_disc(self):
        """Returns the dataframe with dicrete property statistics."""
        return self._dataframe_disc

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
                self._source = self._data["bwells"].get("bwname", "BW")

        QCC.print_info(f"Source is set to: '{self._source}'")

    def _set_wells(self):
        """Set wells attribute"""
        if self._dtype != "grid":
            self._wells = (
                self._xtgdata.wells.wells
                if self._dtype == "wells"
                else self._xtgdata.bwells.wells
            )
            self._validate_wells()
        else:
            self._wells = None

    def _check_properties(self):
        """Group properties into continous and discrete"""
        self._disc_props = []
        self._cont_props = []

        for prop, values in self.pdata.properties.items():
            if self._dtype == "grid":
                xtg_prop = self._xtgdata.gridprops.get_prop_by_name(values["name"])
                if xtg_prop.isdiscrete:
                    self._disc_props.append(prop)
                    if values["name"] not in self.pdata.disc_params:
                        self.pdata.disc_params.append(values["name"])
                else:
                    self._cont_props.append(prop)
            else:
                if self._wells[0].isdiscrete(values["name"]):
                    self._disc_props.append(prop)
                    if values["name"] not in self.pdata.disc_params:
                        self.pdata.disc_params.append(values["name"])
                else:
                    self._cont_props.append(prop)

    def _codes_to_codenames(self, dframe):
        """Replace codes in dicrete parameters with codenames"""
        for param in self.pdata.disc_params:
            if self._dtype == "grid":
                xtg_prop = self._xtgdata.gridprops.get_prop_by_name(param)

                if not xtg_prop.isdiscrete:
                    raise RuntimeError(
                        "A selector parameter needs to be discrete: "
                        f"{param} parameter is not!"
                    )
                codes = xtg_prop.codes.copy()
            else:
                codes = self._wells[0].get_logrecord(param).copy()

            if self.pdata.codenames is not None and param in self.pdata.codenames:
                codes.update(self.pdata.codenames[param])
            self._codes[param] = codes

            # replace codes values in dataframe with code names
            dframe[param] = dframe[param].map(codes.get)
        return dframe

    def _create_prop_df_from_grid_props(self):
        """
        Extract a combined property dataframe for the input properties.
        Values for discrete logs will be replaced by their codename.
        """
        QCC.print_info("Creating property dataframe from grid properties")
        # check that all properties defined are present as xtgeo properties
        for prop in self.pdata.params:
            if prop not in self._xtgdata.gridprops.names:
                print(self._xtgdata.gridprops.names)
                raise ValueError(f"Property name {prop} not found in xtg_props")

        dframe = self._xtgdata.gridprops.dataframe().copy().dropna()

        # replace codes values in dataframe with code names
        return self._codes_to_codenames(dframe)

    def _validate_wells(self):
        removed_wells = []
        for xtg_well in self._wells:
            # skip well if discrete parameters are missing
            if not all(log in xtg_well.lognames for log in self.pdata.disc_params):
                QCC.print_info(
                    f"Skipping {xtg_well.name} some dicrete logs are missing"
                )
                removed_wells.append(xtg_well)
                continue
            for log in self.pdata.disc_params:
                if log in xtg_well.lognames:
                    if not xtg_well.isdiscrete(log):
                        raise ValueError(
                            "Selector and Filter logs needs to be discrete: "
                            f"{log} is not!"
                        )
        self._wells = [
            xtg_well for xtg_well in self._wells if xtg_well not in removed_wells
        ]

    def _create_prop_df_from_wells(self):
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
        dframe = dframe[self.pdata.params]
        # replace codes values in dataframe with code names
        return self._codes_to_codenames(dframe)

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
            self._prop_df_full = (
                self._create_prop_df_from_grid_props()
                if self._dtype == "grid"
                else self._create_prop_df_from_wells()
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

    def _aggregations(self, dframe=None, discrete=False):
        """Statistical aggregations to extract from the data"""

        return (
            [
                ("Avg", np.mean),
                ("Stddev", np.std),
                ("P10", lambda x: np.nanpercentile(x, q=10)),
                ("P90", lambda x: np.nanpercentile(x, q=90)),
                ("Min", np.min),
                ("Max", np.max),
                (
                    "Avg_Weighted",
                    lambda x: np.average(
                        x.dropna(),
                        weights=dframe.loc[
                            x.dropna().index, self.pdata.weights[x.name]
                        ],
                    )
                    if x.name in self.pdata.weights
                    else np.nan,
                ),
            ]
            if not discrete
            else [
                ("Count", "count"),
                (
                    "Sum_Weight",
                    lambda x: np.sum(x)
                    if x.name in list(self.pdata.weights.values())
                    else np.nan,
                ),
            ]
        )

    def _calculate_statistics(self, selector_combo_list, selectors):
        """
        Calculate statistics for continous properties.
        Returns a pandas dataframe.
        """
        dframe = self.property_dataframe.copy()

        # Extract statistics for combinations of selectors
        dfs = []
        groups = []
        for combo in selector_combo_list:
            group = dframe.dropna(subset=combo).groupby(combo)
            groups.append(group)

            df_group = (
                group[self._cont_props]
                .agg(self._aggregations(dframe=dframe))
                .stack(0)
                .rename_axis(combo + ["PROPERTY"])
                .reset_index()
            )
            dfs.append(df_group)

        # Extract statistics for the total
        group_total = dframe.dropna(subset=selectors).groupby(lambda x: "Total")
        df_group = (
            group_total[self._cont_props]
            .agg(self._aggregations(dframe=dframe))
            .stack(0)
            .reset_index(level=0, drop=True)
            .rename_axis(["PROPERTY"])
            .reset_index()
        )
        dfs.append(df_group)
        dframe = pd.concat(dfs)

        # empty values in selectors is filled with "Total"
        dframe[selectors] = dframe[selectors].fillna("Total")

        # return dataframe with specified columns order
        cols_first = ["PROPERTY"] + selectors
        dframe = dframe[cols_first + [x for x in dframe.columns if x not in cols_first]]

        dframe["SOURCE"] = self._source
        dframe["ID"] = self._name
        return dframe

    def _calculate_percentages(self, selector_combo_list, selectors):
        """
        Calculate statistics for discrete properties. A Weighted Percent
        is calculated for each property where a weight is specified
        Returns a pandas dataframe.
        """
        dframe = self.property_dataframe.copy()

        combo_list = selector_combo_list
        selectors = selectors.copy()

        dfs = []
        for prop in self._disc_props:
            if prop not in selectors:
                combo_list = [x + [prop] for x in selector_combo_list]
                combo_list.append([prop])
                selectors.append(prop)

            select = self.pdata.weights[prop] if prop in self.pdata.weights else prop

            for combo in combo_list:
                df_prop = dframe.dropna(subset=combo).copy()
                df_group = (
                    df_prop.groupby(combo)[select]
                    .agg(self._aggregations(discrete=True))
                    .reset_index()
                    .assign(PROPERTY=prop)
                )

                for col, name in {
                    "Percent_weighted": "Sum_Weight",
                    "Percent": "Count",
                }.items():
                    df_group[f"Total_{name}"] = (
                        df_group.groupby([x for x in combo if x != prop])[
                            name
                        ].transform(lambda x: x.sum())
                        if combo != [prop]
                        else df_group[name].sum()
                    )
                    df_group[col] = (df_group[name] / df_group[f"Total_{name}"]) * 100

                df_group = df_group.drop(
                    columns=["Total_Sum_Weight", "Total_Count", "Sum_Weight"]
                )
                dfs.append(df_group)

        dframe = pd.concat(dfs)

        # empty values in selectors is filled with "Total"
        dframe[selectors] = dframe[selectors].fillna("Total")

        # return dataframe with specified columns order
        cols_first = ["PROPERTY"] + selectors
        dframe = dframe[cols_first + [x for x in dframe.columns if x not in cols_first]]

        dframe["SOURCE"] = self._source
        dframe["ID"] = self._name
        return dframe

    def _group_data_and_aggregate(self):
        """
        Calculate statistics for properties for a given set
        of combinations of discrete selector properties.
        Returns a pandas dataframe.
        """
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

        if self._cont_props:
            QCC.print_info("Calculating statistics for continous properties...")
            self._dataframe = self._calculate_statistics(selector_combo_list, selectors)

        if self._disc_props:
            QCC.print_info("Calculating percentages for discrete properties...")
            self._dataframe_disc = self._calculate_percentages(
                selector_combo_list, selectors
            )

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

        # Generate dataframes with statistics
        self._group_data_and_aggregate()

    def to_csv(self, csvfile: str = "../../share/results/tables/propstats.csv"):
        """ Write the property statistics dataframe to csv """
        self.dataframe.to_csv(csvfile, index=False)

    def get_value(
        self, prop, calculation: str = None, conditions: dict = None, codename=None
    ) -> float:
        """
        Retrive statistical value from either of the two the property statistics
        dataframes (dependent on the property type, discrete vs continous).

        Args:
            prop (str): name of property
            conditions (dict): A dictionary with selector conditions to look up
                    value for, e.g {"REGION": "EAST", "ZONE": "TOP_ZONE"}. If no
                    conditions are given, the value for the total will be returned.
            calculation (str): Name of column to retrieve value from. "Avg" is the
                    default for continous properties, "Percent" for discrete.
            codename (str): Codename to select for discrete properties
        """

        conditions = conditions if conditions is not None else {}
        disc_prop = True if prop in self._disc_props else False

        if disc_prop:
            if codename is not None:
                conditions[prop] = codename
            else:
                raise ValueError(
                    "A 'codename' argument is needed for discrete properties"
                )

        if calculation is None:
            calculation = "Avg" if prop in self._cont_props else "Percent"

        if calculation not in PropStat.CALCULATIONS:
            raise KeyError(
                f"{calculation} is not a valid calculation. "
                f"Valid calculations are: {', '.join(PropStat.CALCULATIONS)}"
            )

        dframe = self.dataframe if not disc_prop else self.dataframe_disc
        dframe = dframe[dframe["PROPERTY"] == prop].copy()

        selectors = list(self.pdata.selectors.keys())
        if disc_prop and prop not in selectors:
            selectors = selectors.append(prop) if selectors else [prop]

        if selectors:
            if not all(x in selectors for x in conditions):
                raise ValueError("One or more condition properties are not a selector")

            missing_selectors = [x for x in selectors if x not in conditions]

            # Raise exception if selectors are missing in conditions and
            # self._selector_combos=False as the result will be unambigous.
            # If selector_combos=True use value "Total" for missing selectors
            if not self._selector_combos and missing_selectors:
                raise ValueError("All selectors needs to be defined in conditions")

            for selector in missing_selectors:
                conditions[selector] = "Total"

            for selector, value in conditions.items():
                if value not in dframe[selector].unique():
                    raise ValueError(
                        f"{value} not found in column {selector} "
                        f"Valid options are {dframe[selector].unique()}"
                    )
                dframe = dframe[dframe[selector] == value]

        if len(dframe.index) > 1:
            print(dframe)
            raise Exception("Ambiguous result, multiple rows meet conditions")

        return dframe.iloc[0][calculation]
