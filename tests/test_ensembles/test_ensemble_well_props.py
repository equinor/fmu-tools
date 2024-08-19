"""Testing qcforward method blockedwells vs gridprops"""

import os
import pathlib
from copy import deepcopy

import pytest
import xtgeo
import yaml

from fmu.tools._common import preserve_cwd
from fmu.tools.ensembles import ensemble_well_props

SOURCE = pathlib.Path(__file__).absolute().parent.parent.parent

RPATH0 = (
    SOURCE / "tests/data/ensembles/01_drogon_ahm/realization-0/iter-3/share/results"
)

WELLNAME1 = SOURCE / "tests" / "data" / "zone_tops_from_grid" / "OP_1.w"
WELLNAME2 = RPATH0 / "wells" / "55_33-A-3.rmswell"
WELLNAME3 = SOURCE / "tests/data/ensembles/drogon_planned_wells/OP5_Y1.rmswell"

GFILE1 = RPATH0 / "grids" / "geogrid.roff"
POROFILE1 = RPATH0 / "grids" / "geogrid--phit.roff"
FACIESFILE1 = RPATH0 / "grids" / "geogrid--facies.roff"


@pytest.fixture(name="configdata")
def fixture_configdata():
    root = str(SOURCE / "tests/data/ensembles/01_drogon_ahm")
    return {
        "ensemble": {
            "root": str(root),
            "realizations": {"range": "0-3"},
            "iteration": "iter-3",
        },
        "well": {
            "file": str(WELLNAME2),
            "lognames": ["PHIT", "MDepth", "Facies"],
            "mdlog": "MDepth",
            "mdranges": [[1653, 1670], [1680, 1698]],
        },
        "gridproperties": {
            "grid": {"filestub": "share/results/grids/geogrid.roff"},
            "properties": [
                {
                    "name": "Facies",
                    "filestub": "share/results/grids/geogrid--facies.roff",
                    "discrete": True,
                },
                {
                    "name": "PHIT",
                    "filestub": "share/results/grids/geogrid--phit.roff",
                },
            ],
        },
        "report": {
            "average_logs": {
                "fileroot": "/tmp/xxxx",
            },
            "cumulative_lengths": {
                "fileroot": "/tmp/xxcum",
                "criteria": {
                    "Facies": {
                        "codes": [1],
                    },
                },
            },
            "keep_intermediate_logs": True,
        },
    }


@pytest.fixture(name="configdata2")
def fixture_configdata2():
    root = str(SOURCE / "tests/data/ensembles/01_drogon_ahm")
    return {
        "ensemble": {
            "root": str(root),
            "realizations": {"range": "0-2"},
            "iteration": "iter-3",
        },
        "well": {
            "file": str(WELLNAME2),
            "lognames": ["PHIT", "MDepth", "Facies"],
            "mdlog": "MDepth",
            "mdranges": [[1653, 1670], [1680, 1698]],
        },
        "gridproperties": {
            "grid": {"filestub": "share/results/grids/geogrid.roff"},
            "properties": [
                {
                    "name": "Facies",
                    "filestub": "share/results/grids/geogrid--facies.roff",
                    "discrete": True,
                },
                {
                    "name": "PHIT",
                    "filestub": "share/results/grids/geogrid--phit.roff",
                },
            ],
        },
        "report": {
            "average_logs": {
                "fileroot": "/tmp/xxxx2",
            },
            "cumulative_lengths": {
                "fileroot": "/tmp/xxcum2",
                "criteria": {
                    "PHIT": {
                        "interval": [0.23, 0.4],
                    },
                    "Facies": {
                        "codes": [1],
                    },
                },
            },
            "keep_intermediate_logs": True,
        },
    }


@preserve_cwd
def test_dump_example(tmp_path):
    """Test the dump of example YAML file."""
    os.chdir(tmp_path)
    ensemble_well_props.dump_example_config()

    examplefile = tmp_path / "example.yml"
    assert examplefile.is_file()

    with open(examplefile, "r", encoding="utf-8") as stream:
        cfg = yaml.safe_load(stream)

        assert "mywell.w" in str(cfg)
        assert (
            cfg["gridproperties"]["grid"]["filestub"]
            == "share/results/grids/geogrid.roff"
        )


def test_wellcase_class():
    """Test WellCase data class."""
    well = ensemble_well_props.WellCase(
        xtgeo.well_from_file(WELLNAME1),
        "MDLog",
        [[2200, 2300], [2350, 2400]],
    )

    wobj = well.well
    assert isinstance(wobj, xtgeo.Well)
    print(wobj.dataframe)
    assert wobj.dataframe["Poro"].mean() == pytest.approx(0.200907, abs=0.001)
    assert wobj.nrow == 74

    well = ensemble_well_props.WellCase(
        xtgeo.well_from_file(WELLNAME2, lognames=["MDepth", "PHIT"]),
        "MDepth",
        [[1653, 1670], [1680, 1698]],
        delta=1,
    )

    wobj = well.well
    print(wobj.dataframe)

    assert wobj.dataframe["PHIT"].mean() == pytest.approx(0.176936, abs=0.001)
    assert wobj.nrow == 35


