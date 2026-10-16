from pathlib import Path

import pytest
from pydantic import ValidationError

from fmu.tools.swmodel._config import JFunction, PhaseJFunction, SwConfig


def test_swconfig_valid(make_valid_config_dict) -> None:
    cfg_dict = make_valid_config_dict()
    cfg = SwConfig(**cfg_dict)

    assert Path(cfg.grid).exists()
    assert "Channel" in cfg.sw_functions
    assert cfg.algorithm.method == "truncated_cell_corners_above_ffl"
    assert cfg.phase_types == {"oil", "gas"}


def test_swconfig_gas_missing_contacts_gridparameter_level(
    make_valid_config_dict,
) -> None:
    cfg_dict = make_valid_config_dict()
    cfg_dict["gridparameter"]["goc"] = None

    with pytest.raises(ValueError) as excinfo:
        SwConfig(**cfg_dict)

    msg = str(excinfo.value)
    assert "goc and fwlwg must either both be provided or both be None" in msg


def test_swconfig_gas_missing_contacts_swconfig_level(make_valid_config_dict) -> None:
    cfg_dict = make_valid_config_dict()
    cfg_dict["gridparameter"]["goc"] = None
    cfg_dict["gridparameter"]["fwlwg"] = None

    with pytest.raises(ValueError) as excinfo:
        SwConfig(**cfg_dict)

    assert "Gas J-functions present but goc/fwlwg parameters are missing" in str(
        excinfo.value
    )


def test_swconfig_oil_missing_fwl(make_valid_config_dict) -> None:
    cfg_dict = make_valid_config_dict()
    cfg_dict["gridparameter"]["fwl"] = None

    with pytest.raises(ValueError) as excinfo:
        SwConfig(**cfg_dict)

    assert "Oil J-functions present but no fwl parameter provided" in str(excinfo.value)


def test_swconfig_integrated_rejects_b_minus_one(make_valid_config_dict) -> None:
    cfg_dict = make_valid_config_dict()
    cfg_dict["algorithm"]["calc"] = "integrated"
    cfg_dict["sw_functions"]["Channel"]["oil"]["b"] = -1.0

    with pytest.raises(
        ValidationError,
        match="algorithm.calc='integrated' does not support J-functions with b = -1.0",
    ) as excinfo:
        SwConfig(**cfg_dict)

    assert "Channel.oil" in str(excinfo.value)


def test_swconfig_direct_allows_b_minus_one(make_valid_config_dict) -> None:
    cfg_dict = make_valid_config_dict()
    cfg_dict["sw_functions"]["Channel"]["oil"]["b"] = -1.0

    cfg = SwConfig(**cfg_dict)

    assert cfg.sw_functions["Channel"].oil is not None
    assert cfg.sw_functions["Channel"].oil.b == -1.0


def test_swconfig_rejects_mixed_phase_sets_across_regions(
    make_valid_config_dict,
) -> None:
    cfg_dict = make_valid_config_dict()
    cfg_dict["sw_functions"]["Barrier"] = {"oil": {"a": 4.1, "b": -2.0, "swirr": 0.0}}

    with pytest.raises(
        ValidationError,
        match="All sw_functions groups must define the same phase set",
    ) as excinfo:
        SwConfig(**cfg_dict)

    assert "Barrier (oil)" in str(excinfo.value)


def test_jfunction_requires_at_least_one_phase() -> None:
    with pytest.raises(ValidationError):
        JFunction()

    JFunction(oil=PhaseJFunction(a=4.5, b=-2.2, swirr=0.0))
    JFunction(gas=PhaseJFunction(a=3.8, b=-1.9, swirr=0.0))


def test_phasejfunction_swirr_range() -> None:
    with pytest.raises(ValidationError):
        JFunction(oil=PhaseJFunction(a=1.0, b=-1.0, swirr=1.01))

    jf = JFunction(oil=PhaseJFunction(a=1.0, b=-1.0, swirr=-0.01))
    assert jf.oil is not None
    assert jf.oil.swirr == -0.01


def test_phasejfunction_rejects_nonfinite_values() -> None:
    with pytest.raises(ValidationError, match="finite number"):
        JFunction(oil=PhaseJFunction(a=1.0, b=-1.0, swirr=float("nan")))


def test_swconfig_swl_min_gt_max(make_valid_config_dict) -> None:
    cfg_dict = make_valid_config_dict()
    cfg_dict["swl_height"] = 300
    cfg_dict["swl_min"] = 0.8
    cfg_dict["swl_max"] = 0.2
    with pytest.raises(ValidationError, match="swl_min must be <= swl_max"):
        SwConfig(**cfg_dict)


def test_swconfig_swl_bounds_out_of_range(make_valid_config_dict) -> None:
    cfg_dict = make_valid_config_dict()
    cfg_dict["swl_height"] = 300
    cfg_dict["swl_min"] = -0.1
    with pytest.raises(ValidationError):
        SwConfig(**cfg_dict)

    cfg_dict = make_valid_config_dict()
    cfg_dict["swl_height"] = 300
    cfg_dict["swl_max"] = 1.5
    with pytest.raises(ValidationError):
        SwConfig(**cfg_dict)


def test_swconfig_clip_without_swl_warns(
    make_valid_config_dict, caplog: pytest.LogCaptureFixture
) -> None:
    cfg_dict = make_valid_config_dict()
    cfg_dict["swl_min"] = 0.05

    with caplog.at_level("WARNING"):
        SwConfig(**cfg_dict)

    assert "clipping is ignored" in caplog.text
