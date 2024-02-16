"""The FipMapper class, mapping region/zones in RMS to FIPxxx in Eclipse."""

import collections
import contextlib
import itertools
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import pandas as pd
import yaml
from disjoint_set import DisjointSet

logger = logging.getLogger(__name__)


class FipMapper:
    def __init__(
        self,
        *,
        yamlfile: Optional[Union[str, Path]] = None,
        mapdata: Optional[Dict[str, str]] = None,
        skipstring: Optional[Union[List[str], str]] = None,
    ):
        """Represent mappings between region/zones to FIPxxx.

        FipMapper is a class to represent a to map between
        regions/zones in the geomodel (RMS) and to different region partitions
        in the dynamic model (Eclipse).

        Primary usage is to determine which RMS regions corresponds to
        which FIPNUMs, similarly for zones, and in both directions.

        Configuration is via a yaml-file or directly with a dictionary. The
        map can be configured in any direction.

        Several data structures in the dictionary can be used, such that
        the needed information can be extracted from the global configurations
        file.

        Assumptions:
            * A FIPNUM always maps to an arbitrary-length list of regions
            * A FIPNUM always maps to an arbitrary-length list of zones
            * A region always maps to an arbitrary-length list of FIPNUMs
            * A zone always maps to an arbitrary-length list of FIPNUMs
            * A region is assumed to be present for all zones, but not
              relevant in this class
            * A zone is assumed to be present for all regions, but not
              relevant in this class

        For FIPNUM, the datatype must be integers, but can be initialized
        from strings as long as they can be parsed as strings.

        For Region and Zone, a string datatype is assumed, but the yaml
        input is allowed to be integers or integers and strings mixed. Some
        functions will return these as integers if they were inputted as such,
        but at least the disjoint_sets() function will always return
        these as strings.

        Args:
            yamlfile: Filename
            mapdata: direct dictionary input. Provide only one of the
                arguments, not both.
            skipstring: List of strings which will be ignored (e.g. ["Totals"]).
        """
        self._mapdata: Dict[str, dict] = {}  # To be filled with data we need.

        if skipstring is None:
            self.skipstring = []
        if isinstance(skipstring, str):
            self.skipstring = [skipstring]

        if yamlfile is not None and mapdata is not None:
            raise ValueError(
                "Initialize with either yamlfile or explicit data, not both"
            )
        if yamlfile is None and mapdata is None:
            logger.warning("FipMapper initialized with no data")

        if yamlfile is not None:
            logger.info("Loading data from %s", yamlfile)
            with open(yamlfile, encoding="utf-8") as stream:
                yamldata = yaml.safe_load(stream)
            logger.debug(str(yamldata))
        else:
            yamldata = mapdata

        if yamldata is not None:
            self._get_explicit_mapdata(yamldata)

        if yamldata is not None and "global" in yamldata:
            # This is a fmu-config file.
            self._fipdata_from_fmuconfigyaml(yamldata)

        # Webviz YML format:
        if yamldata is not None and "FIPNUM" in yamldata:
            self._fipdata_from_webvizyaml(yamldata)

        assert isinstance(self._mapdata, dict), "FipMapper needs a dictionary"

        # Determine our capabilities:
        self.has_fip2region = "fipnum2region" in self._mapdata
        self.has_fip2zone = "fipnum2zone" in self._mapdata
        self.has_region2fip = "region2fipnum" in self._mapdata
        self.has_zone2fip = "zone2fipnum" in self._mapdata

        # Validate that all FIPNUMs are integers:
        try:
            [int(fip) for fip in self.get_fipnums()]
        except AssertionError:
            # This is for partially empty fipmappers.
            pass
        except ValueError:
            raise TypeError(f"All FIPNUMs must be integers, got {self.get_fipnums}")

    def _get_explicit_mapdata(self, yamldata: Dict[str, Any]):
        """Fetch explicit mapping configuration from a dictionary.

        Set internal flags when maps are found

        Invert maps when possible/needed

        Args:
            yamldata (dict): Configuration object with predefined items
                at the first level.
        """
        if self._mapdata is None:
            self._mapdata = {}
        if "fipnum2region" in yamldata:
            self._mapdata["fipnum2region"] = yamldata["fipnum2region"]
            if "region2fipnum" not in yamldata:
                self._mapdata["region2fipnum"] = invert_map(
                    self._mapdata["fipnum2region"], skipstring=self.skipstring
                )
            self.has_fip2region = True
            self.has_region2fip = True

        if "region2fipnum" in yamldata:
            self._mapdata["region2fipnum"] = yamldata["region2fipnum"]
            if "fipnum2region" not in yamldata:
                logger.debug(self._mapdata["region2fipnum"])
                self._mapdata["fipnum2region"] = invert_map(
                    self._mapdata["region2fipnum"], skipstring=self.skipstring
                )
            self.has_fip2region = True
            self.has_region2fip = True

        if "fipnum2zone" in yamldata:
            self._mapdata["fipnum2zone"] = yamldata["fipnum2zone"]
            if "zone2fipnum" not in yamldata:
                self._mapdata["zone2fipnum"] = invert_map(
                    self._mapdata["fipnum2zone"], skipstring=self.skipstring
                )
            self.has_fip2zone = True
            self.has_zone2fip = True

        if "zone2fipnum" in yamldata:
            self._mapdata["zone2fipnum"] = yamldata["zone2fipnum"]
            if "fip2zone" not in yamldata:
                self._mapdata["fipnum2zone"] = invert_map(
                    self._mapdata["zone2fipnum"], skipstring=self.skipstring
                )
            self.has_fip2zone = True
            self.has_zone2fip = True

    def _fipdata_from_fmuconfigyaml(self, yamldict: dict):
        """This function should be able to build mapping from region/zones to
        FIPNUM based on data it finds in a fmu-config global_master_config.yml
        file.

        How that map should be deduced is not yet defined, and we only support
        having the explicit maps "region2fipnum" etc under the global section

        Args:
            yamldict (dict):
        """
        self._get_explicit_mapdata(yamldict["global"])

    def _fipdata_from_webvizyaml(self, yamldict: dict):
        """This function loads the Webviz yaml syntax for
        REGION/ZONE to FIPNUM mapping,

        The syntax is defined in
        https://github.com/equinor/webviz-subsurface/blob/master/webviz_subsurface/plugins/_reservoir_simulation_timeseries_regional.py#L1422

        Args:
            yamldict (dict):
        """
        self._get_explicit_mapdata(webviz_to_prtvol2csv(yamldict))

    def _fips2regions(self, fips: List[int]) -> List[List[str]]:
        return [self.fip2region(fip_int) for fip_int in fips]

    def get_regions(self) -> List[str]:
        """Obtain a sorted list of the regions that exist in the map"""
        assert "region2fipnum" in self._mapdata, "No data provided for regions"
        try:
            return sorted(self._mapdata["region2fipnum"].keys())
        except TypeError:
            # We get here if some regions are ints and others are strings
            return sorted(map(str, self._mapdata["region2fipnum"].keys()))

    def get_zones(self) -> List[str]:
        """Obtain a sorted list of the zones that exist in the map"""
        assert "zone2fipnum" in self._mapdata, "No data provided for regions"
        try:
            return sorted(self._mapdata["zone2fipnum"].keys())
        except TypeError:
            # We get here if some zones are ints and others are strings
            return sorted(map(str, self._mapdata["zone2fipnum"].keys()))

    def get_fipnums(self) -> List[str]:
        """Obtain a sorted list of the fip numbers that exist in the map"""
        assert "fipnum2region" in self._mapdata, "No data provided for regions"
        return sorted(self._mapdata["fipnum2region"].keys())

    def fip2region(self, fip: int) -> List[str]:
        """Maps one FIP(NUM) integer to list of Region strings. Each FIPNUM
        can map to multiple regions, therefore a list is always returned for
        each FIPNUM.

        Args:
            array: List/array of FIPNUMS, or integer.

        Returns:
            List of strings or list of lists of strings, depending on input.
            Region names that are "integers" will be returned as strings.
            Empty list if no region is known for a specific FIPNUM.
        """
        assert "fipnum2region" in self._mapdata, "No data provided for fip2region"
        try:
            regions = self._mapdata["fipnum2region"][fip]
            if not isinstance(regions, list):
                # Single region in input
                return [regions]
            return regions
        except KeyError:
            logger.warning(
                "Unknown fip %s, known map is %s",
                str(fip),
                str(self._mapdata["fipnum2region"]),
            )
            return []

    def _regions2fips(self, regions: List[str]) -> List[List[int]]:
        return [self.region2fip(region) for region in regions]

    def region2fip(self, region: Union[int, str]) -> List[int]:
        """Maps a Region string/int to FIPNUM(s).

        Args:
            region: Region

        Returns:
            FIPNUM values. None if the region is unknown, many if many FIPNUMs
            are present in the region.
        """
        assert "region2fipnum" in self._mapdata, "No data provided for region2fip"
        if region not in self._mapdata["region2fipnum"]:
            with contextlib.suppress(ValueError):
                # If regions have mixed types in yaml, we are sometimes
                # asked for a region as a stringified integer
                region = int(region)
        try:
            fips = self._mapdata["region2fipnum"][region]
            if not isinstance(fips, list):
                # Single FIPNUM in input
                return [int(fips)]
            return [int(fip) for fip in fips]
        except KeyError:
            logger.warning(
                "Unknown region %s, known map is %s",
                str(region),
                str(self._mapdata["region2fipnum"]),
            )
            return []

    def zone2fip(self, zone: Union[str, int]) -> List[int]:
        """Maps a zone to FIPNUMs"""
        assert "zone2fipnum" in self._mapdata, "No data provided for zone2fip"
        if zone not in self._mapdata["zone2fipnum"]:
            with contextlib.suppress(ValueError):
                # If zones have mixed types in yaml, we are sometimes
                # asked for a zone as a stringified integer
                zone = int(zone)
        try:
            fips = self._mapdata["zone2fipnum"][zone]
            if not isinstance(fips, list):
                # Single FIPNUM in input
                return [int(fips)]
            return [int(fip) for fip in fips]
        except KeyError:
            logger.warning(
                "Unknown zone %s, known map is %s",
                str(zone),
                str(self._mapdata["zone2fipnum"]),
            )
            return []

    def _fips2zones(self, fips: List[int]) -> List[List[str]]:
        return [self.fip2zone(fip) for fip in fips]

    def fip2zone(self, fip: int) -> List[str]:
        """Maps a FIPNUM integer to an list of Zone strings

        Args:
            array (list): List/array of FIPNUMS, or integer.

        Returns:
            list: Region strings. Always returned as list, and always as
            strings, even if zone "names" are integers. Empty list if no
            zone is assigned to the FIPNUM.
        """
        assert "fipnum2zone" in self._mapdata, "No data provided for fip2zone"
        try:
            zones = self._mapdata["fipnum2zone"][fip]
            if not isinstance(zones, list):
                # Single zone for this FIPNUM
                return [zones]
            return zones
        except KeyError:
            logger.warning("The zone belonging to FIPNUM %s is unknown", str(fip))
            return []  # type: ignore

    def regzone2fip(self, region: str, zone: str) -> List[int]:
        fipreg = self.region2fip(region)
        fipzon = self.zone2fip(zone)
        return sorted(set(fipreg).intersection(set(fipzon)))

    def disjoint_sets(self) -> pd.DataFrame:
        """Determine the minimal disjoint sets of a reservoir

        The disjoint sets returned consist of sets that can be split into
        both a set of FIPxxxx list and a region/zone list. Thus, the sum of
        any additive property is comparable on these disjoint sets.

        The returned object is a dataframe that is to be used to group together
        fipnums or regions/zones so they are summable.

        Note that the REGION and ZONE columns always contain strings only, while
        FIPNUM is always an integer.

        Each row represents a cell in the partition where both region, zone and
        fipnum boundaries apply, this the finest possible partition the
        fipmapper data allows. Each row is then assigned to a integer
        identifier in the ``SET`` column. The chosen integers values for each
        set is based on lexiographical sorting of regions, zones and fipnum
        values.

        These sets signifies the minimal grouping of data that must be applied
        in order for volumes in the region/zone partition or fipnum partition
        to be comparable.
        """

        # Generate all possible combinations of the regions and
        # zones we know of:
        regzone_df = pd.DataFrame(
            columns=["REGION", "ZONE"],
            data=itertools.product(self.get_regions(), self.get_zones()),
        )

        # Map all of the region-zone combinations into the accompanying FIPNUMs:
        regzone_df["FIPNUMS"] = regzone_df.apply(
            lambda x: self.regzone2fip(x["REGION"], x["ZONE"]), axis=1
        )

        # The dataframe has lists in the FIPNUMS column when a reg/zone maps
        # to multiple FIPNUMs. Unroll these into one row pr linked FIPNUM:
        dframe = _expand_regzone_df(regzone_df)

        # The `dframe` now has one row pr. smallest "cell" that is interesting
        # in the current context. In some sense, the "intersection" of all
        # possible partitions.

        # Create a dataframe of all possible combinations of these smallest cells:
        edges = pd.merge(
            dframe.assign(dummy=1), dframe.assign(dummy=1), on="dummy"
        ).drop("dummy", axis=1)
        # When Pandas 1.2 is ubiqutous, replace the above statement with:
        # edges = dframe.merge(dframe, how="cross")

        # A partition is equivalent to an equivalence relation.

        # Apply an equivalence relation to the cell combinations:
        edges["NEIGHBOURS"] = edges.apply(
            lambda x: _equivalent_cells(
                x["REGION_x"],
                x["ZONE_x"],
                x["FIPNUM_x"],
                x["REGION_y"],
                x["ZONE_y"],
                x["FIPNUM_y"],
            ),
            axis=1,
        )
        # Filter to only edges that determine which cell linkages
        # that should be grouped:
        neighbourlist = edges[edges["NEIGHBOURS"]]

        # Construct a disjoint set object of all the smallest cells that are
        # to be grouped/unionized:
        ds: DisjointSet = DisjointSet()
        for _, row in dframe.iterrows():
            ds.find((row["REGION"], row["ZONE"], row["FIPNUM"]))

        # Apply the union-find algorithm to determine the partition
        # where all equivalene relations are obeyed:
        for _, pair in neighbourlist.iterrows():
            ds.union(
                (pair["REGION_x"], pair["ZONE_x"], pair["FIPNUM_x"]),
                (pair["REGION_y"], pair["ZONE_y"], pair["FIPNUM_y"]),
            )

        # The union-find algorithm has now "named" each of the components
        # in the disjoint set by a somewhat random mother/root node. This root
        # not is not any more a root compared to the other cells in the set,
        # so each set is instead mapped to consecutive integers.
        id_dict: dict = collections.defaultdict(lambda: len(id_dict))
        dframe["SET"] = [
            id_dict[root]
            for root in dframe.sort_values(["REGION", "ZONE", "FIPNUM"]).apply(
                lambda x: ds.find((x["REGION"], x["ZONE"], x["FIPNUM"])), axis=1
            )
        ]
        dframe["REGION"] = dframe["REGION"].astype(str)
        dframe["ZONE"] = dframe["ZONE"].astype(str)
        dframe["FIPNUM"] = dframe["FIPNUM"].astype(int)
        return dframe


