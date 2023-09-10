from typing import List, Union, Dict
from enum import Enum
from dataclasses import dataclass, field


class UpscalingQCFiles(Enum):
    WELLS = "well.csv"
    BLOCKEDWELLS = "bw.csv"
    GRID = "grid.csv"
    METADATA = "metadata.json"

    def __fspath__(self):
        return self.value


@dataclass
class WellSource:
    names: List[str] = field(default_factory=list)
    trajectory: str = "Drilled trajectory"
    logrun: str = "log"


@dataclass
class BlockedWellSource:
    grid: str
    bwname: str
    names: List[str] = field(default_factory=list)


@dataclass
class Context:
    properties: Union[List[str], Dict[str, str]]
    selectors: Union[List[str], Dict[str, str]]


@dataclass
class WellContext(Context):
    wells: WellSource = WellSource()

    @classmethod
    def from_dict(cls, data) -> "WellContext":
        wells = data.pop("wells", {})
        return WellContext(wells=WellSource(**wells), **data)


@dataclass
class GridContext(Context):
    grid: str

    @classmethod
    def from_dict(cls, data) -> "GridContext":
        return GridContext(**data)


@dataclass
class BlockedWellContext(Context):
    wells: BlockedWellSource

    @classmethod
    def from_dict(cls, data) -> "BlockedWellContext":
        wells = data.pop("wells", {})
        return BlockedWellContext(wells=BlockedWellSource(**wells), **data)


@dataclass
class MetaData:
    selectors: List[str]
    properties: List[str]
    well_names: List[str]
    trajectory: str
    logrun: str
    grid_name: str
    bw_name: str
