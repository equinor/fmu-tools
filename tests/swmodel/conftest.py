from __future__ import annotations

from functools import partial
from pathlib import Path
from typing import Callable

import numpy as np
import pytest

from fmu.tools.swmodel import _compute, _io


class DummyGridProperty:
    def __init__(self, name: str, shape: tuple[int, ...], values=None):
        self.name = name
        if values is None:
            self.values = np.zeros(shape)
        elif isinstance(values, np.ma.MaskedArray):
            self.values = values
        else:
            self.values = np.array(values)
        self.codes: dict[int, str] = {}

    def copy(self):
        clone = DummyGridProperty(self.name, self.values.shape, self.values.copy())
        clone.codes = dict(self.codes)
        return clone

    def to_file(self, path, **_kwargs):
        Path(path).write_text("dummy", encoding="utf-8")

    def to_roxar(self, project, grid_name, property_name, realisation=0):
        project._to_roxar_calls.append(
            (grid_name, property_name, self.name, realisation)
        )


class DummyGrid:
    def __init__(self, shape: tuple[int, int, int]):
        self._shape = shape
        self.name = "dummy_grid"

    def get_xyz(self, asmasked: bool = True):
        _ = asmasked
        nz, ny, nx = self._shape
        z = np.arange(nz * ny * nx).reshape(self._shape).astype(float)
        x = np.zeros_like(z)
        y = np.zeros_like(z)

        class DummyZ:
            def __init__(self, values):
                self.values = values

        return x, y, DummyZ(z)


class FakeGridModel:
    def __init__(self, properties):
        self.properties = list(properties)


class FakeProject:
    def __init__(self, grid_models: dict[str, FakeGridModel]):
        self.grid_models = grid_models
        self.current_realisation = 0
        self._grid_from_roxar_calls: list[tuple[str, int]] = []
        self._gridproperty_from_roxar_calls: list[tuple[str, str, int]] = []
        self._to_roxar_calls: list[tuple[str, str, str, int]] = []


def _make_dummy_property(
    name: str,
    dummy_shape: tuple[int, int, int],
    fwl_value: float,
    fwlwg_value: float,
    goc_value: float,
) -> DummyGridProperty:
    token = Path(name).stem.lower().split("--")[-1]

    if token in {"swfunction_region", "swfunc_region"}:
        prop = DummyGridProperty(
            "swfunction_region", dummy_shape, values=np.zeros(dummy_shape, dtype=int)
        )
        prop.codes = {0: "Channel"}
        return prop

    specs = {
        "poro": ("poro", 0.2),
        "perm": ("perm", 100.0),
        "fwlwg": ("fwlwg", fwlwg_value),
        "goc": ("goc", goc_value),
        "fwl": ("fwl", fwl_value),
    }
    if token in specs:
        prop_name, fill = specs[token]
        return DummyGridProperty(
            prop_name, dummy_shape, values=np.full(dummy_shape, fill)
        )
    return DummyGridProperty("unknown", dummy_shape)


def _make_fake_swfunction(sw_values_factory, capture: dict | None):
    class FakeSwFunction:
        def __init__(
            self, grid, x, ffl, a, b, invert, swira, method, htop, hcenter, hbot
        ):
            self.x = x
            if capture is not None and "ffl" not in capture:
                capture["ffl"] = np.asarray(ffl.values).reshape(-1).copy()
            _ = (grid, ffl, a, b, invert, swira, method, htop, hcenter, hbot)

        def compute(self, compute_method: str):
            _ = compute_method
            shape = self.x.values.shape
            sw = DummyGridProperty("SW", shape, values=sw_values_factory(shape))
            hcenter = DummyGridProperty("HCENTER", shape, values=np.zeros(shape))
            return {"SW": sw, "HCENTER": hcenter}

    return FakeSwFunction


