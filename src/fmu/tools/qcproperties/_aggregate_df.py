"""Module containing ...."""

import numpy as np
import pandas as pd

from fmu.tools._common import _QCCommon
from fmu.tools.qcproperties._utils import list_combinations

QCC = _QCCommon()


class PropertyAggregation:
    """
    Class for extracting statistics from a property dataframe.
    Statistics for multiple properties can be calculated simultaneosly. The
    aggregation methods and statistics are based on the property type.
    Selectors can be used to extract statistics per value in discrete properties.
    """

    def __init__(
        self,
        props2df,
    ):
        """Initiate instance"""
        self._property_dataframe = props2df.dataframe  # dataframe with properties
        self._controls = props2df.aggregation_controls
        self._controls["property_type"] = props2df.property_type
        self._dataframe = pd.DataFrame()  # dataframe with statistics

        QCC.verbosity = self._controls["verbosity"]

        # Create list with groups for pandas groupby
        selector_combo_list = (
            list_combinations(self._controls["selectors"])
            if self._controls["selector_combos"]
            else [self._controls["selectors"]]
        )

        # Compute dataframe with statistics
        QCC.print_info(
            f"Calculating statistics for {self._controls['property_type']} properties"
        )
        self._dataframe = (
            self._calculate_continous_statistics(selector_combo_list)
            if self._controls["property_type"] == "CONT"
            else self._calculate_discrete_fractions(selector_combo_list)
        )

    # ==================================================================================
    # Class properties
    # ==================================================================================

    @property
    def dataframe(self):
        """Returns the dataframe with property statistics."""
        return self._dataframe

    @property
    def controls(self):
        """Attribute with data used for statistics aggregation."""
        return self._controls

    # ==================================================================================
    # Hidden class methods
    # ==================================================================================

    def _disc_aggregations(self):
        """Statistical aggregations to extract from continous data"""
        return [
            ("Count", "count"),
            (
                "Sum_Weight",
                lambda x: np.sum(x)
                if x.name in list(self._controls["weights"].values())
                else np.nan,
            ),
        ]

    def _cont_aggregations(self, dframe=None):
        """Statistical aggregations to extract from discrete data"""
        return [
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
                        x.dropna().index, self._controls["weights"][x.name]
                    ],
                )
                if x.name in self._controls["weights"]
                else np.nan,
            ),
            ("Count", "count"),
        ]

    def _calculate_continous_statistics(self, selector_combo_list):
        """
        Calculate statistics for continous properties.
        Returns a pandas dataframe.
        """

        # Extract statistics for combinations of selectors
        dfs = []
        groups = []
        for combo in selector_combo_list:
            group = self._property_dataframe.dropna(subset=combo).groupby(combo)
            groups.append(group)

            df_group = (
                group[self._controls["properties"]]
                .agg(self._cont_aggregations(dframe=self._property_dataframe))
                .stack(0)
                .rename_axis(combo + ["PROPERTY"])
                .reset_index()
            )
            dfs.append(df_group)

        # Extract statistics for the total
        group_total = self._property_dataframe.dropna(
            subset=self._controls["selectors"]
        ).groupby(lambda x: "Total")
        df_group = (
            group_total[self._controls["properties"]]
            .agg(self._cont_aggregations(dframe=self._property_dataframe))
            .stack(0)
            .reset_index(level=0, drop=True)
            .rename_axis(["PROPERTY"])
            .reset_index()
        )
        dfs.append(df_group)
        dframe = pd.concat(dfs)

        # Empty values in selectors is filled with "Total"
        dframe[self._controls["selectors"]] = dframe[
            self._controls["selectors"]
        ].fillna("Total")

        return dframe

    def _calculate_discrete_fractions(self, selector_combo_list):
        """
        Calculate fraction statistics for discrete properties. A Weighted
        fraction is calculated for each property where a weight is specified
        Returns a pandas dataframe.
        """

        # Extract statistics for combinations of selectors
        combo_list = selector_combo_list
        dfs = []
        for prop in self._controls["properties"]:
            if prop not in self._controls["selectors"]:
                combo_list = [x + [prop] for x in selector_combo_list]
                combo_list.append([prop])
                self._controls["selectors"].append(prop)

            select = self._controls["weights"].get(prop, prop)

            for combo in combo_list:
                df_prop = self._property_dataframe.dropna(subset=combo).copy()
                df_group = (
                    df_prop.groupby(combo)[select]
                    .agg(self._disc_aggregations())
                    .reset_index()
                    .assign(PROPERTY=prop)
                )

                for col, name in {
                    "Avg_Weighted": "Sum_Weight",
                    "Avg": "Count",
                }.items():
                    df_group[f"Total_{name}"] = (
                        df_group.groupby([x for x in combo if x != prop])[
                            name
                        ].transform(lambda x: x.sum())
                        if combo != [prop]
                        else df_group[name].sum()
                    )
                    df_group[col] = df_group[name] / df_group[f"Total_{name}"]

                df_group = df_group.drop(
                    columns=["Total_Sum_Weight", "Total_Count", "Sum_Weight"]
                )
                dfs.append(df_group)

        dframe = pd.concat(dfs)

        # Empty values in selectors is filled with "Total"
        dframe[self._controls["selectors"]] = dframe[
            self._controls["selectors"]
        ].fillna("Total")

        return dframe
