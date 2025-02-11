import os
from pathlib import Path

import pytest
import yaml

from fmu.tools.qcdata import QCData
from fmu.tools.qcproperties._grid2df import GridProps2df
from fmu.tools.qcproperties._well2df import WellLogs2df
from fmu.tools.qcproperties.qcproperties import QCProperties


class TestProperties2df:
    """Tests related to generation of dataframe from properties"""

    def test_wells(self, data_wells):
        """Test creating property dataframe from wells"""
        pdf = WellLogs2df(data=data_wells, project=None, xtgdata=QCData())
        assert pdf.dataframe["PORO"].mean() == pytest.approx(0.1539, abs=0.001)
        assert pdf.dataframe["PORO"].max() == pytest.approx(0.3661, abs=0.001)
        assert set(pdf.dataframe.columns) == {"PORO", "PERM", "ZONE", "FACIES"}

    def test_blockedwells(self, data_bwells):
        """Test creating property dataframe from blocked wells"""
        pdf = WellLogs2df(
            data=data_bwells, project=None, xtgdata=QCData(), blockedwells=True
        )
        assert pdf.dataframe["PORO"].mean() == pytest.approx(0.1709, abs=0.001)
        assert pdf.dataframe["PORO"].max() == pytest.approx(0.3640, abs=0.001)
        assert set(pdf.dataframe.columns) == {"PORO", "FACIES"}

    def test_gridprops(self, data_grid):
        """Test creating property dataframe from grid properties"""
        pdf = GridProps2df(data=data_grid, project=None, xtgdata=QCData())
        assert pdf.dataframe["PORO"].mean() == pytest.approx(0.1677, abs=0.001)
        assert pdf.dataframe["PORO"].max() == pytest.approx(0.3613, abs=0.001)
        assert set(pdf.dataframe.columns) == {"PORO", "PERM", "ZONE", "FACIES"}

    def test_props_and_selectors_as_list(self, data_grid):
        """Test"""
        data_grid["properties"] = ["reek_sim_poro.roff", "reek_sim_permx.roff"]
        data_grid["selectors"] = ["reek_sim_zone.roff", "reek_sim_facies2.roff"]

        pdf = GridProps2df(data=data_grid, project=None, xtgdata=QCData())
        assert pdf.dataframe["reek_sim_poro.roff"].mean() == pytest.approx(
            0.1677, abs=0.001
        )
        assert pdf.dataframe["reek_sim_poro.roff"].max() == pytest.approx(
            0.3613, abs=0.001
        )
        assert set(pdf.dataframe.columns) == {
            "reek_sim_poro.roff",
            "reek_sim_permx.roff",
            "reek_sim_zone.roff",
            "reek_sim_facies2.roff",
        }

    def test_filters(self, data_grid):
        """Test filters as argument"""
        data_grid["filters"] = {
            "reek_sim_facies2.roff": {
                "include": ["FINESAND", "COARSESAND"],
            }
        }
        pdf = GridProps2df(data=data_grid, project=None, xtgdata=QCData())

        assert list(pdf.dataframe["FACIES"].unique()) == ["FINESAND", "COARSESAND"]
        assert pdf.dataframe["PORO"].mean() == pytest.approx(0.2374, abs=0.001)

        data_grid["filters"] = {
            "reek_sim_facies2.roff": {
                "exclude": "FINESAND",
            }
        }
        pdf = GridProps2df(data=data_grid, project=None, xtgdata=QCData())

        assert "FINESAND" not in list(pdf.dataframe["FACIES"].unique())

        data_grid["filters"] = {
            "reek_sim_poro.roff": {
                "range": [0.15, 0.25],
            }
        }
        pdf = GridProps2df(data=data_grid, project=None, xtgdata=QCData())
        assert pdf.dataframe["PORO"].mean() == pytest.approx(0.2027, abs=0.001)
        assert pdf.dataframe["PORO"].min() > 0.15
        assert pdf.dataframe["PORO"].max() < 0.25

    def test_selector_filters(self, data_grid):
        """Test filters on selector"""
        data_grid["selectors"] = {
            "FACIES": {"name": "reek_sim_facies2.roff", "include": "FINESAND"},
        }
        pdf = GridProps2df(data=data_grid, project=None, xtgdata=QCData())

        assert list(pdf.dataframe["FACIES"].unique()) == ["FINESAND"]

        # test exclude values using list
        data_grid["selectors"] = {
            "FACIES": {
                "name": "reek_sim_facies2.roff",
                "exclude": ["FINESAND", "SHALE"],
            },
        }
        pdf = GridProps2df(data=data_grid, project=None, xtgdata=QCData())

        assert "FINESAND" not in list(pdf.dataframe["FACIES"].unique())
        assert "SHALE" not in list(pdf.dataframe["FACIES"].unique())

    def test_filters_and_selector_filters(self, data_grid):
        """
        Test filters on both selector and as separate argument
        Wanted behaviour is to ignore the filter on the selector
        """
        data_grid["selectors"] = {
            "FACIES": {"name": "reek_sim_facies2.roff", "exclude": "FINESAND"},
        }
        data_grid["filters"] = {
            "reek_sim_facies2.roff": {
                "include": ["FINESAND", "COARSESAND"],
            }
        }
        pdf = GridProps2df(data=data_grid, project=None, xtgdata=QCData())

        assert list(pdf.dataframe["FACIES"].unique()) == ["FINESAND", "COARSESAND"]
        assert pdf.dataframe["PORO"].mean() == pytest.approx(0.2374, abs=0.001)

    def test_filters_and_property_filters(self, data_grid):
        """
        Test filters on both properties and as separate argument.
        Wanted behaviour is to ignore the filter on the property
        """
        data_grid["properties"] = {
            "PORO": {"name": "reek_sim_poro.roff", "range": [0.2, 0.4]},
        }
        data_grid["filters"] = {
            "reek_sim_poro.roff": {
                "range": [0.15, 0.25],
            }
        }
        pdf = GridProps2df(data=data_grid, project=None, xtgdata=QCData())

        assert pdf.dataframe["PORO"].mean() == pytest.approx(0.2027, abs=0.001)
        assert pdf.dataframe["PORO"].min() > 0.15
        assert pdf.dataframe["PORO"].max() < 0.25

    def test_codenames(self, data_grid):
        """Test modifying codenames on selectors"""

        data_grid["selectors"] = {
            "ZONE": {"name": "reek_sim_zone.roff", "codes": {1: "TOP", 2: "MID"}},
            "FACIES": {
                "name": "reek_sim_facies2.roff",
                "codes": {1: "SAND", 2: "SAND"},
            },
        }

        pdf = GridProps2df(data=data_grid, project=None, xtgdata=QCData())

        assert {"TOP", "MID", "Below_Low_reek"} == {
            x for x in list(pdf.dataframe["ZONE"].unique()) if x is not None
        }

        assert {"SAND", "SHALE"} == {
            x for x in list(pdf.dataframe["FACIES"].unique()) if x is not None
        }


