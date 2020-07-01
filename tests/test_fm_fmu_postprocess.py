"""Test fm_fmu_postprocessor

Test data that are not part of the repo, but can be fetched from
other repos:

tests/data/testensemble-reek001  (from fmu-ensemble/tests/data)
tests/data/webviz-subsurface-testdata (separate repository, > gb in size)
"""


import os
import shutil
import subprocess

import pandas as pd

import pytest
import logging

from fmu.tools.fmu_postprocess.fm_fmu_postprocess import (
    get_eclbasename,
    identifying_substrings,
    merge_fipnum_to_rmsvols,
    parse_config,
    prepare_share_dir,
    process_rms_volumetrics,
    process_ecl2df,
)


logger = logging.getLogger("fm_fmu_postprocess")
logging.basicConfig()
logger.setLevel(logging.INFO)


@pytest.fixture
def reek_real0(tmpdir):
    datadir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "data/reek-real0iter0",
    )
    cwd = os.getcwd()
    tmpdir.chdir()
    if not os.path.exists(datadir):
        pytest.skip()
    if not os.path.exists(os.path.join(datadir, "share")):
        pytest.skip()
    shutil.copytree(datadir, "iter-0")
    tmpdir.join("iter-0").chdir()
    try:
        yield
    finally:
        os.chdir(cwd)


@pytest.mark.integration
def test_installed():
    """Check that the script is installed in path"""
    subprocess.check_output(["fm_fmu_postprocess", "-h"])


def test_prepare_share_dir(tmpdir):
    tmpdir.chdir()
    prepare_share_dir(".")
    assert os.path.exists("share")
    assert os.path.isdir("share")
    assert os.path.exists("share/results")
    assert os.path.isdir("share/results")
    assert os.path.exists("share/results/tables")
    assert os.path.isdir("share/results/tables")
    assert os.path.exists("share/results/volumes")
    assert os.path.isdir("share/results/volumes")


def test_identifying_substrings():
    assert identifying_substrings(["share/geogrid.txt", "share/simgrid.txt"]) == [
        "geo",
        "sim",
    ]

    assert identifying_substrings(["geo", "sim"]) == ["geo", "sim"]

    with pytest.raises(ValueError, match="Strings are identical"):
        identifying_substrings(["geo", "geo"])

    assert identifying_substrings(["geo", "geosim"]) == ["", "sim"]

    assert identifying_substrings(
        ["hei_geo_common_id2_txt", "hei_sim_common_id3_txt"]
    ) == ["geo_2", "sim_3"]

    # Spaces are ignored:
    assert identifying_substrings(["g  eo", "si m"]) == ["geo", "sim"]

    # Test recursive feature:
    assert identifying_substrings(
        ["share/geo.txt", "share/sim.txt", "share/eclipse.txt"]
    ) == ["geo", "sim", "eclipse"]
    assert identifying_substrings(
        ["share/geo.txt", "share/sim.txt", "share/eclipse.txt", "share/e300.txt"]
    ) == ["geo", "sim", "eclipse", "e300"]


def test_reek_rmsvol(reek_real0):
    prepare_share_dir(".")
    process_rms_volumetrics()
    assert os.path.exists("share/results/volumes/simgrid_vol_oil.csv")
    assert os.path.exists("share/results/volumes/geogrid_vol_oil.csv")

    simgrid = pd.read_csv("share/results/volumes/simgrid_vol_oil.csv")
    assert "ZONE" in simgrid
    assert "REGION" in simgrid
    assert "STOIIP_OIL" in simgrid
    assert len(simgrid) == 6

    geogrid = pd.read_csv("share/results/volumes/geogrid_vol_oil.csv")
    assert "ZONE" in geogrid
    assert "REGION" in geogrid
    assert "FIPNUM" not in geogrid
    assert "STOIIP_OIL" in geogrid
    assert len(geogrid) == 6


