from packaging import version

import pytest

from fmu.tools.fipmapper import fipmapper

import pandas as pd


@pytest.mark.skipif(
    version.parse(pd.__version__) < version.parse("0.25.2"),
    reason="Pandas 0.25.2 is required for fipmappers disjointsets()",
)
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
            #     +-----------------+----+----+
            #     |                 |    c    |
            #     |       a         +----+----+
            #     |                 |         |
            #     +-----------------+    d    |
            #     |       b         |         |
            #     +-----------------+---------+
            #
            # where the code identifies the joined cell by its "root", which
            # is a triplet (assume arbitrary choice) identifying one of
            # the components.
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
                columns=["REGION", "ZONE", "FIPNUM", "ROOT"],
                data=[
                    ["A", "L", 5, ("B", "L", 5)],  # b
                    ["A", "M", 1, ("B", "U", 1)],  # a
                    ["A", "U", 1, ("B", "U", 1)],  # a
                    ["B", "L", 5, ("B", "L", 5)],  # b
                    ["B", "M", 1, ("B", "U", 1)],  # a
                    ["B", "U", 1, ("B", "U", 1)],  # a
                    ["C", "L", 4, ("C", "M", 4)],  # d
                    ["C", "M", 4, ("C", "M", 4)],  # d
                    ["C", "U", 2, ("C", "U", 3)],  # c
                    ["C", "U", 3, ("C", "U", 3)],  # c
                    # (4 unique ROOTs)
                ],
            ),
        ),
        pytest.param({}, [], marks=pytest.mark.xfail(raises=AssertionError)),
        (
            # Only one cell in both regzone partition and fipnum partition:
            {"region2fipnum": {"A": 1}, "zone2fipnum": {"U": 1}},
            [{"REGION": "A", "ZONE": "U", "FIPNUM": 1, "ROOT": ("A", "U", 1)}],
        ),
        (
            # Same as above, but test that we can provide it as list input:
            {"region2fipnum": {"A": [1]}, "zone2fipnum": {"U": [1]}},
            [{"REGION": "A", "ZONE": "U", "FIPNUM": 1, "ROOT": ("A", "U", 1)}],
        ),
        (
            # FIPNUM split in two, gives only one group in return:
            {"region2fipnum": {"A": [1, 2]}, "zone2fipnum": {"U": [1, 2]}},
            [
                {"REGION": "A", "ZONE": "U", "FIPNUM": 1, "ROOT": ("A", "U", 2)},
                {"REGION": "A", "ZONE": "U", "FIPNUM": 2, "ROOT": ("A", "U", 2)},
            ],
        ),
        (
            # FIPNUM split in two, and two zones, gives two groups in return:
            {"region2fipnum": {"A": [1, 2]}, "zone2fipnum": {"U": [1], "L": [2]}},
            [
                {"REGION": "A", "ZONE": "L", "FIPNUM": 2, "ROOT": ("A", "L", 2)},
                {"REGION": "A", "ZONE": "U", "FIPNUM": 1, "ROOT": ("A", "U", 1)},
            ],
        ),
        (
            # Two zones, one FIPNUM, gives one group in return:
            {"region2fipnum": {"A": 1}, "zone2fipnum": {"U": [1], "L": [1]}},
            [
                {"REGION": "A", "ZONE": "L", "FIPNUM": 1, "ROOT": ("A", "U", 1)},
                {"REGION": "A", "ZONE": "U", "FIPNUM": 1, "ROOT": ("A", "U", 1)},
            ],
        ),
        (
            # Two regions, one FIPNUM, gives one group in return:
            {"region2fipnum": {"A": 1, "B": 1}, "zone2fipnum": {"U": 1}},
            [
                {"REGION": "A", "ZONE": "U", "FIPNUM": 1, "ROOT": ("B", "U", 1)},
                {"REGION": "B", "ZONE": "U", "FIPNUM": 1, "ROOT": ("B", "U", 1)},
            ],
        ),
        (
            # Two regions, two zones, 4 FIPNUMs -> 4 groups:
            {
                "region2fipnum": {"A": [2, 1], "B": [3, 4]},
                "zone2fipnum": {"U": [1, 3], "L": [2, 4]},
            },
            [
                {"REGION": "A", "ZONE": "L", "FIPNUM": 2, "ROOT": ("A", "L", 2)},
                {"REGION": "A", "ZONE": "U", "FIPNUM": 1, "ROOT": ("A", "U", 1)},
                {"REGION": "B", "ZONE": "L", "FIPNUM": 4, "ROOT": ("B", "L", 4)},
                {"REGION": "B", "ZONE": "U", "FIPNUM": 3, "ROOT": ("B", "U", 3)},
            ],
        ),
        (
            # Two regions, two zones, 2 horizontal FIPNUMs -> 2 groups:
            {
                "region2fipnum": {"A": [2, 1], "B": [1, 2]},
                "zone2fipnum": {"U": 1, "L": [2, 2]},  # Double for L is ignored.
            },
            [
                {"REGION": "A", "ZONE": "L", "FIPNUM": 2, "ROOT": ("B", "L", 2)},
                {"REGION": "A", "ZONE": "U", "FIPNUM": 1, "ROOT": ("B", "U", 1)},
                {"REGION": "B", "ZONE": "L", "FIPNUM": 2, "ROOT": ("B", "L", 2)},
                {"REGION": "B", "ZONE": "U", "FIPNUM": 1, "ROOT": ("B", "U", 1)},
            ],
        ),
        (
            # Two regions, two zones, 2 region-wise FIPNUMs -> 2 groups:
            {
                "region2fipnum": {"A": 1, "B": 2},
                "zone2fipnum": {"U": [1, 2], "L": [1, 2]},
            },
            [
                {"REGION": "A", "ZONE": "L", "FIPNUM": 1, "ROOT": ("A", "U", 1)},
                {"REGION": "A", "ZONE": "U", "FIPNUM": 1, "ROOT": ("A", "U", 1)},
                {"REGION": "B", "ZONE": "L", "FIPNUM": 2, "ROOT": ("B", "U", 2)},
                {"REGION": "B", "ZONE": "U", "FIPNUM": 2, "ROOT": ("B", "U", 2)},
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
                {"REGION": "A", "ZONE": "U", "FIPNUM": 1, "ROOT": ("B", "U", 2)},
                {"REGION": "B", "ZONE": "U", "FIPNUM": 1, "ROOT": ("B", "U", 2)},
                {"REGION": "B", "ZONE": "U", "FIPNUM": 2, "ROOT": ("B", "U", 2)},
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
