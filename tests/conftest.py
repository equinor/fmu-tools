import os
import pytest


def pytest_runtest_setup(item):
    """Called for each test, see also pytest section in setup.cfg."""

    markers = [value.name for value in item.iter_markers()]

    # pytest.mark.skipifroxar:
    if "skipifroxar" in markers:
        if "ROXENV" in os.environ:
            pytest.skip("Skip test in ROXENV (env variable ROXENV is present)")

    # pytest.mark.skipunlessroxar:
    if "skipunlessroxar" in markers:
        if "ROXENV" not in os.environ:
            pytest.skip("Skip test if outside ROXENV (env variable ROXENV is present)")