def _equivalent_cells(
    reg1: Any, zon1: Any, fip1: Any, reg2: Any, zon2: Any, fip2: Any
) -> bool:
    """Define the equivalence relation for the reg-zone-fip reservoir partition

    A pair of reg-zone-fip is in the same group if they must be treated together
    when (and have properties summed). Say if you have a value for
    a specific region, but this region contains two FIPNUMs. Then we can never
    treat these two FIPNUMs separately, they must be summed in order to be
    comparable to the value for the region
    """
    return ((reg1 == reg2) and (zon1 == zon2)) or (fip1 == fip2)


def regions_in_set(dframe: pd.DataFrame) -> Dict[int, List[str]]:
    """From the dataframe returned by disjoint_sets(), compute
    a dictionary to map from a set index to a list of regions
    that are members of that set index

    Args:
        dframe: The dataframe emitted by disjoint_sets()
    """
    if dframe.empty:
        return {}
    return (
        dframe.groupby("SET")["REGION"].apply(set).apply(list).apply(sorted).to_dict()
    )


def zones_in_set(dframe: pd.DataFrame) -> Dict[int, List[str]]:
    """From the dataframe returned by disjoint_sets(), compute
    a dictionary to map from a set index to a list of zones
    that are members of that set index

    Args:
        dframe: The dataframe emitted by disjoint_sets()
    """
    if dframe.empty:
        return {}
    return dframe.groupby("SET")["ZONE"].apply(set).apply(list).apply(sorted).to_dict()


