import pandas as pd

from fmu.tools._common import _QCCommon
from fmu.tools.qcdata.qcdata import QCData
from fmu.tools.qcproperties._propstat_parameter_data import PropStatParameterData

QCC = _QCCommon()


def create_property_dataframe(
    parameter_data: PropStatParameterData,
    xtgeo_data: QCData,
    dtype: str,
    verbosity: int = 0,
) -> pd.DataFrame:
    """
    Check if input data type is grid props or wells, and create an unfiltered
    property dataframe for the input parameters/logs.
    """
    QCC.verbosity = verbosity

    if dtype == "grid":
        gridprops = xtgeo_data.gridprops
        dframe = _create_prop_df_from_grid_props(gridprops, parameter_data)
    else:
        wells = xtgeo_data.wells.wells if dtype == "wells" else xtgeo_data.bwells.wells
        dframe = _create_prop_df_from_wells(wells, parameter_data)

    return dframe


def _codes_to_codenames(dframe, pdata, gridprops=None, wells=None):
    """Replace codes in dicrete parameters with codenames"""

    for param in pdata.disc_params:
        codes = _get_param_codes(param, gridprops, wells)
        if pdata.codenames is not None and param in pdata.codenames:
            codes.update(pdata.codenames[param])
        dframe[param] = dframe[param].map(codes.get)
        codes[param] = codes

    return dframe


def _get_param_codes(param, gridprops, wells):
    """Get codenames for discrete parameter"""
    if gridprops is not None:
        xtg_prop = gridprops.get_prop_by_name(param)

        if not xtg_prop.isdiscrete:
            raise RuntimeError(
                "A selector parameter needs to be discrete: "
                f"{param} parameter is not!"
            )
        codes = xtg_prop.codes.copy()
    else:
        codes = wells[0].get_logrecord(param).copy()

    return codes


def _create_prop_df_from_grid_props(gridprops, pdata):
    """
    Extract a combined property dataframe for the input properties.
    Values for discrete logs will be replaced by their codename.
    """
    QCC.print_info("Creating property dataframe from grid properties")
    # check that all properties defined are present as xtgeo properties
    for prop in pdata.params:
        if prop not in gridprops.names:
            raise ValueError(f"Property name {prop} not found in xtg_props")

    dframe = gridprops.dataframe().copy().dropna()

    # Use codenames instead of values for dicrete properties
    dframe = _codes_to_codenames(dframe, pdata, gridprops=gridprops)
    return dframe


def _create_prop_df_from_wells(wells, pdata):
    """
    Create a combined property dataframe for the input wells.
    Values for discrete logs will be replaced by their codename.
    """
    QCC.print_info("Creating property dataframe from well logs")
    # Loop through XTGeo wells and combine into one dataframe
    dfs = []
    for xtg_well in wells:
        # skip well if discrete parameters are missing
        if not all(log in xtg_well.lognames for log in pdata.disc_params):
            QCC.print_info(f"Skipping {xtg_well.name} some dicrete logs are missing")
            continue
        # check that all selectors and filter logs are discrete in well
        for log in pdata.disc_params:
            if log in xtg_well.lognames:
                if not xtg_well.isdiscrete(log):
                    raise ValueError(
                        "Selector and Filter logs needs to be discrete: "
                        f"{log} is not!"
                    )
        # extract dataframe for well
        df_well = xtg_well.dataframe.copy()
        df_well["WELL"] = xtg_well.name
        dfs.append(df_well)
    dframe = pd.concat(dfs)

    # To avoid bias in statistics, drop duplicates to remove
    # cells penetrated by multiple wells.
    dframe = dframe.drop_duplicates(subset=[x for x in dframe.columns if x != "WELL"])
    dframe = dframe[pdata.params]
    # Use codenames instead of values for dicrete properties
    dframe = _codes_to_codenames(dframe, pdata, wells=wells)
    return dframe
