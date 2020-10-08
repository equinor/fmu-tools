import pandas as pd
from fmu.tools._common import _QCCommon

QCC = _QCCommon()


def combine_property_statistics(
    propstats: list, discrete=False, verbosity=0
) -> pd.DataFrame:
    """
    Combine property dataframes from each PropStat() instance in one dataframe
    """
    QCC.verbosity = verbosity

    dfs = []
    _check_for_duplicate_names(propstats)
    all_selectors = _check_consistency_in_selectors(propstats)

    for pstat in propstats:
        dframe = pstat.dataframe if not discrete else pstat.dataframe_disc
        dframe["ID"] = pstat.name
        dfs.append(dframe)

    dframe = pd.concat(dfs)
    # fill NaN with "Total" for PropStat()'s with missing selectors
    dframe[all_selectors] = dframe[all_selectors].fillna("Total")

    return dframe


def _check_for_duplicate_names(propstats):
    """
    Check if PropStat() instances have similar names, adjust
    names by adding a number to get them unique.
    """
    names = []

    for pstat in propstats:
        pstat.name = pstat.name if pstat.name is not None else pstat.source

        if pstat.name in names:
            count = len([x for x in names if x.startswith(pstat.name)])
            newname = f"{pstat.name}_{count+1}"
            QCC.print_info(
                f"Name {pstat.name} already in use, changing name to {newname}"
            )
            pstat.name = newname
        names.append(pstat.name)


def _check_consistency_in_selectors(propstats):
    """
    Check if all PropStat() instances have the same selectors,
    give warning if not.

    TO-DO: Add check to see if selectors have same codenames

    Same selectors and codenames are needed in order to compare
    data from the different instances in e.g. WebViz
    """
    ps_selectors = []

    for pstat in propstats:
        ps_selectors.append(list(pstat.pdata.selectors.keys()))

    # create list of all unique selectors from the PropStat() instances
    all_selectors = list(set(sum(ps_selectors, [])))

    if not all(len(value) == len(all_selectors) for value in ps_selectors):
        QCC.give_warn("Not all propstat elements have equal selectors")
        for name, sel in zip([pstat.name for pstat in propstats], ps_selectors):
            QCC.print_info(f"name = {name}, selectors = {sel}")

    return all_selectors
