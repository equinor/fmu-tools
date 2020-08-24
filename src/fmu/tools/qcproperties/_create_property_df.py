import pandas as pd


def create_property_dataframe(self, dtype: str) -> pd.DataFrame:
    """
    Create a full property dataframe for the input parameters/logs.
    Separate functions exists for extracting 3D grid data vs well data.

    Args:
        dtype (string): Controls what funtion to run (options "grid" or "wells")

    """
    if dtype == "grid":
        self._prop_df_full = _create_prop_df_from_grid_props(self)
    if dtype == "wells":
        self._prop_df_full = _create_prop_df_from_wells(self)


def _create_prop_df_from_grid_props(self):
    """
    Extract a combined property dataframe for the input properties.
    Values for discrete logs will be replaced by their codename.
    """
    myprops = self._gridprops

    # check that all properties defined are present as xtgeo properties
    for prop in self.pdata.params:
        if prop not in myprops.names:
            raise ValueError(f"Property name {prop} not found in xtg_props")

    dframe = myprops.dataframe().dropna()

    # Use codenames instead of values for dicrete properties
    for param in self.pdata.disc_params:
        xtg_prop = myprops.get_prop_by_name(param)
        if xtg_prop.isdiscrete:
            codes = xtg_prop.codes
            if self.pdata.codenames is not None and param in self.pdata.codenames:
                codes.update(self.pdata.codenames[param])
            dframe[param] = dframe[param].map(codes.get)
            self._codes[param] = codes
        else:
            raise RuntimeError(
                "A selector parameter needs to be discrete: "
                f"{param} parameter is not!"
            )

    return dframe


def _xtg_wells_to_df(self):
    """ Loop through XTGeo wells and combine into one dataframe """

    dfs = []
    for xtg_well in self._wells:
        # skip well if discrete parameters are missing
        if not all(log in xtg_well.lognames for log in self.pdata.disc_params):
            print(f"Skipping {xtg_well.name} as logs are missing")
            continue

        # check that all selectors and filter logs are discrete in well
        for log in self.pdata.disc_params:
            if log in xtg_well.lognames:
                if not xtg_well.isdiscrete(log):
                    raise ValueError(
                        "Selector and Filter logs needs to be discrete: "
                        f"{log} is not!"
                    )

        # extract dataframe for well
        df_well = xtg_well.dataframe
        df_well["WELL"] = xtg_well.name
        dfs.append(df_well)

    return pd.concat(dfs)


def _create_prop_df_from_wells(self):
    """
    Create a combined property dataframe for the input wells.
    Values for discrete logs will be replaced by their codename.
    """

    dframe = _xtg_wells_to_df(self)

    # To avoid bias in statistics, drop duplicates to remove
    # cells penetrated by multiple wells.
    dframe = dframe.drop_duplicates(subset=[x for x in dframe.columns if x != "WELL"])
    dframe = dframe[self.pdata.params]

    # Use codenames instead of values for dicrete properties
    for param in self.pdata.disc_params:
        codes = self._wells[0].get_logrecord(param)
        if self.pdata.codenames is not None and param in self.pdata.codenames:
            codes.update(self.pdata.codenames[param])
        dframe[param] = dframe[param].map(codes.get)
        self._codes[param] = codes
    return dframe
