"""Extract grid zone tops from wells."""

import pathlib
from typing import Any, Dict, Optional, Union

import numpy as np
import pandas as pd
import xtgeo


def extract_grid_zone_tops(
    project: Optional[Any] = None,
    well_list: Optional[list] = None,
    logrun: str = "log",
    trajectory: str = "Drilled trajectory",
    gridzonelog: Optional[str] = None,
    mdlogname: Optional[str] = None,
    grid: Optional[str] = None,
    zone_param: Optional[str] = None,
    alias_file: Optional[str] = None,
    rms_name: str = "RMS_WELL_NAME",
    ecl_name: str = "ECLIPSE_WELL_NAME",
) -> pd.DataFrame:
    """
    Function for extracting top and base from gridzones, both in TVD and MD.
    A pandas dataframe will be returned.

    Users can either input a pre-generated gridzonelog or a grid and a zone parameter
    for computing the gridzonelog.

    The function works both inside RMS and outside with file input. If input from files,
    and a MD log is not present in the well a quasi md log will be computed and used.
    """
    use_gridzonelog = gridzonelog is not None

    if not use_gridzonelog:
        if grid is not None and zone_param is not None:
            if project is not None:
                mygrid = xtgeo.grid_from_roxar(project, grid)
                gridzones = xtgeo.gridproperty_from_roxar(project, grid, zone_param)
            else:
                mygrid = xtgeo.grid_from_file(grid)
                gridzones = xtgeo.gridproperty_from_file(zone_param, grid=mygrid)
            gridzones.name = "Zone"
        else:
            raise ValueError("Specify either 'gridzonelog' or 'grid' and 'zone_param")

    dfs = []

    if well_list is None:
        well_list = []

    for well in well_list:
        try:
            if project is not None:
                xtg_well = xtgeo.well_from_roxar(
                    project,
                    str(well),
                    trajectory=trajectory,
                    logrun=logrun,
                    inclmd=True,
                )
            else:
                xtg_well = xtgeo.well_from_file(str(well), mdlogname=mdlogname)
                # quasi md log will be computed
                xtg_well.geometrics()
        except (ValueError, KeyError):
            continue

        # if no gridzonelog create one from the zone parameter
        if not use_gridzonelog:
            xtg_well.get_gridproperties(gridzones, mygrid)
            gridzonelog = "Zone_model"

        if xtg_well.dataframe[gridzonelog].isnull().values.all():
            continue

        # Set gridzonelog as zonelog and extract zonation tops from it
        xtg_well.zonelogname = gridzonelog
        dframe = xtg_well.get_zonation_points(top_prefix="", use_undef=True)

        dframe.rename(
            columns={
                "Z_TVDSS": "TOP_TVD",
                xtg_well.mdlogname: "TOP_MD",
                "Zone": "ZONE_CODE",
                "WellName": "WELL",
            },
            inplace=True,
        )
        # find deepest point in well while in grid
        df_max = (
            xtg_well.dataframe[["Z_TVDSS", xtg_well.mdlogname, gridzonelog]]
            .dropna()
            .sort_values(by=xtg_well.mdlogname)
        )
        # create base picks also
        dframe["BASE_TVD"] = dframe["TOP_TVD"].shift(-1)
        dframe["BASE_MD"] = dframe["TOP_MD"].shift(-1)
        dframe.at[dframe.index[-1], "BASE_TVD"] = df_max.iloc[-1]["Z_TVDSS"]
        dframe.at[dframe.index[-1], "BASE_MD"] = df_max.iloc[-1][xtg_well.mdlogname]
        # adjust zone values to get correct zone information
        dframe["ZONE_CODE"] = shift_zone_values(dframe["ZONE_CODE"].values.copy())
        dframe["ZONE"] = (
            dframe["ZONE_CODE"]
            .map(xtg_well.get_logrecord(xtg_well.zonelogname))
            .fillna("Outside")
        )
        dfs.append(dframe.drop(columns=["TopName", "Q_INCL", "Q_AZI"], errors="ignore"))

    df = pd.concat(dfs)
    if alias_file is not None:
        well_dict = make_alias_dict(alias_file, rms_name, ecl_name)
        df["WELL"] = df["WELL"].replace(well_dict)
    return df


def shift_zone_values(zvals: np.ndarray) -> np.ndarray:
    for idx, _zval in enumerate(zvals):
        if idx == len(zvals) - 1:
            continue
        if zvals[idx] == zvals[idx + 1]:
            zvals[idx + 1] = zvals[idx + 1] - 1
    return zvals


def make_alias_dict(
    alias_file: Union[str, pathlib.Path],
    rms_name: str = "RMS_WELL_NAME",
    ecl_name: str = "ECLIPSE_WELL_NAME",
) -> Dict[str, str]:
    """
    Create a correspondance dictionary so that well_dict[ <RMS wellname> ]
    = <Eclipse wellname>
    """
    df = pd.read_csv(alias_file, index_col=rms_name)
    well_dict = df.to_dict()
    return well_dict[ecl_name]
