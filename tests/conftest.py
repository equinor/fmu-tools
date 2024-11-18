import os
import pathlib

import pytest

# Capture the initial working directory at the start of the test session
initial_pwd = pathlib.Path.cwd()


def pytest_runtest_setup(item):
    """Called for each test, see also pytest section in setup.cfg."""

    markers = [value.name for value in item.iter_markers()]

    # pytest.mark.skipifroxar:
    if "skipifroxar" in markers and "ROXENV" in os.environ:
        pytest.skip("Skip test in ROXENV (env variable ROXENV is present)")

    # pytest.mark.skipunlessroxar:
    if "skipunlessroxar" in markers and "ROXENV" not in os.environ:
        pytest.skip("Skip test if outside ROXENV (env variable ROXENV is present)")


def pytest_configure(config):
    # Ensure xtgeo-testdata is present where expected before running
    testdatapath = os.environ.get("XTG_TESTPATH", config.getoption("--testdatapath"))
    xtg_testdata = pathlib.Path(testdatapath)
    if not xtg_testdata.is_dir():
        raise RuntimeError(
            f"xtgeo-testdata path {testdatapath} does not exist! Clone it from "
            "https://github.com/equinor/xtgeo-testdata. The preferred location "
            " is ../xtgeo-testdata."
        )


def pytest_addoption(parser):
    parser.addoption(
        "--testdatapath",
        help="Relative path to xtgeo-testdata, defaults to ../xtgeo-testdata"
        "and is overriden by the XTG_TESTPATH environment variable."
        "Experimental feature, not all tests obey this option.",
        action="store",
        default="../xtgeo-testdata",
    )


@pytest.fixture(scope="session")
def testdata_path(request):
    # Prefer 'XTG_TESTPATH' environment variable, fallback to the pytest --testdatapath
    # environment variable, which defaults to '../xtgeo-testdata'
    testdatapath = os.environ.get(
        "XTG_TESTPATH", request.config.getoption("--testdatapath")
    )
    return (initial_pwd / testdatapath).resolve()