class TestStatistics:
    """Tests for extracting statistics with QCProperties"""

    def test_gridprops(self, data_grid):
        """Test extracting statsitics from grid properties"""

        qcp = QCProperties()
        qcp.get_grid_statistics(data_grid)

        assert set(qcp.dataframe["PROPERTY"].unique()) == {"PORO", "PERM"}

        row = qcp.dataframe[
            (qcp.dataframe["ZONE"] == "Total")
            & (qcp.dataframe["FACIES"] == "Total")
            & (qcp.dataframe["PROPERTY"] == "PORO")
        ]
        assert row["Avg"].values == pytest.approx(0.1677, abs=0.001)
        assert row["Max"].values == pytest.approx(0.3613, abs=0.001)

    def test_wells(self, data_wells):
        """Test extracting statsitics from well logs"""
        qcp = QCProperties()
        qcp.get_well_statistics(data_wells)

        assert set(qcp.dataframe["PROPERTY"].unique()) == {"PORO", "PERM"}
        assert set(qcp.dataframe["ZONE"].unique()) == {
            "Above_TopUpperReek",
            "Below_TopLowerReek",
            "Below_TopMidReek",
            "Below_TopUpperReek",
            "Below_BaseLowerReek",
            "Total",
        }

        row = qcp.dataframe[
            (qcp.dataframe["ZONE"] == "Total")
            & (qcp.dataframe["FACIES"] == "Total")
            & (qcp.dataframe["PROPERTY"] == "PORO")
        ]
        assert row["Avg"].values == pytest.approx(0.1539, abs=0.001)
        assert row["Max"].values == pytest.approx(0.3661, abs=0.001)

    def test_blockedwells(self, data_bwells):
        """Test extracting statsitics from blocked well logs"""
        qcp = QCProperties()
        qcp.get_bwell_statistics(data_bwells)

        assert list(qcp.dataframe["PROPERTY"].unique()) == ["PORO"]

        row = qcp.dataframe[
            (qcp.dataframe["FACIES"] == "Total") & (qcp.dataframe["PROPERTY"] == "PORO")
        ]
        assert row["Avg"].values == pytest.approx(0.1709, abs=0.001)
        assert row["Max"].values == pytest.approx(0.3640, abs=0.001)

    def test_continous_properties(self, data_grid):
        """Test extracting statsitics on continous properties"""
        qcp = QCProperties()
        qcp.get_grid_statistics(data_grid)

        assert set(qcp.dataframe.columns) == {
            "Avg_Weighted",
            "Avg",
            "Count",
            "FACIES",
            "Max",
            "Min",
            "P10",
            "P90",
            "PROPERTY",
            "Stddev",
            "ZONE",
            "SOURCE",
            "ID",
        }
        assert qcp._proptypes_all[0] == "CONT"

    def test_discrete_properties(self, data_grid):
        """Test extracting statsitics on discrete properties"""
        data_grid["properties"] = {
            "FACIES": {"name": "reek_sim_facies2.roff"},
        }
        data_grid["selectors"] = {
            "ZONE": {"name": "reek_sim_zone.roff"},
        }

        qcp = QCProperties()
        qcp.get_grid_statistics(data_grid)

        assert set(qcp.dataframe.columns) == {
            "Avg_Weighted",
            "Avg",
            "Count",
            "FACIES",
            "PROPERTY",
            "ZONE",
            "SOURCE",
            "ID",
        }
        assert qcp._proptypes_all[0] == "DISC"
        assert list(qcp.dataframe["PROPERTY"].unique()) == ["FACIES"]
        assert set(qcp.dataframe["FACIES"].unique()) == {
            "FINESAND",
            "COARSESAND",
            "SHALE",
        }
        row = qcp.dataframe[
            (qcp.dataframe["ZONE"] == "Total") & (qcp.dataframe["FACIES"] == "FINESAND")
        ]
        assert row["Avg"].values == pytest.approx(0.4024, abs=0.001)

    def test_set_id(self, data_grid):
        """Test extracting statsitics on continous properties"""
        data_grid["name"] = "Test_case"

        qcp = QCProperties()
        qcp.get_grid_statistics(data_grid)
        assert list(qcp.dataframe["ID"].unique()) == ["Test_case"]

        qcp.get_grid_statistics(data_grid)
        assert qcp.dataframe["ID"].unique().tolist() == ["Test_case", "Test_case(1)"]

    def test_no_selectors(self, data_grid):
        """Test running without selectors"""
        data_grid.pop("selectors", None)

        qcp = QCProperties()
        qcp.get_grid_statistics(data_grid)

        assert len(qcp.dataframe) == 2
        assert qcp.dataframe[qcp.dataframe["PROPERTY"] == "PORO"][
            "Avg"
        ].values == pytest.approx(0.1677, abs=0.001)

    def test_no_selector_combos(self, data_grid):
        """Test running without selector_combos"""
        data_grid["selector_combos"] = False

        qcp = QCProperties()
        qcp.get_grid_statistics(data_grid)

        assert list(
            qcp.dataframe[qcp.dataframe["ZONE"] == "Total"]["FACIES"].unique()
        ) == ["Total"]

    def test_multiple_filters(self, data_grid):
        """Test running two statistics extractions using multiple_filters"""
        data_grid.pop("selectors", None)
        data_grid["multiple_filters"] = {
            "test1": {
                "reek_sim_facies2.roff": {
                    "include": ["SHALE"],
                }
            },
            "test2": {
                "reek_sim_facies2.roff": {
                    "exclude": ["SHALE"],
                }
            },
        }
        qcp = QCProperties()
        qcp.get_grid_statistics(data_grid)

        assert {"test1", "test2"} == set(qcp.dataframe["ID"].unique())
        assert qcp.dataframe[
            (qcp.dataframe["PROPERTY"] == "PORO") & (qcp.dataframe["ID"] == "test1")
        ]["Avg"].values == pytest.approx(0.1183, abs=0.001)

    def test_read_eclipse_init(self, data_grid):
        """Test reading property from INIT-file"""
        data_grid["grid"] = "REEK.EGRID"
        data_grid["properties"] = {
            "PORO": {"name": "PORO", "pfile": "REEK.INIT"},
            "PERM": {"name": "PERMX", "pfile": "REEK.INIT"},
        }
        data_grid["selectors"] = {
            "REGION": {"name": "FIPNUM", "pfile": "REEK.INIT"},
        }

        qcp = QCProperties()
        qcp.get_grid_statistics(data_grid)

        assert list(qcp.dataframe["ID"].unique()) == ["REEK"]
        assert qcp.dataframe[
            (qcp.dataframe["PROPERTY"] == "PORO") & (qcp.dataframe["REGION"] == "2")
        ]["Avg"].values == pytest.approx(0.1661, abs=0.001)