def fipnums_in_set(dframe: pd.DataFrame) -> Dict[int, List[int]]:
    """From the dataframe returned by disjoint_sets(), compute
    a dictionary to map from a set index to a list of FIPNUM values
    that are members of that set index

    Args:
        dframe: The dataframe emitted by disjoint_sets()
    """
    if dframe.empty:
        return {}
    return (
        dframe.groupby("SET")["FIPNUM"].apply(set).apply(list).apply(sorted).to_dict()
    )


def regzonefips_in_set(dframe: pd.DataFrame) -> Dict[int, List[Tuple[str, str, int]]]:
    """From the dataframe returned by disjoint_sets(), compute
    a dictionary to map from a set index to a list of tuples
    of the region, zones and fipnums in the set.

    Args:
        dframe: The dataframe emitted by disjoint_sets()
    """
    if dframe.empty:
        return {}
    dframe = dframe.copy()
    dframe["reg-zone-fip"] = dframe[["REGION", "ZONE", "FIPNUM"]].apply(tuple, axis=1)
    return (
        dframe.groupby("SET")["reg-zone-fip"]
        .apply(set)
        .apply(list)
        .apply(sorted)
        .to_dict()
    )


def webviz_to_prtvol2csv(webvizdict: dict):
    """Convert a dict representation of a region/zone map in the Webviz format
    to the prtvol2csv format"""
    if "FIPNUM" in webvizdict and isinstance(webvizdict["FIPNUM"], dict):
        prtvoldict = {}
        if "groups" in webvizdict["FIPNUM"]:
            if "REGION" in webvizdict["FIPNUM"]["groups"]:
                prtvoldict["region2fipnum"] = webvizdict["FIPNUM"]["groups"]["REGION"]
            if "ZONE" in webvizdict["FIPNUM"]["groups"]:
                prtvoldict["zone2fipnum"] = webvizdict["FIPNUM"]["groups"]["ZONE"]
        else:
            # The "groups" level might go away:
            if "REGION" in webvizdict["FIPNUM"]:
                prtvoldict["region2fipnum"] = webvizdict["FIPNUM"]["REGION"]
            if "ZONE" in webvizdict["FIPNUM"]:
                prtvoldict["zone2fipnum"] = webvizdict["FIPNUM"]["ZONE"]
        return prtvoldict
    return {}


