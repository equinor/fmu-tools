import pandas as pd


def _check_for_duplicate_names(self):
    """
    Check if PropStat() instances have similar names, adjust
    names by adding a number to get them unique.
    """
    names = []

    for pstat in self._propstats:
        pstat.name = pstat.name if pstat.name is not None else pstat.source

        if pstat.name in names:
            count = len([x for x in names if x.startswith(pstat.name)])
            pstat.name = f"{pstat.name}_{count+1}"

        names.append(pstat.name)


def _check_consistency_in_selectors(self):
    """
    Check if all PropStat() instances have the same selectors,
    give warning if not.

    TO-DO: Add check to see if selectors have same codenames

    Same selectors and codenames are needed in order to compare
    data from the different instances in e.g. WebViz
    """
    ps_selectors = []

    for pstat in self._propstats:
        ps_selectors.append(list(pstat.pdata.selectors.keys()))

    if not all(value == next(iter(ps_selectors)) for value in ps_selectors):
        print("WARNING: not all propstat elements have equal selectors")
        print(
            [
                (f"name = {name} selectors = {sel}")
                for name, sel in zip(
                    [pstat.name for pstat in self._propstats], ps_selectors
                )
            ]
        )


def combine_property_statistics(self):
    """Collect contents of dataframes from each ensemble"""

    dfs = []

    _check_for_duplicate_names(self)
    _check_consistency_in_selectors(self)

    for pstat in self._propstats:
        dframe = pstat.dataframe
        dframe["ID"] = pstat.name
        dfs.append(dframe)

    return pd.concat(dfs)
