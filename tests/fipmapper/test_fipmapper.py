import pytest

from fmu.tools.fipmapper import fipmapper


@pytest.mark.parametrize(
    "input_dict, expected_inverse",
    [
        ({}, {}),
        ({"foo": "bar"}, {"bar": ["foo"]}),
        ({"foo": "1", "bar": "2"}, {"1": ["foo"], "2": ["bar"]}),
        ({"foo": "1", "bar": "1"}, {"1": ["bar", "foo"]}),
        ({"foo": 1, "bar": 1}, {1: ["bar", "foo"]}),
        ({1: "foo", 2: "foo"}, {"foo": [1, 2]}),
        ({2: "foo", 1: "foo"}, {"foo": [1, 2]}),
        (
            {"foo": [1, 2], "bar": [3, 4]},
            {1: ["foo"], 2: ["foo"], 3: ["bar"], 4: ["bar"]},
        ),
        (
            {"foo": [1, 2], "bar": [3, 4], "Totals": [1, 2, 3, 4]},
            {
                1: ["Totals", "foo"],
                2: ["Totals", "foo"],
                3: ["Totals", "bar"],
                4: ["Totals", "bar"],
            },
        ),
    ],
)
def test_invert_map(input_dict, expected_inverse):
    assert fipmapper.invert_map(input_dict) == expected_inverse


def test_invert_map_skipstring():
    input_dict = {"foo": [1, 2], "bar": [3, 4], "Totals": [1, 2, 3, 4]}
    assert fipmapper.invert_map(input_dict, skipstring="Totals") == {
        1: ["foo"],
        2: ["foo"],
        3: ["bar"],
        4: ["bar"],
    }


def test_fipmapper_empty():
    mapper = fipmapper.FipMapper()
    assert mapper.has_region2fip is False
    assert mapper.has_zone2fip is False
    assert mapper.has_fip2region is False
    assert mapper.has_fip2zone is False


def test_fipmapper():
    mapper = fipmapper.FipMapper(
        mapdata={"fipnum2region": {1: "West-Brent", 2: "East-Sognefjord"}}
    )
    assert mapper.fip2region(1) == ["West-Brent"]
    assert mapper.fip2region(2) == ["East-Sognefjord"]
    assert mapper._fips2regions([1, 2]) == [["West-Brent"], ["East-Sognefjord"]]
    assert mapper.region2fip("West-Brent") == [1]
    assert mapper._regions2fips(["West-Brent"]) == [[1]]
    assert mapper._regions2fips(["West-Brent", "East-Sognefjord"]) == [[1], [2]]


def test_fipmapper_zones():
    mapper = fipmapper.FipMapper(
        mapdata={"fipnum2zone": {1: "Upper", 2: "Middle", 3: "Middle"}}
    )
    assert mapper.fip2zone(1) == ["Upper"]
    assert mapper.fip2zone(2) == ["Middle"]
    assert mapper.fip2zone(3) == ["Middle"]
    assert mapper.zone2fip("Upper") == [1]
    assert mapper.zone2fip("Middle") == [2, 3]


def test_integer_regions():
    """Regions are sometimes integer, and then they will
    typically be returned as integers from the yaml parsing"""
    mapper = fipmapper.FipMapper(mapdata={"fipnum2region": {1: 1, 2: 2}})
    assert mapper.fip2region(1) == [1]
    assert mapper.fip2region(2) == [2]
    assert mapper.region2fip(1) == [1]
    assert mapper.region2fip(2) == [2]


def test_integer_zones():
    """Should also allow using integers for zones. Maybe
    the integer is actually the k index"""
    mapper = fipmapper.FipMapper(mapdata={"fipnum2zone": {1: 1, 2: 2}})
    assert mapper.fip2zone(1) == [1]
    assert mapper.fip2zone(2) == [2]
    assert mapper.zone2fip(1) == [1]
    assert mapper.zone2fip(2) == [2]


def test_mixed_datatypes():
    """Mixed ints/strs in regions and zones"""
    mapper = fipmapper.FipMapper(
        mapdata={"fipnum2region": {1: 1, 2: "B"}, "fipnum2zone": {1: 1, 2: "L"}}
    )
    assert mapper.fip2region(1) == [1]
    assert mapper.fip2region(2) == ["B"]
    assert mapper.region2fip(1) == [1]
    assert mapper.region2fip("B") == [2]

    assert mapper.fip2zone(1) == [1]
    assert mapper.fip2zone(2) == ["L"]
    assert mapper.zone2fip(1) == [1]
    assert mapper.zone2fip("L") == [2]


