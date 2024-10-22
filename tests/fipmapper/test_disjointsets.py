import pandas as pd
import pytest

from fmu.tools.fipmapper import fipmapper


@pytest.mark.parametrize(
    "mapdata, expected_disjointsets",
    [
        (
            # The first test proves the code on a three-by-three reservoir model
            # which includes the major "cruxes" to be solved. This serves
            # as both the motivation for the code and as demonstration of
            # the solution.
            #
            # In the geomodel, the reservoir is three-by-three
            # with region-zone pairs as follows:
            #
            #    +--------+--------+--------+
            #    | (A, U) | (B, U) | (C, U) |
            #    +--------+--------+--------+
            #    | (A, M) | (B, M) | (C, M) |
            #    +--------+--------+--------+
            #    | (A, L) | (B, L) | (C, L) |
            #    +--------+--------+--------+
            #
            # while in the dynamical (Eclipse) model the reservoir has
            # a FIPNUM split like this:
            #
            #  regs: A    |   B     |    C       zones:
            #     +-----------------+----+----+
            #     |                 |  2 |  3 |    U
            #     |       1         +----+----+
            #     |                 |         |    M
            #     +-----------------+    4    |
            #     |       5         |         |    L
            #     +-----------------+---------+
            #
            # The problem the code solves is to determine which of these cells
            # that must be joined in order to have comparable numbers (when say
            # volume is available for each cell in the geomodel and dynamical
            # model separately.
            #
            # In this case, the joined structure must be a 4-cell partition:
            #
            #     +-----------------+---------+
            #     |                 |    3    |
            #     |       1         +---------+
            #     |                 |         |
            #     +-----------------+    2    |
            #     |       0         |         |
            #     +-----------------+---------+
            #
            # where the code identifies each set of joined cells by a
            # unique integer from a consecutive list starting at zero.
            # The enumeration of sets are predictable, based on lexiographical
            # sorts of REGION, ZONE and FIPNUM.
            {
                # The input is just mappings from the (region, zone)
                # "tuple" in the geomodel into FIPNUM in the dynamical
                # model. The spatial layout of regions, zones and FIPNUM
                # as displayed above does not matter.
                "region2fipnum": {
                    "A": [1, 5],
                    "B": [1, 5],
                    "C": [2, 3, 4],
                },
                "zone2fipnum": {
                    "U": [1, 2, 3],
                    "M": [1, 4],
                    "L": [5, 4],
                },
            },
            pd.DataFrame(
                columns=["REGION", "ZONE", "FIPNUM", "SET"],
                data=[
                    ["A", "L", 5, 0],
                    ["A", "M", 1, 1],
                    ["A", "U", 1, 1],
                    ["B", "L", 5, 0],
                    ["B", "M", 1, 1],
                    ["B", "U", 1, 1],
                    ["C", "L", 4, 2],
                    ["C", "M", 4, 2],
                    ["C", "U", 2, 3],
                    ["C", "U", 3, 3],
                ],
            ),
        ),
        pytest.param({}, [], marks=pytest.mark.xfail(raises=AssertionError)),
        (
            # Only one cell in both regzone partition and fipnum partition:
            {"region2fipnum": {"A": 1}, "zone2fipnum": {"U": 1}},
            [{"REGION": "A", "ZONE": "U", "FIPNUM": 1, "SET": 0}],
        ),
        (
            # Same as above, but test that we can provide it as list input:
            {"region2fipnum": {"A": [1]}, "zone2fipnum": {"U": [1]}},
            [{"REGION": "A", "ZONE": "U", "FIPNUM": 1, "SET": 0}],
        ),
        (
            # Same as above, but with integer regions and zone:
            {"region2fipnum": {1: 1}, "zone2fipnum": {1: 1}},
            [{"REGION": "1", "ZONE": "1", "FIPNUM": 1, "SET": 0}],
        ),
        (
            # FIPNUM split in two, gives only one group in return:
            {"region2fipnum": {"A": [1, 2]}, "zone2fipnum": {"U": [1, 2]}},
            [
                {"REGION": "A", "ZONE": "U", "FIPNUM": 1, "SET": 0},
                {"REGION": "A", "ZONE": "U", "FIPNUM": 2, "SET": 0},
            ],
        ),
        (
            # FIPNUM split in two, and two zones, gives two groups in return:
            {"region2fipnum": {"A": [1, 2]}, "zone2fipnum": {"U": [1], "L": [2]}},
            [
                {"REGION": "A", "ZONE": "L", "FIPNUM": 2, "SET": 0},
                {"REGION": "A", "ZONE": "U", "FIPNUM": 1, "SET": 1},
            ],
        ),
        (
            # Two zones, one FIPNUM, gives one group in return:
            {"region2fipnum": {"A": 1}, "zone2fipnum": {"U": [1], "L": [1]}},
            [
                {"REGION": "A", "ZONE": "L", "FIPNUM": 1, "SET": 0},
                {"REGION": "A", "ZONE": "U", "FIPNUM": 1, "SET": 0},
            ],
        ),
        (
            # Two regions, one FIPNUM, gives one group in return:
            {"region2fipnum": {"A": 1, "B": 1}, "zone2fipnum": {"U": 1}},
            [
                {"REGION": "A", "ZONE": "U", "FIPNUM": 1, "SET": 0},
                {"REGION": "B", "ZONE": "U", "FIPNUM": 1, "SET": 0},
            ],
        ),
        (
            # Two regions, two zones, 4 FIPNUMs -> 4 groups:
            {
                "region2fipnum": {"A": [2, 1], "B": [3, 4]},
                "zone2fipnum": {"U": [1, 3], "L": [2, 4]},
            },
            [
                {"REGION": "A", "ZONE": "L", "FIPNUM": 2, "SET": 0},
                {"REGION": "A", "ZONE": "U", "FIPNUM": 1, "SET": 1},
                {"REGION": "B", "ZONE": "L", "FIPNUM": 4, "SET": 2},
                {"REGION": "B", "ZONE": "U", "FIPNUM": 3, "SET": 3},
            ],
        ),
        (
            # Two regions, two zones, 2 horizontal FIPNUMs -> 2 groups:
            {
                "region2fipnum": {"A": [2, 1], "B": [1, 2]},
                "zone2fipnum": {"U": 1, "L": [2, 2]},  # Double for L is ignored.
            },
            [
                {"REGION": "A", "ZONE": "L", "FIPNUM": 2, "SET": 0},
                {"REGION": "A", "ZONE": "U", "FIPNUM": 1, "SET": 1},
                {"REGION": "B", "ZONE": "L", "FIPNUM": 2, "SET": 0},
                {"REGION": "B", "ZONE": "U", "FIPNUM": 1, "SET": 1},
            ],
        ),
        (
            # Two regions, two zones, 2 region-wise FIPNUMs -> 2 groups:
            {
                "region2fipnum": {"A": 1, "B": 2},
                "zone2fipnum": {"U": [1, 2], "L": [1, 2]},
            },
            [
                {"REGION": "A", "ZONE": "L", "FIPNUM": 1, "SET": 0},
                {"REGION": "A", "ZONE": "U", "FIPNUM": 1, "SET": 0},
                {"REGION": "B", "ZONE": "L", "FIPNUM": 2, "SET": 1},
                {"REGION": "B", "ZONE": "U", "FIPNUM": 2, "SET": 1},
            ],
        ),
        (
            # Two regions, one zone, 2 horizontal FIPNUMs which don't align
            # with the region boundary -> 1 group:
            {
                "region2fipnum": {"A": [1], "B": [1, 2]},
                "zone2fipnum": {"U": [1, 2]},
            },
            [
                {"REGION": "A", "ZONE": "U", "FIPNUM": 1, "SET": 0},
                {"REGION": "B", "ZONE": "U", "FIPNUM": 1, "SET": 0},
                {"REGION": "B", "ZONE": "U", "FIPNUM": 2, "SET": 0},
            ],
        ),
        (
            # Integer datatypes for regions and zones, always
            # strings in returned dataframe, even though
            # FipMapper handles the integers as ints internally
            {
                "region2fipnum": {1: 1, 2: 2},
                "zone2fipnum": {1: [1, 2], 2: [1, 2]},
            },
            [
                {"REGION": "1", "ZONE": "1", "FIPNUM": 1, "SET": 0},
                {"REGION": "1", "ZONE": "2", "FIPNUM": 1, "SET": 0},
                {"REGION": "2", "ZONE": "1", "FIPNUM": 2, "SET": 1},
                {"REGION": "2", "ZONE": "2", "FIPNUM": 2, "SET": 1},
            ],
        ),
        (
            # Mixed datatype int/str for regions and zones
            {
                "region2fipnum": {1: 1, "B": 2},
                "zone2fipnum": {"U": [1, 2], 2: [1, 2]},
            },
            [
                {"REGION": "1", "ZONE": "2", "FIPNUM": 1, "SET": 0},
                {"REGION": "1", "ZONE": "U", "FIPNUM": 1, "SET": 0},
                {"REGION": "B", "ZONE": "2", "FIPNUM": 2, "SET": 1},
                {"REGION": "B", "ZONE": "U", "FIPNUM": 2, "SET": 1},
            ],
        ),
    ],
)
def test_disjointsets(mapdata, expected_disjointsets):
    expected_dframe = pd.DataFrame(expected_disjointsets)
    cols = list(expected_dframe.columns)
    mapper = fipmapper.FipMapper(mapdata=mapdata)
    pd.testing.assert_frame_equal(
        mapper.disjoint_sets()[cols].sort_values(by=cols, axis=0),
        expected_dframe.sort_values(by=cols, axis=0),
    )


