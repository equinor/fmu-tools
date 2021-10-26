from pathlib import Path
from typing import List, Union, Dict, Set
from dataclasses import asdict
import json

import pandas as pd
from fmu.tools.qcproperties._grid2df import GridProps2df
from fmu.tools.qcproperties._well2df import WellLogs2df
from fmu.tools.qcdata import QCData

from fmu.tools.rms.upscaling_qc._types import (
    WellContext,
    GridContext,
    BlockedWellContext,
    UpscalingQCFiles,
    MetaData,
)


class RMSUpscalingQC:
    def __init__(
        self, project, well_data: dict, grid_data: dict, bw_data: dict
    ) -> None:
        self._project = project
        self._well_data = WellContext.from_dict(well_data)
        self._grid_data = GridContext.from_dict(grid_data)
        self._bw_data = BlockedWellContext.from_dict(bw_data)
        self._validate_grid_name()
        self._validate_properties()
        self._validate_selectors()
        self._set_well_names()

    def _set_well_names(self) -> None:
        self._well_data.wells.names = self.well_names
        self._bw_data.wells.names = self.well_names

    def _validate_grid_name(self) -> None:
        if self._grid_data.grid != self._bw_data.wells.grid:
            raise ValueError("Different grids given for blocked well and grid.")

    def _validate_properties(self) -> None:
        if (
            not self._to_set(self._well_data.properties)
            == self._to_set(self._bw_data.properties)
            == self._to_set(self._grid_data.properties)
        ):
            raise ValueError("Data sources do not have the same properties!")

    def _validate_selectors(self) -> None:
        if (
            not self._to_set(self._well_data.selectors)
            == self._to_set(self._bw_data.selectors)
            == self._to_set(self._grid_data.selectors)
        ):
            raise ValueError("Data sources do not have the same selectors!")

    @staticmethod
    def _to_set(values: Union[List, Dict]) -> Set[str]:
        if isinstance(values, list):
            return set(values)
        return set(list(values.keys()))

    @property
    def _selectors(self) -> List[str]:
        if isinstance(self._well_data.selectors, list):
            return self._well_data.selectors
        return list(self._well_data.selectors.keys())

    @property
    def _properties(self) -> List[str]:
        if isinstance(self._well_data.properties, list):
            return self._well_data.properties
        return list(self._well_data.properties.keys())

    @property
    def _grid_name(self) -> str:
        return self._grid_data.grid

    @property
    def _metadata(self) -> MetaData:
        return MetaData(
            selectors=self._selectors,
            properties=self._properties,
            well_names=self.well_names,
            trajectory=self._well_data.wells.trajectory,
            logrun=self._well_data.wells.logrun,
            grid_name=self._grid_data.grid,
            bw_name=self._bw_data.wells.bwname,
        )

    @property
    def well_names(self) -> List[str]:
        try:
            grid = self._project.grid_models[self._grid_data.grid]
            return grid.blocked_wells_set[self._bw_data.wells.bwname].get_well_names()
        except ValueError:
            return []

    def _get_well_data(self) -> pd.DataFrame:
        _ = WellLogs2df(
            project=self._project, data=asdict(self._well_data), xtgdata=QCData()
        )
        return _.dataframe

    def _get_bw_data(self) -> pd.DataFrame:
        _ = WellLogs2df(
            project=self._project,
            data=asdict(self._bw_data),
            xtgdata=QCData(),
            blockedwells=True,
        )
        return _.dataframe

    def _get_grid_data(self) -> pd.DataFrame:
        _ = GridProps2df(
            project=self._project, data=asdict(self._grid_data), xtgdata=QCData()
        )
        return _.dataframe

    def get_statistics(self) -> pd.DataFrame:
        for _, df in self._get_well_data().groupby("ZONE"):
            print(df)

    def to_disk(self, path: str = "../../share/results/tables/upscaling_qc") -> None:
        folder = Path(path)

        if not folder.parent.is_dir():
            print(f"Cannot create folder. Ensure that {folder.parent} exists.")
        folder.mkdir(exist_ok=True)
        print("Extracting data...")
        self._get_well_data().to_csv(folder / UpscalingQCFiles.WELLS, index=False)
        self._get_bw_data().to_csv(folder / UpscalingQCFiles.BLOCKEDWELLS, index=False)
        self._get_grid_data().to_csv(folder / UpscalingQCFiles.GRID, index=False)
        with open(folder / UpscalingQCFiles.METADATA, "w") as fp:
            json.dump(asdict(self._metadata), fp, indent=4)
        print(f"Done. Output written to {folder}.")