def test_config_data(configdata):
    """Test the ConfigData class."""

    cfg = ensemble_well_props.ConfigData(configdata)
    assert cfg.wellfile == str(WELLNAME2)

    assert cfg.proplist[0].name == "Facies"


def test_loop_for_compute_dryrun(configdata):
    """Test the loop compute."""

    sinfo = ensemble_well_props.ScreenInfo()
    cfg = ensemble_well_props.ConfigData(configdata)

    print(cfg.mdranges)

    ensemble_well_props.loop_for_compute(configdata, sinfo, _dryrun=True)


def test_compute_some_props(configdata):
    """Test the actual compute of one well on one realization."""

    cfg = ensemble_well_props.ConfigData(configdata)

    wcase = ensemble_well_props.WellCase(
        xtgeo.well_from_file(WELLNAME2, lognames=cfg.lognames), cfg.mdlog, cfg.mdranges
    )
    grd = xtgeo.grid_from_file(GFILE1)
    wcase.well.make_ijk_from_grid(grd)

    myprops = [FACIESFILE1, POROFILE1]
    for ncount, pcase in enumerate(myprops):
        prop = xtgeo.gridproperty_from_file(pcase)
        prop.geometry = grd

        ensemble_well_props.run_compute(0, wcase.well, cfg.proplist[ncount], prop)

    assert "Facies_r0" in wcase.well.dataframe
    assert wcase.well.dataframe["PHIT_r0"].mean() == pytest.approx(0.171533, abs=0.001)


def test_loop_for_compute(configdata):
    """Test the loop compute with actual run."""

    newcfg = deepcopy(configdata)
    newcfg["well"]["file"] = WELLNAME3
    newcfg["well"]["lognames"] = "all"
    newcfg["well"]["mdlog"] = "MD"
    newcfg["well"]["mdranges"] = [[4100, 4200], [4680, 4700]]
    newcfg["well"]["delta"] = 3
    sinfo = ensemble_well_props.ScreenInfo()

    ensprops = ensemble_well_props.loop_for_compute(newcfg, sinfo)

    print(ensprops.well.dataframe)


def test_main(configdata):
    newcfg = deepcopy(configdata)
    newcfg["well"]["file"] = WELLNAME3
    newcfg["well"]["lognames"] = "all"
    newcfg["well"]["mdlog"] = "MD"
    newcfg["well"]["mdranges"] = [[4100, 4200], [4680, 4700]]
    newcfg["well"]["delta"] = 3

    ensemble_well_props.main(newcfg)


@preserve_cwd
def test_script(tmp_path, configdata):
    """Test the command line script end point."""

    newcfg = deepcopy(configdata)
    newcfg["well"]["file"] = str(WELLNAME3)
    newcfg["well"]["lognames"] = "all"
    newcfg["well"]["mdlog"] = "MD"
    newcfg["well"]["mdranges"] = [[4100, 4200], [4680, 4700]]
    newcfg["well"]["delta"] = 3

    newcfg["report"]["average_logs"]["fileroot"] = "avgfile"
    newcfg["report"]["cumulative_lengths"]["fileroot"] = "cumfile"

    with open(tmp_path / "myconfig.yml", "w", encoding="utf-8") as stream:
        yaml.dump(newcfg, stream)

    print(tmp_path)

    os.chdir(tmp_path)

    ensemble_well_props.main(["--config", "myconfig.yml"])


@preserve_cwd
@pytest.mark.parametrize(
    "faciescodes, poro_interval, expected",
    [
        ([1], [0.21, 0.5], 0.391666),
        ([1], [0.23, 0.5], 0.291666),
        ([6], [0.0, 0.5], 0.45000),
    ],
)
def test_script_config2(tmp_path, configdata2, faciescodes, poro_interval, expected):
    """Test the command line script end point."""

    newcfg = deepcopy(configdata2)
    newcfg["well"]["file"] = str(WELLNAME3)
    newcfg["well"]["lognames"] = "all"
    newcfg["well"]["mdlog"] = "MD"
    newcfg["well"]["mdranges"] = [[4100, 4200], [4680, 4700]]
    newcfg["well"]["delta"] = 3

    newcumlen = newcfg["report"]["cumulative_lengths"]["criteria"]
    newcumlen["PHIT"]["interval"] = poro_interval
    newcumlen["Facies"]["codes"] = faciescodes

    newcfg["report"]["average_logs"]["fileroot"] = "avgfile2"
    newcfg["report"]["cumulative_lengths"]["fileroot"] = "cumfile2"

    with open(tmp_path / "myconfig2.yml", "w", encoding="utf-8") as stream:
        yaml.dump(newcfg, stream)

    print(tmp_path)

    os.chdir(tmp_path)

    ensemble_well_props.main(["--config", "myconfig2.yml"])
    with open(tmp_path / "cumfile2_summary.csv", "r", encoding="utf-8") as result:
        for line in result.readlines():
            name, frac, _ = line.split(",")
            if name == "mean":
                assert float(frac) == pytest.approx(expected, abs=0.01)
