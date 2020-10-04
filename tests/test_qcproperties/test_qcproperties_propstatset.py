from os.path import abspath
import yaml

from fmu.tools.qcproperties.qcproperties import QCProperties


cfg_path = abspath("tests/data/propstatistics/propstat.yml")

with open(cfg_path, "r") as stream:
    cfg = yaml.safe_load(stream)

GRIDDATA = cfg["grid"][0]
GRIDDATA["path"] = abspath("../xtgeo-testdata/3dgrids/reek/")

WELLDATA = cfg["wells"][0]
WELLDATA["path"] = abspath("../xtgeo-testdata/wells/reek/1/")

BWELLDATA = cfg["blockedwells"][0]
BWELLDATA["path"] = abspath("../xtgeo-testdata/wells/reek/1/")


def test_propstatset():

    qcp = QCProperties()

    qcp.get_grid_statistics(GRIDDATA)
    qcp.get_well_statistics(WELLDATA)
    qcp.get_bwell_statistics(BWELLDATA)

    assert len(qcp.dataframe["ID"].unique()) == 3


def test_propstatset_auto_combination():

    qcp = QCProperties()

    qcp.get_grid_statistics(GRIDDATA)

    assert len(qcp.dataframe["ID"].unique()) == 1

    qcp.get_well_statistics(WELLDATA)

    assert len(qcp.dataframe["ID"].unique()) == 2

    qcp.get_bwell_statistics(BWELLDATA, reuse=True)

    assert len(qcp.dataframe["ID"].unique()) == 3
