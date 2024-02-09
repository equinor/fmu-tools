"""The qcproperties module"""

from pathlib import Path
from typing import Any, Optional

import pandas as pd
import yaml

from fmu.tools._common import _QCCommon
from fmu.tools.qcdata import QCData
from fmu.tools.qcproperties._aggregate_df import PropertyAggregation
from fmu.tools.qcproperties._grid2df import GridProps2df
from fmu.tools.qcproperties._well2df import WellLogs2df

QCC = _QCCommon()


class QCProperties:
    """
    The QCProperties class consists of a set of methods for extracting
    property statistics from 3D Grids, Raw and Blocked wells.

    Statistics can be collected from either discrete or continous properties.
    Dependent on the property different statistics are collected.

    The methods for statistics extraction can be run individually, or a
    yaml-configuration file can be used to enable an automatic run of the
    methods. See the method 'from_yaml'.

    When several methods of statistics extraction has been run within the instance,
    a merged dataframe is available through the 'dataframe' property.

    All methods can be run from either RMS python, or from files.

    XTGeo is being utilized to get a dataframe from the input parameter data.
    XTGeo data is reused in the instance to increase performance.

    """

    def __init__(self):
        self._xtgdata = QCData()  # QCData instance, general XTGeo data
        self._dfs = []  # list of dataframes with aggregated statistics
        self._selectors_all = []
        self._proptypes_all = []
        self._ids = []
        self._dataframe = pd.DataFrame()  # merged dataframe with statistics

    # Properties:
    # ==================================================================================

    @property
    def dataframe(self):
        """Dataframe with statistics"""
        self._dataframe = self._create_or_return_dataframe()
        return self._dataframe

    # Hidden methods:
    # ==================================================================================

    def _initiate_from_config(self, cfg: str, project: Optional[object]):
        """Run methods for statistics extraction based on entries in yaml-config"""
        with open(cfg, "r", encoding="utf-8") as stream:
            data = yaml.safe_load(stream)

        if "grid" in data:
            for item in data["grid"]:
                self.get_grid_statistics(data=item, project=project)

        if "wells" in data:
            for item in data["wells"]:
                self.get_well_statistics(data=item, project=project)

        if "blockedwells" in data:
            for item in data["blockedwells"]:
                self.get_bwell_statistics(data=item, project=project)

    def _create_or_return_dataframe(self):
        """
        Combine dataframes from all runs within the instance.
        Only update dataframe if more data have been run within the
        instance, else return previous dataframe.
        """
        dframe = self._dataframe
        dframes = self._dfs

        if dframe.empty or len(dframes) > len(dframe["ID"].unique()):
            QCC.print_debug("Updating combined dataframe")
            self._warn_if_different_property_types()
            dframe = pd.concat(dframes)

            # fill NaN with "Total" for dataframes with missing selectors
            dframe[self._selectors_all] = dframe[self._selectors_all].fillna("Total")

            # Specify column order in statistics dataframe
            cols_first = ["PROPERTY"] + self._selectors_all
            dframe = dframe[
                cols_first + [x for x in dframe.columns if x not in cols_first]
            ]
        return dframe

    def _warn_if_different_property_types(self):
        """Give warning if dataframes have different property types"""
        if not all(ptype == self._proptypes_all[0] for ptype in self._proptypes_all):
            QCC.give_warn(
                "Merging statistics dataframes from different property types "
                "(continous/discrete). Is this intentional?"
            )

    def _adjust_id_if_duplicate(self, run_id: str) -> str:
        """
        Check for equal run ids, modify ids
        by adding a number to get them unique.
        """
        check_id = run_id
        count = 0
        while check_id in self._ids:
            check_id = f"{run_id}({count + 1})"
            count += 1
        return check_id

    def _set_dataframe_id_and_class_attributes(
        self, statistics: PropertyAggregation, source: str, run_id: str
    ):
        """
        Set source and id column of statistics datframe, and different
        class attributes.
        """
        run_id = self._adjust_id_if_duplicate(run_id)
        # set id and source columns in statistics dataframe
        statistics.dataframe["ID"] = run_id
        statistics.dataframe["SOURCE"] = source

        self._ids.append(run_id)
        self._dfs.append(statistics.dataframe)

        for selector in statistics.controls["selectors"]:
            if selector not in self._selectors_all:
                self._selectors_all.append(selector)

        self._proptypes_all.append(statistics.controls["property_type"])

    # pylint: disable = no-self-argument, not-callable
    def _check_multiple_filters(method: Any):
        """Decorator function for extracting statistics with different filters"""

        def wrapper(self, **kwargs):
            if "multiple_filters" in kwargs["data"]:
                for name, filters in kwargs["data"]["multiple_filters"].items():
                    kwargs["data"].update(filters=filters, name=name)
                    method(self, **kwargs)
                return self.dataframe
            return method(self, **kwargs)

        return wrapper

    @_check_multiple_filters
    def _extract_statistics(
        self, dtype: str, data: dict, project: Optional[object], source: str
    ):
        """Create dataframe from properties and extract statistics"""
        QCC.verbosity = data.get("verbosity", 0)
        QCC.print_info("Starting run...")

        # Create Property dataframe from input (using XTGeo)
        property_data = (
            GridProps2df(project=project, data=data, xtgdata=self._xtgdata)
            if dtype == "grid"
            else WellLogs2df(
                project=project,
                data=data,
                xtgdata=self._xtgdata,
                blockedwells=dtype == "bwells",
            )
        )

        # Compute statistics
        stats = PropertyAggregation(property_data)

        self._set_dataframe_id_and_class_attributes(
            stats,
            source=source,
            run_id=data.get("name", source),
        )

        return stats.dataframe

    # QC methods:
    # ==================================================================================

    def get_grid_statistics(
        self,
        data: dict,
        project: Optional[object] = None,
    ) -> pd.DataFrame:
        """Extract property statistics from 3D Grid"""
        return self._extract_statistics(
            dtype="grid",
            data=data,
            project=project,
            source=data.get("source", Path(data["grid"]).stem),
        )

    def get_well_statistics(
        self,
        data: dict,
        project: Optional[object] = None,
    ) -> pd.DataFrame:
        """Extract property statistics from wells"""
        return self._extract_statistics(
            dtype="wells",
            data=data,
            project=project,
            source=data.get("source", "wells"),
        )

    def get_bwell_statistics(
        self,
        data: dict,
        project: Optional[object] = None,
    ) -> pd.DataFrame:
        """Extract property statistics from blocked wells"""
        return self._extract_statistics(
            dtype="bwells",
            data=data,
            project=project,
            source=data.get(
                "source",
                "bwells" if project is None else data["wells"].get("bwname", "BW"),
            ),
        )

    def from_yaml(self, cfg: str, project: Optional[object] = None):
        """Use yaml-configuration file to run the statistics extractions methods"""
        self._initiate_from_config(cfg, project)

    def to_csv(self, csvfile: str):
        """Write combined dataframe to csv"""
        self.dataframe.to_csv(csvfile, index=False)
        QCC.print_info(f"Dataframe with statistics written to {csvfile}")