def patch_file_io_and_swfunc(
    monkeypatch: pytest.MonkeyPatch,
    sw_values_factory,
    dummy_shape: tuple[int, int, int] = (2, 2, 2),
    *,
    fwl_value: float = 0.0,
    fwlwg_value: float = 0.0,
    goc_value: float = 0.0,
    capture: dict | None = None,
) -> None:
    def fake_grid_from_file(_path):
        return DummyGrid(dummy_shape)

    def fake_gridproperty_from_file(path):
        return _make_dummy_property(
            path, dummy_shape, fwl_value, fwlwg_value, goc_value
        )

    monkeypatch.setattr(_io.xtgeo, "grid_from_file", fake_grid_from_file)
    monkeypatch.setattr(
        _io.xtgeo,
        "gridproperty_from_file",
        fake_gridproperty_from_file,
    )
    monkeypatch.setattr(
        _compute, "SwFunction", _make_fake_swfunction(sw_values_factory, capture)
    )


def patch_rms_io_and_swfunc(
    monkeypatch: pytest.MonkeyPatch,
    sw_values_factory,
    dummy_shape: tuple[int, int, int] = (2, 2, 2),
    *,
    fwl_value: float = 0.0,
    fwlwg_value: float = 0.0,
    goc_value: float = 0.0,
    capture: dict | None = None,
) -> None:
    def fake_grid_from_roxar(_project, _grid_name, realisation=0):
        _project._grid_from_roxar_calls.append((_grid_name, realisation))
        return DummyGrid(dummy_shape)

    def fake_gridproperty_from_roxar(_project, _grid_name, prop_name, realisation=0):
        _project._gridproperty_from_roxar_calls.append(
            (_grid_name, prop_name, realisation)
        )
        return _make_dummy_property(
            prop_name, dummy_shape, fwl_value, fwlwg_value, goc_value
        )

    monkeypatch.setattr(_io.xtgeo, "grid_from_roxar", fake_grid_from_roxar)
    monkeypatch.setattr(
        _io.xtgeo, "gridproperty_from_roxar", fake_gridproperty_from_roxar
    )
    monkeypatch.setattr(
        _compute, "SwFunction", _make_fake_swfunction(sw_values_factory, capture)
    )


def _make_valid_config_dict(tmp_path: Path) -> dict:
    grid_file = tmp_path / "grid.roff"
    grid_file.write_text("dummy", encoding="utf-8")
    swfunction_region_file = tmp_path / "swfunction_region.roff"
    swfunction_region_file.write_text("dummy", encoding="utf-8")
    poro_file = tmp_path / "poro.roff"
    poro_file.write_text("dummy", encoding="utf-8")
    perm_file = tmp_path / "perm.roff"
    perm_file.write_text("dummy", encoding="utf-8")
    fwl_file = tmp_path / "fwl.roff"
    fwl_file.write_text("dummy", encoding="utf-8")
    goc_file = tmp_path / "goc.roff"
    goc_file.write_text("dummy", encoding="utf-8")
    fwlwg_file = tmp_path / "fwlwg.roff"
    fwlwg_file.write_text("dummy", encoding="utf-8")

    return {
        "grid": str(grid_file),
        "gridparameter": {
            "swfunction_region": str(swfunction_region_file),
            "poro": str(poro_file),
            "perm": str(perm_file),
            "fwl": str(fwl_file),
            "goc": str(goc_file),
            "fwlwg": str(fwlwg_file),
        },
        "sw_functions": {
            "Channel": {
                "oil": {"a": 4.5, "b": -2.2, "swirr": 0.0},
                "gas": {"a": 3.8, "b": -1.9, "swirr": 0.0},
            }
        },
        "algorithm": {
            "method": "truncated_cell_corners_above_ffl",
            "calc": "direct",
            "epsilon": 1e-9,
            "invert_jfunc": False,
        },
    }


@pytest.fixture
def make_valid_config_dict(tmp_path: Path) -> Callable[[], dict]:
    return partial(_make_valid_config_dict, tmp_path)