class TestStatisticsMultipleSources:
    """Tests for extracting statistics from different sources"""

    def test_auto_combination(self, data_grid, data_wells, data_bwells):
        """Tests combining statistic"""
        qcp = QCProperties()

        qcp.get_grid_statistics(data_grid)
        assert len(qcp.dataframe["ID"].unique()) == 1

        qcp.get_well_statistics(data_wells)
        assert len(qcp.dataframe["ID"].unique()) == 2

        qcp.get_bwell_statistics(data_bwells)
        assert len(qcp.dataframe["ID"].unique()) == 3

    def test_from_yaml(self, testdata_path, tmp_path):
        """Tests extracting statistics from yaml-file"""
        qcp = QCProperties()
        yaml_input = Path(__file__).parent / "data/propstat.yml"
        try:
            qcp.from_yaml(yaml_input)
        except IOError:
            # xtgeo-testdata could be placed at a custom path set in
            # 'XTG_TESTPATH' environment variable or pytest --testdatapath"

            with open(yaml_input, "r") as f:
                yaml_doc = yaml.safe_load(f)
            custom_testdata_path = str(testdata_path)
            custom_grid_path = str(yaml_doc["common_grid_data"]["path"]).replace(
                "../xtgeo-testdata", custom_testdata_path
            )
            custom_well_path = str(yaml_doc["common_well_data"]["path"]).replace(
                "../xtgeo-testdata", custom_testdata_path
            )
            custom_bwell_path = str(yaml_doc["common_bwell_data"]["path"]).replace(
                "../xtgeo-testdata", custom_testdata_path
            )

            yaml_doc["common_grid_data"]["path"] = custom_grid_path
            yaml_doc["common_well_data"]["path"] = custom_well_path
            yaml_doc["common_bwell_data"]["path"] = custom_bwell_path
            for grid_cell in yaml_doc["grid"]:
                grid_cell["path"] = custom_grid_path
            for well_cell in yaml_doc["wells"]:
                well_cell["path"] = custom_well_path
            for blocked_well_cell in yaml_doc["blockedwells"]:
                blocked_well_cell["path"] = custom_bwell_path

            run_pwd = os.getcwd()
            os.chdir(tmp_path)

            os.mkdir("data")
            yaml_tmp_path = Path(tmp_path) / "data/propstat.yml"
            with open(yaml_tmp_path, "w") as f:
                yaml.dump(yaml_doc, f)

            os.chdir(run_pwd)

            qcp.from_yaml(yaml_tmp_path)
