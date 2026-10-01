import logging
from pathlib import Path

import numpy as np
import pytest
from pydantic import ValidationError

from fmu.tools.swmodel import _compute, swmodel
from fmu.tools.swmodel._config import SwConfig
from fmu.tools.swmodel._io import FileBackend

from .conftest import DummyGrid, DummyGridProperty, patch_file_io_and_swfunc


def _restore_logger_state(
    logger_name: str,
    *,
    level: int,
    propagate: bool,
    handlers: list[tuple[logging.Handler, int, logging.Formatter | None]],
) -> None:
    logger = logging.getLogger(logger_name)
    logger.handlers = [handler for handler, _level, _formatter in handlers]
    for handler, handler_level, formatter in handlers:
        handler.setLevel(handler_level)
        handler.setFormatter(formatter)
    logger.setLevel(level)
    logger.propagate = propagate


def test_compute_sw_smoke(
    monkeypatch: pytest.MonkeyPatch, make_valid_config_dict
) -> None:
    cfg = SwConfig(**make_valid_config_dict())
    patch_file_io_and_swfunc(monkeypatch, lambda shape: np.full(shape, 0.5))

    grid, gridprops = FileBackend(cfg).load_grid_and_properties()
    sw, sw_h, swl = _compute.compute_sw(grid, gridprops, cfg)

    assert swl is None
    assert sw.name == "sw"
    assert sw_h.name == "sw_hcenter"
    assert sw.values.shape == (2, 2, 2)
    assert np.allclose(sw.values, 0.5)


def test_compute_oil_only_end_to_end(
    monkeypatch: pytest.MonkeyPatch, make_valid_config_dict
) -> None:
    cfg_dict = make_valid_config_dict()
    cfg_dict["gridparameter"]["goc"] = None
    cfg_dict["gridparameter"]["fwlwg"] = None
    cfg_dict["sw_functions"]["Channel"].pop("gas")
    cfg = SwConfig(**cfg_dict)

    captured: dict[str, np.ndarray] = {}
    patch_file_io_and_swfunc(
        monkeypatch,
        lambda shape: np.full(shape, 0.25),
        fwl_value=111.0,
        capture=captured,
    )

    grid, gridprops = FileBackend(cfg).load_grid_and_properties()
    _gridname, props = _compute.compute(
        cfg,
        grid=grid,
        gridprops=gridprops,
        output_all=True,
    )

    assert set(props) == {"sw", "sw_h", "so", "sg"}
    assert np.allclose(captured["ffl"], 111.0)
    assert np.allclose(props["sw"].values, 0.25)
    assert np.allclose(props["so"].values, 0.75)
    assert np.allclose(props["sg"].values, 0.0)


def test_compute_gas_only_end_to_end(
    monkeypatch: pytest.MonkeyPatch, make_valid_config_dict
) -> None:
    cfg_dict = make_valid_config_dict()
    cfg_dict["gridparameter"]["fwl"] = None
    cfg_dict["sw_functions"]["Channel"].pop("oil")
    cfg = SwConfig(**cfg_dict)

    captured: dict[str, np.ndarray] = {}
    patch_file_io_and_swfunc(
        monkeypatch,
        lambda shape: np.full(shape, 0.25),
        fwlwg_value=-999.0,
        capture=captured,
    )

    grid, gridprops = FileBackend(cfg).load_grid_and_properties()
    _gridname, props = _compute.compute(
        cfg,
        grid=grid,
        gridprops=gridprops,
        output_all=True,
    )

    assert set(props) == {"sw", "sw_h", "so", "sg"}
    assert np.allclose(captured["ffl"], -999.0)
    assert np.allclose(props["sw"].values, 0.25)
    assert np.allclose(props["so"].values, 0.0)
    assert np.allclose(props["sg"].values, 0.75)