def test_merge_fipnum():
    dframe = pd.DataFrame(columns=["REGION", "VOLUME"], data=[["foo", 1], ["bar", 2]])

    assert "FIPNUM" not in merge_fipnum_to_rmsvols(dframe)  # No config provided
    dframe_fipnum = merge_fipnum_to_rmsvols(
        dframe, config={"region2fipnum": {"foo": 3, "bar": 4}}, inplace=False
    )
    assert "FIPNUM" in dframe_fipnum
    assert set(dframe_fipnum["FIPNUM"].unique()) == {3, 4}

    dframe_fail = merge_fipnum_to_rmsvols(
        dframe, config={"region2fipnum": {"foo": 3}}  # One region missing
    )
    assert "FIPNUM" not in dframe_fail  # logger will emit warning/error

    # Merging with a reverse dict:
    dframe_fipnum = merge_fipnum_to_rmsvols(
        dframe, config={"fipnum2region": {3: "foo", 4: "bar"}}, inplace=False
    )
    assert "FIPNUM" in dframe_fipnum
    assert set(dframe_fipnum["FIPNUM"].unique()) == {3, 4}

    dframe_fail = merge_fipnum_to_rmsvols(  # One missing region, should fail:
        dframe, config={"fipnum2region": {3: "foo"}}, inplace=False
    )
    assert "FIPNUM" not in dframe_fail


def test_parse_config(tmpdir):
    tmpdir.chdir()
    with open("foo.yml", "w") as file_h:
        file_h.write(
            """
region2fipnum:
  foo: 3
  bar: 4
"""
        )
    config = parse_config("foo.yml")
    assert "region2fipnum" in config
    assert config.region2fipnum["foo"] == 3
    assert config.region2fipnum["bar"] == 4


def test_reek_rmsvol_fipnum(reek_real0):
    prepare_share_dir(".")
    region2fipnum = {"1": "1", "2": "1"}
    process_rms_volumetrics(config=dict(region2fipnum=region2fipnum))
    assert os.path.exists("share/results/volumes/simgrid_vol_oil.csv")
    simgrid = pd.read_csv("share/results/volumes/simgrid_vol_oil.csv")
    assert "FIPNUM" in simgrid
    assert len(simgrid["FIPNUM"].unique()) == 1
    assert len(simgrid) == 6

    # Type difficulties, okay because we go via CSV files
    region2fipnum = {"1": "1", "2": 1}
    process_rms_volumetrics(config=dict(region2fipnum=region2fipnum))
    assert os.path.exists("share/results/volumes/simgrid_vol_oil.csv")
    simgrid = pd.read_csv("share/results/volumes/simgrid_vol_oil.csv")
    assert "FIPNUM" in simgrid
    assert len(simgrid["FIPNUM"].unique()) == 1
    assert len(simgrid) == 6

    geogrid = pd.read_csv("share/results/volumes/geogrid_vol_oil.csv")
    assert "ZONE" in geogrid
    assert "REGION" in geogrid
    assert "STOIIP_OIL" in geogrid
    assert len(geogrid) == 6


def test_get_eclbasename(reek_real0):
    assert get_eclbasename


def test_reek_ecl2df(reek_real0):
    prepare_share_dir(".")
    files_to_be_produced = [
        "compdat.csv",
        "equil.csv",
        "faults.csv",
        "gruptree.csv",
        "fipreports.csv",
        "nnc.csv",
        "pvt.csv",
        "rft.csv",
        "satfunc.csv",
        "trans.csv",
        "trans-fipnum.csv",
        "wcon.csv",
        "unsmry--monthly.csv",
        "unsmry--yearly.csv",
        "unsmry--lastdate.csv",
        "unsmry--block-monthly.csv",
        "unsmry--region--monthly.csv",
        "unsmry--group-monthly.csv",
    ]
    files_to_be_produced = [
        os.path.join("share/results/tables", filename)
        for filename in files_to_be_produced
    ]
    # In case repo gets polluted:
    for filename in files_to_be_produced:
        if os.path.exists(filename):
            os.path.unlink(filename)

    process_ecl2df(get_eclbasename("2_R001"))

    for filename in files_to_be_produced:
        assert os.path.exists(filename)
        dframe = pd.read_csv(filename)
        assert not dframe.empty