def invert_map(
    dictmap: Dict[str, Any], skipstring: Optional[Union[list, str]] = None
) -> Dict[str, List[Any]]:
    """Invert a dictionary, supporting many-to-many maps.

    Args:
        dictmap
        skipstring: List of strings which will be ignored (e.g. "Totals").
    """
    if skipstring is None:
        skipstring = []
    if isinstance(skipstring, str):
        skipstring = [skipstring]

    inv_map: Dict[str, List[Any]] = {}
    for key, value in dictmap.items():
        if key in skipstring or value in skipstring:
            continue
        if isinstance(value, list):
            for _value in value:
                inv_map[_value] = list(set(inv_map.get(_value, set())).union({key}))
        else:
            base = set(inv_map.get(value, set()))
            # mypy workaround: https://github.com/python/mypy/issues/2013
            inv_map[value] = list(base.union({key}))

    for key, value in inv_map.items():
        try:
            inv_map[key] = sorted(inv_map[key])
        except TypeError:
            # Datatype of keys are mixed, typically int and str.
            inv_map[key] = sorted(map(str, list(inv_map[key])))

    return inv_map


def _expand_regzone_df(dframe: pd.DataFrame, fipname: str = "FIPNUM") -> pd.DataFrame:
    """Unroll dataframe rows with a FIPNUM list in the "FIPNUMS" column"""
    new_rows = []
    for _, row in dframe.iterrows():
        for fipnumber in row[fipname + "S"]:
            new_rows.append(
                {
                    "REGION": row["REGION"],
                    "ZONE": row["ZONE"],
                    fipname: fipnumber,
                    "REGZONE": str(row["REGION"]) + "-" + str(row["ZONE"]),
                }
            )
    return pd.DataFrame(new_rows)
