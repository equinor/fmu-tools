import numpy as np
import pytest
from pydantic import ValidationError

import fmu.tools.swmodel.swmodel as swmodel_module
from fmu.tools.swmodel import run_swmodel
from fmu.tools.swmodel._config import SwConfig
from fmu.tools.swmodel._io import RmsBackend, validate_code_names_vs_cfg_names

from .conftest import (
    DummyGridProperty,
    FakeGridModel,
    FakeProject,
    patch_rms_io_and_swfunc,
)


def _make_rms_config() -> dict:
    return {
        "grid": "Geogrid",
        "gridparameter": {
            "swfunc_region": "SWFUNC_REGION",
            "poro": "PORO",
            "perm": "PERM",
            "fwl": "FWL",
            "goc": "GOC",
            "fwlwg": "FWLWG",
        },
        "sw_functions": {
            "Channel": {
                "oil": {"a": 4.5, "b": -2.2, "swirr": 0.0},
                "gas": {"a": 3.8, "b": -1.9, "swirr": 0.0},
            }
        },
        "output": {
            "sw": "SW_INIT",
            "sw_h": "SW_H_INIT",
            "so": "SO_INIT",
            "sg": "SG_INIT",
        },
    }


def test_run_swmodel_writes_to_rms(monkeypatch: pytest.MonkeyPatch) -> None:
    patch_rms_io_and_swfunc(monkeypatch, lambda shape: np.full(shape, 0.25))
    project = FakeProject(
        {
            "Geogrid": FakeGridModel(
                {"SWFUNC_REGION", "PORO", "PERM", "FWL", "GOC", "FWLWG"}
            )
        }
    )
    project.current_realisation = 7

    props = run_swmodel(project, _make_rms_config(), output_all=True)

    assert set(props) == {"sw", "sw_h", "so", "sg"}
    assert project._grid_from_roxar_calls == [("Geogrid", 7)]
    assert project._gridproperty_from_roxar_calls == [
        ("Geogrid", "SWFUNC_REGION", 7),
        ("Geogrid", "PORO", 7),
        ("Geogrid", "PERM", 7),
        ("Geogrid", "FWL", 7),
        ("Geogrid", "GOC", 7),
        ("Geogrid", "FWLWG", 7),
    ]
    assert project._to_roxar_calls == [
        ("Geogrid", "SW_INIT", "sw", 7),
        ("Geogrid", "SW_H_INIT", "sw_hcenter", 7),
        ("Geogrid", "SO_INIT", "so", 7),
        ("Geogrid", "SG_INIT", "sg", 7),
    ]


def test_run_swmodel_configures_logging(monkeypatch: pytest.MonkeyPatch) -> None:
    patch_rms_io_and_swfunc(monkeypatch, lambda shape: np.full(shape, 0.25))
    project = FakeProject(
        {
            "Geogrid": FakeGridModel(
                {"SWFUNC_REGION", "PORO", "PERM", "FWL", "GOC", "FWLWG"}
            )
        }
    )
    seen: list[bool] = []

    def fake_configure_logging(*, debug: bool = False) -> None:
        seen.append(debug)

    monkeypatch.setattr(swmodel_module, "_configure_logging", fake_configure_logging)

    run_swmodel(project, _make_rms_config())
    run_swmodel(project, _make_rms_config(), debug=True)

    assert seen == [False, True]


def test_run_swmodel_wraps_validation_error_with_key_path() -> None:
    project = FakeProject({})
    # Deliberately omit swfunc_region so validation fails before any RMS I/O.
    config = {
        "swmodel": {
            "geogrid": {
                "grid": "Geogrid",
                "gridparameter": {
                    "poro": "PORO",
                    "perm": "PERM",
                    "fwl": "FWL",
                    "goc": "GOC",
                    "fwlwg": "FWLWG",
                },
                "sw_functions": {
                    "Channel": {
                        "oil": {"a": 4.5, "b": -2.2, "swirr": 0.0},
                    }
                },
            }
        }
    }

    with pytest.raises(
        RuntimeError,
        match="Invalid SwConfig from provided mapping "
        r"\(key_path='swmodel\.geogrid'\)",
    ) as excinfo:
        run_swmodel(project, config, key_path="swmodel.geogrid")

    assert isinstance(excinfo.value.__cause__, ValidationError)


def test_run_swmodel_reads_nested_mapping_with_key_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    patch_rms_io_and_swfunc(monkeypatch, lambda shape: np.full(shape, 0.25))
    project = FakeProject(
        {
            "Geogrid": FakeGridModel(
                {"SWFUNC_REGION", "PORO", "PERM", "FWL", "GOC", "FWLWG"}
            )
        }
    )
    config = {"swmodel": {"geogrid": _make_rms_config()}}

    props = run_swmodel(project, config, key_path="swmodel.geogrid", output_all=True)

    assert set(props) == {"sw", "sw_h", "so", "sg"}


def test_rms_backend_missing_property_raises() -> None:
    project = FakeProject(
        {"Geogrid": FakeGridModel({"SWFUNC_REGION", "PORO", "FWL", "GOC", "FWLWG"})}
    )

    with pytest.raises(ValueError, match="Property 'PERM' was not found"):
        RmsBackend(project, SwConfig(**_make_rms_config())).load_grid_and_properties()


def test_rms_backend_write_rejects_duplicate_selected_output_names() -> None:
    project = FakeProject({"Geogrid": FakeGridModel(set())})
    config = _make_rms_config()
    config["output"]["so"] = "SW_INIT"
    backend = RmsBackend(project, SwConfig(**config))
    props = {
        "sw": DummyGridProperty("sw", (1, 1, 1)),
        "so": DummyGridProperty("so", (1, 1, 1)),
    }

    with pytest.raises(
        ValueError,
        match="RMS output property names must be unique for the selected outputs",
    ) as excinfo:
        backend.write(props)

    assert "SW_INIT" in str(excinfo.value)
    assert project._to_roxar_calls == []


def test_rms_backend_write_logs_output_targets(
    caplog: pytest.LogCaptureFixture,
) -> None:
    class FakeProperty:
        def __init__(self, name: str):
            self.name = name

        def __eq__(self, other: object) -> bool:
            return isinstance(other, FakeProperty) and self.name == other.name

    project = FakeProject({"Geogrid": FakeGridModel([FakeProperty("SW_INIT")])})
    config = _make_rms_config()
    backend = RmsBackend(project, SwConfig(**config))
    props = {
        "sw": DummyGridProperty("sw", (1, 1, 1)),
        "so": DummyGridProperty("so", (1, 1, 1)),
    }

    with caplog.at_level("INFO", logger="fmu.tools.swmodel._io"):
        backend.write(props)

    assert "Updated RMS parameter 'SW_INIT' in grid model 'Geogrid'" in caplog.text
    assert "Created RMS parameter 'SO_INIT' in grid model 'Geogrid'" in caplog.text


def test_validate_code_names_requires_discrete_code_names() -> None:
    cfg = SwConfig(**_make_rms_config())
    region = type("DummyRegion", (), {"codes": {}})()
    region.values = np.zeros((1, 1, 1), dtype=int)

    with pytest.raises(ValueError, match="does not define any code names"):
        validate_code_names_vs_cfg_names(region, cfg)


def test_validate_code_names_rejects_active_codes_without_names() -> None:
    cfg = SwConfig(**_make_rms_config())
    region = type("DummyRegion", (), {"codes": {1: "Channel"}})()
    region.values = np.array([[[1, 2]]], dtype=int)

    with pytest.raises(ValueError, match=r"uses codes without names: \[2\]"):
        validate_code_names_vs_cfg_names(region, cfg)