def test_compute_api(monkeypatch: pytest.MonkeyPatch, make_valid_config_dict) -> None:
    cfg = SwConfig(**make_valid_config_dict())
    dummy_grid = DummyGrid((2, 2, 2))
    dummy_sw = DummyGridProperty("sw", (2, 2, 2), values=np.full((2, 2, 2), 0.2))
    dummy_sw_h = DummyGridProperty("sw_hcenter", (2, 2, 2))

    def fake_compute_sw(grid, gridprops, cfg, **_kwargs):
        _ = (grid, gridprops, cfg)
        return dummy_sw, dummy_sw_h, None

    def fake_compute_so_sg(*_args, **_kwargs):
        so = DummyGridProperty("so", (2, 2, 2))
        sg = DummyGridProperty("sg", (2, 2, 2))
        return so, sg

    monkeypatch.setattr(_compute, "compute_sw", fake_compute_sw)
    monkeypatch.setattr(_compute, "compute_so_sg", fake_compute_so_sg)

    gridname, props = _compute.compute(
        cfg,
        grid=dummy_grid,
        gridprops={"poro": DummyGridProperty("poro", (2, 2, 2))},
        output_all=True,
    )

    assert gridname == "dummy_grid"
    assert set(props) == {"sw", "sw_h", "so", "sg"}


def test_compute_reuses_grid_z_values(
    monkeypatch: pytest.MonkeyPatch, make_valid_config_dict
) -> None:
    cfg = SwConfig(**make_valid_config_dict())
    shape = (2, 2, 2)

    class CountingGrid(DummyGrid):
        def __init__(self, shape: tuple[int, int, int]):
            super().__init__(shape)
            self.get_xyz_calls = 0

        def get_xyz(self, asmasked: bool = True):
            self.get_xyz_calls += 1
            return super().get_xyz(asmasked=asmasked)

    class FakeSwFunction:
        def __init__(self, *args, **kwargs):
            _ = (args, kwargs)

        def compute(self, compute_method: str):
            _ = compute_method
            return {
                "SW": DummyGridProperty("SW", shape, values=np.full(shape, 0.25)),
                "HCENTER": DummyGridProperty("HCENTER", shape, values=np.zeros(shape)),
            }

    grid = CountingGrid(shape)
    region = DummyGridProperty(
        "swfunction_region", shape, values=np.zeros(shape, dtype=int)
    )
    region.codes = {0: "Channel"}
    gridprops = {
        "swfunction_region": region,
        "poro": DummyGridProperty("poro", shape, values=np.full(shape, 0.2)),
        "perm": DummyGridProperty("perm", shape, values=np.full(shape, 100.0)),
        "fwl": DummyGridProperty("fwl", shape, values=np.full(shape, 111.0)),
        "goc": DummyGridProperty("goc", shape, values=np.full(shape, 3.0)),
        "fwlwg": DummyGridProperty("fwlwg", shape, values=np.full(shape, -999.0)),
    }

    monkeypatch.setattr(_compute, "SwFunction", FakeSwFunction)

    _gridname, props = _compute.compute(
        cfg,
        grid=grid,
        gridprops=gridprops,
        output_all=True,
    )

    assert set(props) == {"sw", "sw_h", "so", "sg"}
    assert grid.get_xyz_calls == 1


def test_main_creates_output_folder(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, make_valid_config_dict
) -> None:
    outfolder = tmp_path / "does" / "not" / "exist"

    monkeypatch.setattr(
        swmodel,
        "load_swconfig",
        lambda *_a, **_k: SwConfig(**make_valid_config_dict()),
    )
    monkeypatch.setattr(
        FileBackend,
        "load_grid_and_properties",
        lambda self: (
            DummyGrid((2, 2, 2)),
            {"poro": DummyGridProperty("poro", (2, 2, 2))},
        ),
    )
    monkeypatch.setattr(
        swmodel,
        "compute",
        lambda *_a, **_k: (
            "MYGRID",
            {
                "sw": DummyGridProperty("sw", (2, 2, 2)),
                "sw_h": DummyGridProperty("sw_h", (2, 2, 2)),
            },
        ),
    )
    monkeypatch.setattr(
        "sys.argv",
        ["swmodel", str(tmp_path / "cfg.yaml"), "--output_folder", str(outfolder)],
    )

    swmodel.main()

    assert (outfolder / "mygrid--sw.roff").exists()
    assert (outfolder / "mygrid--sw_h.roff").exists()


