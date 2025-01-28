from os.path import abspath

import pytest


@pytest.fixture()
def data_grid(testdata_path):
    return {
        "path": abspath(testdata_path / "3dgrids/reek/"),
        "grid": "reek_sim_grid.roff",
        "properties": {
            "PORO": {"name": "reek_sim_poro.roff"},
            "PERM": {"name": "reek_sim_permx.roff"},
        },
        "selectors": {
            "ZONE": {"name": "reek_sim_zone.roff"},
            "FACIES": {"name": "reek_sim_facies2.roff"},
        },
        "verbosity": 1,
    }


@pytest.fixture()
def data_wells(testdata_path):
    return {
        "path": abspath(testdata_path / "wells/reek/1/"),
        "wells": ["OP_*.w"],
        "properties": {
            "PORO": {"name": "Poro"},
            "PERM": {"name": "Perm"},
        },
        "selectors": {
            "ZONE": {"name": "Zonelog"},
            "FACIES": {"name": "Facies"},
        },
        "verbosity": 1,
    }


@pytest.fixture()
def data_bwells(testdata_path):
    return {
        "path": abspath(testdata_path / "wells/reek/1/"),
        "wells": ["OP_1.bw"],
        "properties": {
            "PORO": {"name": "Poro"},
        },
        "selectors": {
            "FACIES": {"name": "Facies"},
        },
        "verbosity": 1,
    }