def test_fipmapper_regzone2fip():
    mapper = fipmapper.FipMapper(
        mapdata={
            "fipnum2zone": {1: "Upper", 2: "Middle", 3: "Upper", 4: "Middle"},
            "fipnum2region": {
                1: "West-Brent",
                2: "West-Brent",
                3: "East-Sognefjord",
                4: "East-Sognefjord",
            },
        }
    )
    assert mapper.regzone2fip("West-Brent", "Upper") == [1]
    assert mapper.regzone2fip("West-Brent", "Middle") == [2]
    assert mapper.regzone2fip("East-Sognefjord", "Upper") == [3]
    assert mapper.regzone2fip("East-Sognefjord", "Middle") == [4]


@pytest.mark.parametrize(
    "map_data, expected_regions, expected_zones, expected_fipnums",
    [
        ({"region2fipnum": {"A": 1}, "zone2fipnum": {"U": 1}}, ["A"], ["U"], [1]),
        (
            {"region2fipnum": {"A": [1, 2]}, "zone2fipnum": {"U": 1}},
            ["A"],
            ["U"],
            [1, 2],
        ),
        (
            # Test sorting
            {"region2fipnum": {"A": [2, 1]}, "zone2fipnum": {"U": [2, 1]}},
            ["A"],
            ["U"],
            [1, 2],
        ),
        (
            # Test sorting with integer regions
            {"region2fipnum": {10: [3], 1: [2, 1]}, "zone2fipnum": {"U": [2, 1, 3]}},
            [1, 10],
            ["U"],
            [1, 2, 3],
        ),
        (
            {
                "region2fipnum": {"A": [2, 1], "B": 3},
                "zone2fipnum": {"U": [1], "L": [3, 2]},
            },
            ["A", "B"],
            ["L", "U"],
            [1, 2, 3],
        ),
        pytest.param({}, [], [], [], marks=pytest.mark.xfail(raises=AssertionError)),
        pytest.param(
            {"region2fipnum": {"A": 1}},
            ["A"],
            [],
            [1],
            # get_zones fails here.
            marks=pytest.mark.xfail(raises=AssertionError),
        ),
        pytest.param(
            {"zone2fipnum": {"U": 1}},
            [],
            ["U"],
            [1],
            # get_regions fails here.
            marks=pytest.mark.xfail(raises=AssertionError),
        ),
        pytest.param(
            {"zone2fipnum": {"U": "fip1"}, "region2fipnum": {"W": "fip1"}},
            ["W"],
            ["U"],
            ["fip1"],
            marks=pytest.mark.xfail(raises=TypeError),
        ),
    ],
)
def test_get_regions_zones_fipnums(
    map_data, expected_regions, expected_zones, expected_fipnums
):
    """Test the three functions get_regions, get_zones and get_fipnums"""
    mapper = fipmapper.FipMapper(mapdata=map_data)
    assert mapper.get_regions() == expected_regions
    assert mapper.get_zones() == expected_zones
    assert mapper.get_fipnums() == expected_fipnums


@pytest.mark.parametrize(
    "input_dict, expected_dict",
    [
        ({}, {}),
        ({"FIPNUM": {}}, {}),
        ({"FIPNUM": 0}, {}),
        ({"FIPNUM": {"groups": {}}}, {}),
        ({"FOO": 0}, {}),
        # First test with the webviz format @march 2021, with "groups"
        # as a required level:
        (
            {"FIPNUM": {"groups": {"REGION": {"west": 1}}}},
            {"region2fipnum": {"west": 1}},
        ),
        (
            {"FIPNUM": {"groups": {"REGION": {"west": [1]}, "ZONE": {"lower": [2]}}}},
            {"region2fipnum": {"west": [1]}, "zone2fipnum": {"lower": [2]}},
        ),
        # The "groups" level might disappear in webviz format, so ensure
        # we also support that when/if it happens:
        (
            {"FIPNUM": {"REGION": {"west": 1}}},
            {"region2fipnum": {"west": 1}},
        ),
        (
            {"FIPNUM": {"REGION": {"west": [1]}, "ZONE": {"lower": [2]}}},
            {"region2fipnum": {"west": [1]}, "zone2fipnum": {"lower": [2]}},
        ),
    ],
)
def test_webviz_to_prtvol2csv(input_dict, expected_dict):
    print(fipmapper.webviz_to_prtvol2csv(input_dict))
    assert fipmapper.webviz_to_prtvol2csv(input_dict) == expected_dict