def test_file_backend_write_logs_individual_files(
    tmp_path: Path,
    make_valid_config_dict,
    caplog: pytest.LogCaptureFixture,
) -> None:
    backend = FileBackend(SwConfig(**make_valid_config_dict()))
    outfolder = tmp_path / "results"
    props = {
        "sw": DummyGridProperty("sw", (1, 1, 1)),
        "sw_h": DummyGridProperty("sw_hcenter", (1, 1, 1)),
    }

    with caplog.at_level("INFO", logger="fmu.tools.swmodel._io"):
        backend.write("MYGRID", props, outfolder)

    assert "Write swmodel properties to" in caplog.text
    assert f"Wrote swmodel file {outfolder / 'mygrid--sw.roff'}" in caplog.text
    assert f"Wrote swmodel file {outfolder / 'mygrid--sw_h.roff'}" in caplog.text


def test_main_wraps_validation_error_with_key_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config_file = tmp_path / "cfg.yaml"
    # Deliberately omit swfunction_region so validation fails after resolving key_path.
    config_file.write_text(
        "\n".join(
            [
                "nested:",
                "  swmodel:",
                "    grid: Geogrid",
                "    gridparameter:",
                "      poro: PORO",
                "      perm: PERM",
                "      fwl: FWL",
                "      goc: GOC",
                "      fwlwg: FWLWG",
                "    sw_functions:",
                "      Channel:",
                "        oil:",
                "          a: 4.5",
                "          b: -2.2",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "swmodel",
            str(config_file),
            "--key_path",
            "nested.swmodel",
        ],
    )

    with pytest.raises(
        RuntimeError,
        match="Invalid SwConfig in .*\\(key_path='nested.swmodel'\\)",
    ) as excinfo:
        swmodel.main()

    assert isinstance(excinfo.value.__cause__, ValidationError)


def test_configure_logging_suppresses_xtgeo_info_by_default() -> None:
    logger_names = [
        "fmu.tools.swmodel",
        "fmu.tools.properties.swfunction",
        "xtgeo",
    ]
    saved: dict[
        str,
        tuple[
            int,
            bool,
            list[tuple[logging.Handler, int, logging.Formatter | None]],
        ],
    ] = {}
    for logger_name in logger_names:
        current_logger = logging.getLogger(logger_name)
        saved[logger_name] = (
            current_logger.level,
            current_logger.propagate,
            [
                (handler, handler.level, handler.formatter)
                for handler in current_logger.handlers
            ],
        )

    try:
        swmodel._configure_logging()
        assert logging.getLogger("fmu.tools.swmodel").level == logging.INFO
        assert logging.getLogger("fmu.tools.swmodel").propagate is False
        assert (
            logging.getLogger("fmu.tools.properties.swfunction").level == logging.INFO
        )
        assert logging.getLogger("xtgeo").level == logging.WARNING

        swmodel._configure_logging(debug=True)
        assert logging.getLogger("fmu.tools.swmodel").level == logging.DEBUG
        assert (
            logging.getLogger("fmu.tools.properties.swfunction").level == logging.DEBUG
        )
        assert logging.getLogger("xtgeo").level == logging.DEBUG
    finally:
        for logger_name in logger_names:
            level, propagate, handlers = saved[logger_name]
            _restore_logger_state(
                logger_name,
                level=level,
                propagate=propagate,
                handlers=handlers,
            )


def test_clip_swl_physical_bounds() -> None:
    swl = DummyGridProperty("swl", (2, 2), values=np.array([[-0.2, 0.5], [1.3, 0.9]]))
    _compute.clip_swl(swl, None, None)
    assert swl.values.min() >= 0.0
    assert swl.values.max() <= 1.0


def test_clip_swl_user_bounds() -> None:
    swl = DummyGridProperty("swl", (2, 2), values=np.array([[0.01, 0.5], [0.95, 0.2]]))
    _compute.clip_swl(swl, 0.05, 0.7)
    assert swl.values.min() >= 0.05
    assert swl.values.max() <= 0.7


def test_clip_swl_returns_same_object() -> None:
    swl = DummyGridProperty("swl", (2,), values=np.array([0.5]))
    assert _compute.clip_swl(swl, None, None) is swl


def test_clip_swl_preserves_mask() -> None:
    arr = np.ma.masked_array([0.5, 2.0], mask=[True, False])
    swl = DummyGridProperty("swl", (2,), values=arr)
    _compute.clip_swl(swl, None, None)
    assert np.ma.getmaskarray(swl.values)[0]
    assert swl.values[1] == 1.0


def test_compute_sw_func_parameters_preserves_poro_mask(
    make_valid_config_dict,
) -> None:
    cfg_dict = make_valid_config_dict()
    cfg_dict["gridparameter"]["goc"] = None
    cfg_dict["gridparameter"]["fwlwg"] = None
    cfg_dict["sw_functions"]["Channel"].pop("gas")
    cfg = SwConfig(**cfg_dict)
    shape = (2, 2, 2)
    mask = np.array([False, True, False, False, False, False, False, False]).reshape(
        shape
    )
    grid = DummyGrid(shape)
    region = DummyGridProperty(
        "swfunction_region",
        shape,
        values=np.ma.array(np.zeros(shape, dtype=int), mask=mask),
    )
    region.codes = {0: "Channel"}
    poro = DummyGridProperty(
        "poro",
        shape,
        values=np.ma.array(np.full(shape, 0.2), mask=mask),
    )

    a, b, swirr = _compute.compute_sw_func_parameters(
        grid,
        {"swfunction_region": region, "poro": poro},
        cfg,
        {"oil"},
    )

    assert np.ma.getmaskarray(a.values)[0, 0, 1]
    assert np.ma.getmaskarray(b.values)[0, 0, 1]
    assert np.ma.getmaskarray(swirr.values)[0, 0, 1]


@pytest.mark.parametrize(
    ("swl_min", "swl_max", "expected_lo", "expected_hi"),
    [
        (0.05, None, 0.05, 1.0),
        (None, 0.7, 0.0, 0.7),
        (0.05, 0.7, 0.05, 0.7),
        (None, None, 0.0, 1.0),
    ],
)
def test_compute_sw_swl_bounds_paths(
    monkeypatch: pytest.MonkeyPatch,
    make_valid_config_dict,
    swl_min,
    swl_max,
    expected_lo,
    expected_hi,
) -> None:
    cfg_dict = make_valid_config_dict()
    cfg_dict["swl_height"] = 300
    if swl_min is not None:
        cfg_dict["swl_min"] = swl_min
    if swl_max is not None:
        cfg_dict["swl_max"] = swl_max
    cfg = SwConfig(**cfg_dict)

    def sw_values(shape):
        vals = np.full(shape, 0.9)
        vals.flat[0] = -0.3
        vals.flat[1] = 0.01
        return vals

    patch_file_io_and_swfunc(monkeypatch, sw_values)
    grid, gridprops = FileBackend(cfg).load_grid_and_properties()
    _sw, _sw_h, swl = _compute.compute_sw(grid, gridprops, cfg)

    assert swl is not None
    assert swl.name == "swl"
    assert swl.values.min() >= expected_lo
    assert swl.values.max() <= expected_hi


def test_compute_so_sg_goc_boundary_convention(make_valid_config_dict) -> None:
    cfg = SwConfig(**make_valid_config_dict())
    shape = (2, 2, 2)
    grid = DummyGrid(shape)
    goc = DummyGridProperty("goc", shape, values=np.full(shape, 3.0))
    sw = DummyGridProperty("sw", shape, values=np.full(shape, 0.25))

    so, sg = _compute.compute_so_sg(grid=grid, gridprops={"goc": goc}, sw=sw, cfg=cfg)

    so_flat = so.values.reshape(-1)
    sg_flat = sg.values.reshape(-1)
    for i in (0, 1, 2):
        assert sg_flat[i] == pytest.approx(0.75)
        assert so_flat[i] == pytest.approx(0.0)
    for i in (3, 4, 5, 6, 7):
        assert so_flat[i] == pytest.approx(0.75)
        assert sg_flat[i] == pytest.approx(0.0)

    assert so_flat[3] == pytest.approx(0.75)
    assert sg_flat[3] == pytest.approx(0.0)
    assert np.allclose(sw.values + so.values + sg.values, 1.0)


def test_compute_so_sg_preserves_mask_for_single_phase(
    make_valid_config_dict,
) -> None:
    cfg_dict = make_valid_config_dict()
    cfg_dict["gridparameter"]["goc"] = None
    cfg_dict["gridparameter"]["fwlwg"] = None
    cfg_dict["sw_functions"]["Channel"].pop("gas")
    cfg = SwConfig(**cfg_dict)
    shape = (2, 2, 2)
    grid = DummyGrid(shape)
    sw = DummyGridProperty(
        "sw",
        shape,
        values=np.ma.array(
            np.full(shape, 0.25),
            mask=np.array(
                [False, True, False, False, False, False, False, False]
            ).reshape(shape),
        ),
    )

    so, sg = _compute.compute_so_sg(grid=grid, gridprops={}, sw=sw, cfg=cfg)

    assert np.ma.getmaskarray(so.values)[0, 0, 1]
    assert np.ma.getmaskarray(sg.values)[0, 0, 1]


def test_compute_sw_ffl_boundary_uses_fwl_at_goc(
    monkeypatch: pytest.MonkeyPatch, make_valid_config_dict
) -> None:
    cfg = SwConfig(**make_valid_config_dict())

    captured: dict[str, np.ndarray] = {}
    patch_file_io_and_swfunc(
        monkeypatch,
        lambda shape: np.full(shape, 0.5),
        fwl_value=111.0,
        fwlwg_value=-999.0,
        goc_value=3.0,
        capture=captured,
    )

    grid, gridprops = FileBackend(cfg).load_grid_and_properties()
    _compute.compute_sw(grid, gridprops, cfg)

    ffl = captured["ffl"]
    assert ffl[2] == pytest.approx(-999.0)
    assert ffl[3] == pytest.approx(111.0)
    assert ffl[4] == pytest.approx(111.0)


def test_compute_sw_swl_height_preserves_mask(
    monkeypatch: pytest.MonkeyPatch, make_valid_config_dict
) -> None:
    cfg_dict = make_valid_config_dict()
    cfg_dict["swl_height"] = 300.0
    cfg = SwConfig(**cfg_dict)
    shape = (2, 2, 2)
    capture: dict[str, np.ma.MaskedArray] = {}
    call_count = 0

    class CapturingSwFunction:
        def __init__(
            self, grid, x, ffl, a, b, invert, swira, method, htop, hcenter, hbot
        ):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                capture["swl_h"] = np.ma.array(hcenter.values, copy=True)
            _ = (grid, x, ffl, a, b, invert, swira, method, htop, hbot)

        def compute(self, compute_method: str):
            _ = compute_method
            hcenter = DummyGridProperty(
                "HCENTER",
                shape,
                values=np.ma.array(
                    np.zeros(shape),
                    mask=np.array(
                        [False, True, False, False, False, False, False, False]
                    ).reshape(shape),
                ),
            )
            return {
                "SW": DummyGridProperty("SW", shape, values=np.full(shape, 0.25)),
                "HCENTER": hcenter,
            }

    grid = DummyGrid(shape)
    region = DummyGridProperty(
        "swfunction_region", shape, values=np.zeros(shape, dtype=int)
    )
    region.codes = {0: "Channel"}
    gridprops = {
        "swfunction_region": region,
        "poro": DummyGridProperty("poro", shape, values=np.full(shape, 0.2)),
        "perm": DummyGridProperty("perm", shape, values=np.full(shape, 100.0)),
        "fwl": DummyGridProperty("fwl", shape, values=np.full(shape, 111.0)),
        "goc": DummyGridProperty("goc", shape, values=np.full(shape, 3.0)),
        "fwlwg": DummyGridProperty("fwlwg", shape, values=np.full(shape, -999.0)),
    }

    monkeypatch.setattr(_compute, "SwFunction", CapturingSwFunction)
    _compute.compute_sw(grid, gridprops, cfg)

    swl_h = capture["swl_h"].reshape(-1)
    assert np.ma.getmaskarray(swl_h)[1]
    assert swl_h[0] == pytest.approx(300.0)


def test_compute_sw_preserves_masked_ffl_selection(
    monkeypatch: pytest.MonkeyPatch, make_valid_config_dict
) -> None:
    cfg = SwConfig(**make_valid_config_dict())
    shape = (2, 2, 2)
    capture: dict[str, np.ma.MaskedArray] = {}

    class MaskedZGrid(DummyGrid):
        def get_xyz(self, asmasked: bool = True):
            _ = asmasked
            nz, ny, nx = self._shape
            z = np.arange(nz * ny * nx).reshape(self._shape).astype(float)
            z = np.ma.array(
                z,
                mask=np.array(
                    [False, True, False, False, False, False, False, False]
                ).reshape(self._shape),
            )
            x = np.zeros_like(z)
            y = np.zeros_like(z)

            class DummyZ:
                def __init__(self, values):
                    self.values = values

            return x, y, DummyZ(z)

    class CapturingSwFunction:
        def __init__(
            self, grid, x, ffl, a, b, invert, swira, method, htop, hcenter, hbot
        ):
            capture["ffl"] = np.ma.array(ffl.values, copy=True)
            _ = (grid, x, a, b, invert, swira, method, htop, hcenter, hbot)

        def compute(self, compute_method: str):
            _ = compute_method
            return {
                "SW": DummyGridProperty("SW", shape, values=np.full(shape, 0.25)),
                "HCENTER": DummyGridProperty("HCENTER", shape, values=np.zeros(shape)),
            }

    grid = MaskedZGrid(shape)
    region = DummyGridProperty(
        "swfunction_region", shape, values=np.zeros(shape, dtype=int)
    )
    region.codes = {0: "Channel"}
    gridprops = {
        "swfunction_region": region,
        "poro": DummyGridProperty("poro", shape, values=np.full(shape, 0.2)),
        "perm": DummyGridProperty("perm", shape, values=np.full(shape, 100.0)),
        "fwl": DummyGridProperty("fwl", shape, values=np.full(shape, 111.0)),
        "goc": DummyGridProperty("goc", shape, values=np.full(shape, 3.0)),
        "fwlwg": DummyGridProperty("fwlwg", shape, values=np.full(shape, -999.0)),
    }

    monkeypatch.setattr(_compute, "SwFunction", CapturingSwFunction)
    _compute.compute_sw(grid, gridprops, cfg)

    ffl = capture["ffl"].reshape(-1)
    assert np.ma.getmaskarray(ffl)[1]
    assert ffl[0] == pytest.approx(-999.0)
    assert ffl[3] == pytest.approx(111.0)
