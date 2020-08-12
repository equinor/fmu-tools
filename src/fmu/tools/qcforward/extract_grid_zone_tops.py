import pandas as pd
import xtgeo


class MockProject:
    # pylint: disable=too-few-public-methods
    @property
    def wells(self):
        """mock"""
        return None


try:
    project
except NameError:
    project = MockProject()


def extract_grid_zone_tops(
    well_list,
    logrun="log",
    trajectory="Drilled trajectory",
    gridzonelog=None,
    mdlogname=None,
    grid=None,
    zone_param=None,
    inside_rms=False,
):
    """
    Function for extracting top and base from gridzones, both in TVD and MD.

    Users can either input a pre-generated gridzonelog or a grid and a zone parameter
    for computing the gridzonelog.

    The function works both inside RMS and outside with file input. If input from files,
    and a MD log is not present in the well a quasi md log will be computed and used.
    """

    if gridzonelog is not None and grid is not None and zone_param is not None:
        raise ValueError("Specify either 'gridzonelog' or 'grid' and 'zone_param")

    if gridzonelog is None:
        if inside_rms:
            mygrid = xtgeo.grid_from_roxar(project, grid)
            gridzones = xtgeo.gridproperty_from_roxar(project, grid, zone_param)
        else:
            mygrid = xtgeo.grid_from_file(grid)
            gridzones = xtgeo.gridproperty_from_file(zone_param, grid=mygrid)

    dfs = []
    for well in well_list:
        try:
            if inside_rms:
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
        if gridzonelog is None:
            xtg_well.get_gridproperties(gridzones, mygrid)
            gridzonelog = f"{zone_param}_model" if inside_rms else "unknown_model"

        if xtg_well.dataframe[gridzonelog].isnull().values.all():
            continue

        # Set gridzonelog as zonelog and extract zonation tops from it
        xtg_well.zonelogname = gridzonelog
        dframe = xtg_well.get_zonation_points(top_prefix="", use_undef=True)

        dframe.rename(
            columns={
                "Z_TVDSS": "TOP_TVD",
                xtg_well.mdlogname: "TOP_MD",
                "Zone": "ZONE_val",
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
        dframe["ZONE_val"] = shift_zone_values(dframe["ZONE_val"].values.copy())
        dframe["ZONE"] = (
            dframe["ZONE_val"]
            .map(xtg_well.get_logrecord(xtg_well.zonelogname))
            .fillna("Outside")
        )
        dfs.append(dframe.drop(columns=["TopName", "Q_INCL", "Q_AZI"]))

    return pd.concat(dfs)


def shift_zone_values(zvals):
    for idx, _zval in enumerate(zvals):
        if idx == len(zvals) - 1:
            continue
        if zvals[idx] == zvals[idx + 1]:
            zvals[idx + 1] = zvals[idx + 1] - 1
    return zvals


if __name__ == "__main__":

    WELLS = project.wells
    LOGRUN = "data"
    GRID = "RG"
    ZONE_PARAM = "Zone"
    GRIDZONELOG = "zone_RG"

    # df_tops = xtract_gridzonetops(WELLS, GRID, ZONE_PARAM, LOGRUN)
    df_tops = extract_grid_zone_tops(
        WELLS, logrun=LOGRUN, gridzonelog=GRIDZONELOG, inside_rms=True
    )
    df_tops.to_csv("./formation_grid_tops.csv", index=False)
