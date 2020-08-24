import pandas as pd
import numpy as np

from fmu.tools.qcproperties._utils import list_combinations


def aggregations():
    """Statistical aggregations to extract from the data"""
    return [
        ("Avg", np.mean),
        ("Stddev", np.std),
        ("P10", lambda x: np.nanpercentile(x, q=10)),
        ("P90", lambda x: np.nanpercentile(x, q=90)),
        ("Min", np.min),
        ("Max", np.max),
    ]


def agg_avg_weight(dframe, weight):
    """Aggregation for extracting weighted average from the data"""
    return [
        (
            "Avg_weighted",
            lambda x: np.average(x, weights=dframe.loc[x.index, weight]),
        )
    ]


def calculate_weighted_average(self, selectors, groups, group_total):
    """Calculate weighted average for each property where a weight is specified"""

    dframe = self.property_dataframe

    dfs = []
    for prop, weight in self.pdata.weights.items():
        df_prop = dframe[dframe[prop].notnull()].copy()
        # Extract statistics for combinations of selectors
        for group in groups:
            df_group = group[prop].agg(agg_avg_weight(df_prop, weight)).reset_index()
            df_group["PROPERTY"] = prop
            dfs.append(df_group)

        # Extract statistics for the total
        df_group = (
            group_total[prop]
            .agg(agg_avg_weight(df_prop, weight))
            .reset_index(drop=True)
        )
        df_group["PROPERTY"] = prop
        dfs.append(df_group)

    dframe = pd.concat(dfs)
    dframe[selectors] = dframe[selectors].fillna("Total")

    return dframe


def group_data_and_aggregate(self, selector_combos=True):
    """
    Calculate statistics for properties for a given set
    of combinations of discrete selector properties.
    Returns a pandas dataframe.
    """

    dframe = self.property_dataframe
    properties = list(self.pdata.properties.keys())
    selectors = list(self.pdata.selectors.keys())

    if selectors:
        if selector_combos:
            selector_combo_list = list_combinations(selectors)
            print(f"Extracting statistics for combinations of: {', '.join(selectors)}")
        else:
            selector_combo_list = selectors if len(selectors) == 1 else [selectors]
            print(f"Extracting statistics per: {', '.join(selectors)}")
    else:
        selector_combo_list = []
        print("Extracting statistics for total")

    # Extract statistics for combinations of selectors
    dfs = []
    groups = []

    for combo in selector_combo_list:
        group = dframe.dropna(subset=combo).groupby(combo)
        groups.append(group)

        df_group = (
            group[properties]
            .agg(aggregations())
            .stack(0)
            .rename_axis(combo + ["PROPERTY"])
            .reset_index()
        )
        dfs.append(df_group)

    # Extract statistics for the total
    group_total = dframe.dropna(subset=selectors).groupby(lambda x: "Total")
    df_group = (
        group_total[properties]
        .agg(aggregations())
        .stack(0)
        .reset_index(level=0, drop=True)
        .rename_axis(["PROPERTY"])
        .reset_index()
    )

    dfs.append(df_group)

    dframe = pd.concat(dfs)
    dframe[selectors] = dframe[selectors].fillna("Total")

    # create a dataframe with weighted average for properties where a weight is present
    if self.pdata.weights:
        df_weighted = calculate_weighted_average(self, selectors, groups, group_total)
        dframe = dframe.merge(df_weighted, on=(selectors + ["PROPERTY"]), how="outer")

    # rearrange order of columns in datframe
    cols_first = ["PROPERTY"] + selectors
    dframe = dframe[cols_first + [x for x in dframe.columns if x not in cols_first]]

    return dframe


def compute_statistics_df(self):

    dframe = group_data_and_aggregate(self, selector_combos=self._selector_combos)
    dframe["SOURCE"] = self._source
    dframe["ID"] = self._name

    return dframe