@pytest.mark.parametrize(
    "dframe_records, expected_regions, expected_zones, "
    "expected_fipnums, expected_regzonefips",
    [
        ([{}], {}, {}, {}, {}),
        (
            [{"REGION": "A", "ZONE": "U", "FIPNUM": 1, "SET": 0}],
            {0: ["A"]},
            {0: ["U"]},
            {0: [1]},
            {0: [("A", "U", 1)]},
        ),
        (
            [
                {"REGION": "A", "ZONE": "U", "FIPNUM": 1, "SET": 0},
                {"REGION": "B", "ZONE": "U", "FIPNUM": 1, "SET": 0},
            ],
            {0: ["A", "B"]},
            {0: ["U"]},
            {0: [1]},
            {0: [("A", "U", 1), ("B", "U", 1)]},
        ),
        (
            [
                # Switched order of rows compared to above:
                {"REGION": "B", "ZONE": "U", "FIPNUM": 1, "SET": 0},
                {"REGION": "A", "ZONE": "U", "FIPNUM": 1, "SET": 0},
            ],
            {0: ["A", "B"]},
            {0: ["U"]},
            {0: [1]},
            {0: [("A", "U", 1), ("B", "U", 1)]},
        ),
        (
            [
                {"REGION": "A", "ZONE": "U", "FIPNUM": 1, "SET": 0},
                {"REGION": "B", "ZONE": "U", "FIPNUM": 2, "SET": 1},
            ],
            {0: ["A"], 1: ["B"]},
            {0: ["U"], 1: ["U"]},
            {0: [1], 1: [2]},
            {0: [("A", "U", 1)], 1: [("B", "U", 2)]},
        ),
        (
            # The full example from the top of this file:
            pd.DataFrame(
                columns=["REGION", "ZONE", "FIPNUM", "SET"],
                data=[
                    ["A", "L", 5, 0],
                    ["A", "M", 1, 1],
                    ["A", "U", 1, 1],
                    ["B", "L", 5, 0],
                    ["B", "M", 1, 1],
                    ["B", "U", 1, 1],
                    ["C", "L", 4, 2],
                    ["C", "M", 4, 2],
                    ["C", "U", 2, 3],
                    ["C", "U", 3, 3],
                ],
            ).to_dict(orient="records"),
            {0: ["A", "B"], 1: ["A", "B"], 2: ["C"], 3: ["C"]},
            {0: ["L"], 1: ["M", "U"], 2: ["L", "M"], 3: ["U"]},
            {0: [5], 1: [1], 2: [4], 3: [2, 3]},
            {
                0: [("A", "L", 5), ("B", "L", 5)],
                1: [("A", "M", 1), ("A", "U", 1), ("B", "M", 1), ("B", "U", 1)],
                2: [("C", "L", 4), ("C", "M", 4)],
                3: [("C", "U", 2), ("C", "U", 3)],
            },
        ),
    ],
)
def test_set_lookups(
    dframe_records,
    expected_regions,
    expected_zones,
    expected_fipnums,
    expected_regzonefips,
):
    dframe = pd.DataFrame(dframe_records)
    assert fipmapper.regions_in_set(dframe) == expected_regions
    assert fipmapper.zones_in_set(dframe) == expected_zones
    assert fipmapper.fipnums_in_set(dframe) == expected_fipnums
    assert fipmapper.regzonefips_in_set(dframe) == expected_regzonefips
