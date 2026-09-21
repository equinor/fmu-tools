from __future__ import annotations

import difflib
import logging
from functools import cached_property
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    NegativeFloat,
    PositiveFloat,
    field_validator,
    model_validator,
)

logger = logging.getLogger(__name__)


class _SwBaseModel(BaseModel):
    """Base model for swmodel configuration."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class GridParameter(_SwBaseModel):
    """Parameter grid paths or RMS property names."""

    swfunc_region: str = Field(
        description="Discrete parameter or RMS property matching sw_functions groups.",
        examples=["path/to/swfunc_region.roff", "SWFUNC_REGION"],
        min_length=1,
    )
    poro: str = Field(
        description="Porosity parameter or RMS property name.",
        examples=["path/to/poro.roff", "PORO"],
        min_length=1,
    )
    perm: str = Field(
        description="Permeability parameter or RMS property name.",
        examples=["path/to/perm.roff", "PERM"],
        min_length=1,
    )
    fwl: str | None = Field(
        default=None,
        description="Free water level parameter or RMS property name.",
        examples=["path/to/fwl.roff", "FWL"],
    )
    goc: str | None = Field(
        default=None,
        description="Gas-oil contact parameter or RMS property name.",
        examples=["path/to/goc.roff", "GOC"],
    )
    fwlwg: str | None = Field(
        default=None,
        description="Water-gas free water level parameter or RMS property name.",
        examples=["path/to/fwlwg.roff", "FWLWG"],
    )

    @model_validator(mode="after")
    def _check_contacts(self) -> GridParameter:
        if self.fwl is None and self.goc is None and self.fwlwg is None:
            raise ValueError("At least one of fwl or goc/fwlwg must be provided.")

        if (self.goc is None) ^ (self.fwlwg is None):
            raise ValueError(
                "goc and fwlwg must either both be provided or both be None "
                "(WG J-function mode requires both)."
            )

        return self


class PhaseJFunction(_SwBaseModel):
    """J-function parameters for a single phase."""

    a: PositiveFloat = Field(description="a-value for this phase")
    b: NegativeFloat = Field(description="b-value for this phase")
    swirr: float = Field(default=0.0, description="Irreducible water saturation")

    @field_validator("swirr")
    @classmethod
    def _check_swirr_range(cls, value: float) -> float:
        if value < 0.0:
            logger.warning(
                "swirr is negative; this is unusual but allowed (value=%s).", value
            )
        if value > 1.0:
            raise ValueError("swirr must be 1.0 or smaller.")
        return value


class JFunction(_SwBaseModel):
    """J-function parameters for a single sw-function group."""

    oil: PhaseJFunction | None = Field(
        default=None, description="Oil/water J-function parameters."
    )
    gas: PhaseJFunction | None = Field(
        default=None, description="Gas/water J-function parameters."
    )

    @model_validator(mode="after")
    def _check_at_least_one_phase(self) -> JFunction:
        if self.oil is None and self.gas is None:
            raise ValueError(
                "At least one of 'oil' or 'gas' J-functions must be defined "
                "for each sw-function group."
            )
        return self


class SwAlgorithm(_SwBaseModel):
    """Numerical and algorithmic settings for SwFunction."""

    method: Literal[
        "cell_center_above_ffl",
        "cell_corners_above_ffl",
        "truncated_cell_corners_above_ffl",
    ] = "truncated_cell_corners_above_ffl"
    calc: Literal["direct", "integrated"] = "direct"
    epsilon: PositiveFloat = Field(
        default=1e-9,
        description="Used to avoid division by zero. Must be larger than zero.",
    )
    invert_jfunc: bool = Field(
        default=False,
        description="Set to true if a and b input is in RMS format.",
    )


class SwOutputNames(_SwBaseModel):
    """Output names used when writing properties to RMS."""

    sw: str = Field(default="sw", min_length=1)
    sw_h: str = Field(default="sw_hcenter", min_length=1)
    swl: str = Field(default="swl", min_length=1)
    so: str = Field(default="so", min_length=1)
    sg: str = Field(default="sg", min_length=1)


class SwConfig(_SwBaseModel):
    """Top-level configuration parsed from YAML or a Python mapping."""

    grid: str = Field(
        description="Grid file path or RMS grid model name.",
        examples=["path/to/grid.roff", "Geogrid"],
        min_length=1,
    )
    gridparameter: GridParameter
    sw_functions: dict[str, JFunction]
    algorithm: SwAlgorithm = Field(default_factory=SwAlgorithm)
    output: SwOutputNames = Field(default_factory=SwOutputNames)
    swl_height: PositiveFloat | None = Field(
        default=None,
        description="If supplied this will be used to create a swl parameter.",
        examples=[300],
    )
    swl_min: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="If supplied, calculated swl is clipped to be >= swl_min.",
        examples=[0.05],
    )
    swl_max: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="If supplied, calculated swl is clipped to be <= swl_max.",
        examples=[0.7],
    )

    @model_validator(mode="after")
    def _check_non_empty_sw_functions(self) -> SwConfig:
        if not self.sw_functions:
            raise ValueError("sw_functions must contain at least one J-function group.")
        return self

    @model_validator(mode="after")
    def _check_swl_clip_range(self) -> SwConfig:
        if (
            self.swl_min is not None
            and self.swl_max is not None
            and self.swl_min > self.swl_max
        ):
            raise ValueError("swl_min must be <= swl_max.")
        return self

    @model_validator(mode="after")
    def _warn_clip_without_swl(self) -> SwConfig:
        if self.swl_height is None and (
            self.swl_min is not None or self.swl_max is not None
        ):
            logger.warning(
                "swl_min/swl_max provided but swl_height is None; "
                "no swl parameter will be produced and clipping is ignored."
            )
        return self

    @cached_property
    def phase_types(self) -> set[str]:
        has_oil = any(jf.oil is not None for jf in self.sw_functions.values())
        has_gas = any(jf.gas is not None for jf in self.sw_functions.values())

        phase_types: set[str] = set()
        if has_oil:
            phase_types.add("oil")
        if has_gas:
            phase_types.add("gas")
        if not phase_types:
            raise ValueError(
                "No valid J-functions found in sw_functions: "
                "none of the groups has a complete oil or gas (a,b) pair."
            )
        return phase_types

    @model_validator(mode="after")
    def _check_phase_vs_contacts(self) -> SwConfig:
        has_oil = any(jf.oil is not None for jf in self.sw_functions.values())
        has_gas = any(jf.gas is not None for jf in self.sw_functions.values())
        gp = self.gridparameter

        if has_oil and gp.fwl is None:
            raise ValueError(
                "Oil J-functions present but no fwl parameter provided; "
                "this combination is not supported."
            )
        if has_gas and (gp.goc is None or gp.fwlwg is None):
            raise ValueError(
                "Gas J-functions present but goc/fwlwg parameters are missing; "
                "both are required for gas J-functions."
            )
        return self

    @model_validator(mode="after")
    def _check_uniform_phase_sets(self) -> SwConfig:
        expected_phase_types = self.phase_types
        mismatches: list[str] = []

        for group_name, jfunc in self.sw_functions.items():
            group_phase_types: set[str] = set()
            if jfunc.oil is not None:
                group_phase_types.add("oil")
            if jfunc.gas is not None:
                group_phase_types.add("gas")

            if group_phase_types != expected_phase_types:
                phases = "/".join(sorted(group_phase_types))
                mismatches.append(f"{group_name} ({phases})")

        if mismatches:
            expected = "/".join(sorted(expected_phase_types))
            details = ", ".join(mismatches)
            raise ValueError(
                "All sw_functions groups must define the same phase set because "
                "region-specific contact selection is not supported. Expected "
                f"every group to define {expected}; mismatches: {details}."
            )
        return self

    @model_validator(mode="after")
    def _check_integrated_b_values(self) -> SwConfig:
        if self.algorithm.calc != "integrated":
            return self

        unsupported: list[str] = []
        for group_name, jfunc in self.sw_functions.items():
            if jfunc.oil is not None and jfunc.oil.b == -1.0:
                unsupported.append(f"{group_name}.oil")
            if jfunc.gas is not None and jfunc.gas.b == -1.0:
                unsupported.append(f"{group_name}.gas")

        if unsupported:
            joined = ", ".join(unsupported)
            raise ValueError(
                "algorithm.calc='integrated' does not support J-functions with "
                f"b = -1.0 (found in: {joined}). Use calc='direct' or choose "
                "b != -1.0."
            )
        return self

    @model_validator(mode="after")
    def _log_algorithm_settings(self) -> SwConfig:
        if self.algorithm.invert_jfunc:
            logger.info(
                "invert_jfunc is True: a and b input is in RMS format. "
                "Make sure to verify this."
            )
        else:
            logger.info(
                "invert_jfunc is False: a and b input is in petrophysical format. "
                "Make sure to verify this."
            )
        return self


def load_config(config_file: str | Path, key_path: str = "") -> dict[str, Any]:
    """Load a YAML configuration file and optionally return a nested mapping."""

    config_path = Path(config_file)
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file {config_path} does not exist")

    with config_path.open(encoding="utf-8") as stream:
        config = yaml.safe_load(stream)

    if config is None:
        config = {}

    if not isinstance(config, dict):
        raise ValueError(
            f"Configuration file {config_path} must contain a YAML mapping at the root"
        )

    return _select_key_path_mapping(config, key_path)


def _select_key_path_mapping(config: dict[str, Any], key_path: str) -> dict[str, Any]:
    """Return the mapping located at key_path within config."""

    current: Any = config
    for path_part in filter(None, key_path.split(".")):
        if not isinstance(current, dict):
            raise KeyError(
                f"Key path '{key_path}' is invalid: '{path_part}' is not a mapping"
            )
        if path_part not in current:
            available = [str(key) for key in current]
            match = difflib.get_close_matches(path_part, available, n=1, cutoff=0.5)
            if match:
                hint = f" (did you mean '{match[0]}'?)"
            elif available:
                hint = f" (available: {', '.join(available)})"
            else:
                hint = ""
            raise KeyError(
                f"Key path '{key_path}' not found: missing '{path_part}'{hint}"
            )
        current = current[path_part]

    if not isinstance(current, dict):
        raise KeyError(
            f"Key path '{key_path}' is invalid: final value is not a mapping"
        )

    return current


def load_swconfig(
    config: str | Path | dict[str, Any] | SwConfig,
    key_path: str = "",
) -> SwConfig:
    """Parse a configuration source into SwConfig."""

    if isinstance(config, SwConfig):
        return config

    if isinstance(config, (str, Path)):
        data = load_config(config, key_path=key_path)
    else:
        data = _select_key_path_mapping(dict(config), key_path)
    return SwConfig(**data)
