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
            # Almost three-by-three reservoir, used in demonstration
            # of the problem solved, involving all "cruxes":
            {
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
                    ["A", "L", 5, ("B", "L", 5)],
                    ["A", "M", 1, ("B", "U", 1)],
                    ["A", "U", 1, ("B", "U", 1)],
                    ["B", "L", 5, ("B", "L", 5)],
                    ["B", "M", 1, ("B", "U", 1)],
                    ["B", "U", 1, ("B", "U", 1)],
                    ["C", "L", 4, ("C", "M", 4)],
                    ["C", "M", 4, ("C", "M", 4)],
                    ["C", "U", 2, ("C", "U", 3)],
                    ["C", "U", 3, ("C", "U", 3)],
                    # (4 unique ROOTs)
                ],
            ),
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
