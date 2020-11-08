"""Module for common utility functions"""

from itertools import combinations


def filter_df(dframe, filters):
    """Filter dataframe """
    dframe = dframe.copy()
    for prop, filt in filters.items():

        if filt.get("include"):
            if isinstance(filt["include"], str):
                filt["include"] = [filt["include"]]
            if all(x in dframe[prop].unique() for x in filt["include"]):

                dframe = dframe[dframe[prop].isin(filt["include"])]
            else:
                raise ValueError(
                    f"One or more items in {filt['include']} "
                    f"does not exist in dataframe column {prop} "
                    f"Available values are: {dframe[prop].unique()}"
                )
        if filt.get("exclude"):
            if isinstance(filt["exclude"], str):
                filt["exclude"] = [filt["exclude"]]
            if all(x in dframe[prop].unique() for x in filt["exclude"]):
                dframe = dframe[~dframe[prop].isin(filt["exclude"])]
            else:
                raise ValueError(
                    f"One or more items in {filt['exclude']} "
                    f"does not exist in dataframe column {prop} "
                    f"Available values are: {dframe[prop].unique()}"
                )

    if dframe.empty:
        raise Exception("Empty dataframe - no data left after filtering")

    return dframe


def list_combinations(input_list):
    """Create a list of all possible combinations of an existing list"""
    combo_list = []
    for item in range(len(input_list), 0, -1):
        for combo in combinations(input_list, item):
            combo_list.append(list(combo))
    return combo_list
