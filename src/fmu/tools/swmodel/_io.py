from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np
import xtgeo

if TYPE_CHECKING:
    from ._config import SwConfig

logger = logging.getLogger(__name__)


def validate_code_names_vs_cfg_names(
    sw_region_param: xtgeo.GridProperty, cfg: SwConfig
) -> None:
    """Validate that region parameter code names are present in YAML sw_functions."""

    active_codes = {
        int(code) for code in np.ma.array(sw_region_param.values).compressed().tolist()
    }
    code_names = {str(code_name) for code_name in sw_region_param.codes.values()}
    if not code_names:
        raise ValueError(
            f"Sw-function region property ({cfg.gridparameter.swfunc_region}) does "
            "not define any code names; discrete code names must match the keys "
            "under YAML sw_functions."
        )
    unnamed_codes = sorted(active_codes - set(sw_region_param.codes))
    if unnamed_codes:
        raise ValueError(
            f"Sw-function region property ({cfg.gridparameter.swfunc_region}) uses "
            f"codes without names: {unnamed_codes}"
        )

    unknown_groups = code_names - set(cfg.sw_functions)
    if unknown_groups:
        raise ValueError(
            f"Sw-function region property ({cfg.gridparameter.swfunc_region}) contains "
            f"codes not present in YAML sw_functions: {sorted(unknown_groups)}"
        )

    unused_groups = set(cfg.sw_functions) - code_names
    if unused_groups:
        logger.warning(
            "YAML sw_functions contains groups that are not defined in swfunc_region "
            "parameter: %s",
            sorted(unused_groups),
        )


class FileBackend:
    """Load and write swmodel data from ordinary files."""

    def __init__(self, cfg: SwConfig):
        self.cfg = cfg

    @staticmethod
    def _require_file(path_str: str) -> Path:
        path = Path(path_str)
        if not path.is_file():
            raise FileNotFoundError(f"Input file {path} does not exist")
        return path

    def load_grid_and_properties(
        self,
    ) -> tuple[xtgeo.Grid, dict[str, xtgeo.GridProperty]]:
        """Load grid and properties from file paths."""

        grid = xtgeo.grid_from_file(self._require_file(self.cfg.grid))
        cfg_gp = self.cfg.gridparameter

        gridprops: dict[str, xtgeo.GridProperty] = {}
        gridprops["swfunc_region"] = xtgeo.gridproperty_from_file(
            self._require_file(cfg_gp.swfunc_region)
        )
        gridprops["poro"] = xtgeo.gridproperty_from_file(
            self._require_file(cfg_gp.poro)
        )
        gridprops["perm"] = xtgeo.gridproperty_from_file(
            self._require_file(cfg_gp.perm)
        )

        if cfg_gp.fwl is not None:
            gridprops["fwl"] = xtgeo.gridproperty_from_file(
                self._require_file(cfg_gp.fwl)
            )
        if cfg_gp.goc is not None:
            gridprops["goc"] = xtgeo.gridproperty_from_file(
                self._require_file(cfg_gp.goc)
            )
        if cfg_gp.fwlwg is not None:
            gridprops["fwlwg"] = xtgeo.gridproperty_from_file(
                self._require_file(cfg_gp.fwlwg)
            )

        validate_code_names_vs_cfg_names(gridprops["swfunc_region"], self.cfg)
        return grid, gridprops

    def write(
        self,
        gridname: str,
        props: dict[str, xtgeo.GridProperty],
        output_folder: str | Path,
    ) -> None:
        """Write output properties to ROFF files."""

        outfolder = Path(output_folder)
        outfolder.mkdir(parents=True, exist_ok=True)
        logger.info("Write swmodel properties to %s", outfolder)
        for prop_key, prop in props.items():
            output_file = outfolder / f"{gridname.lower()}--{prop_key}.roff"
            prop.to_file(output_file)
            logger.info("Wrote swmodel file %s", output_file)


class RmsBackend:
    """Load and write swmodel data through the RMS API."""

    def __init__(self, project: Any, cfg: SwConfig):
        self.project = project
        self.cfg = cfg
        self.grid_name = cfg.grid

    @property
    def realisation(self) -> int:
        """Return the active RMS realisation for this project."""

        return int(self.project.current_realisation)

    def _grid_model(self) -> Any:
        if self.grid_name not in self.project.grid_models:
            raise ValueError(
                f"Grid model {self.grid_name!r} was not found in the project"
            )
        return self.project.grid_models[self.grid_name]

    def _property_names(self) -> set[str]:
        return {
            prop if isinstance(prop, str) else str(prop.name)
            for prop in self._grid_model().properties
        }

    def _require_property(self, property_name: str) -> None:
        if property_name not in self._property_names():
            raise ValueError(
                f"Property {property_name!r} was not found in grid model "
                f"{self.grid_name!r}"
            )

    def load_grid_and_properties(
        self,
    ) -> tuple[xtgeo.Grid, dict[str, xtgeo.GridProperty]]:
        """Load grid and properties from RMS."""

        self._grid_model()
        cfg_gp = self.cfg.gridparameter
        required = {
            "swfunc_region": cfg_gp.swfunc_region,
            "poro": cfg_gp.poro,
            "perm": cfg_gp.perm,
        }
        for prop_name in required.values():
            self._require_property(prop_name)

        optional: list[tuple[str, str | None]] = [
            ("fwl", cfg_gp.fwl),
            ("goc", cfg_gp.goc),
            ("fwlwg", cfg_gp.fwlwg),
        ]
        for prop_key, optional_prop_name in optional:
            if optional_prop_name is None:
                continue
            self._require_property(optional_prop_name)

        grid = xtgeo.grid_from_roxar(
            self.project,
            self.grid_name,
            realisation=self.realisation,
        )
        gridprops: dict[str, xtgeo.GridProperty] = {}
        for prop_key, prop_name in required.items():
            gridprops[prop_key] = xtgeo.gridproperty_from_roxar(
                self.project,
                self.grid_name,
                prop_name,
                realisation=self.realisation,
            )
        for prop_key, optional_prop_name in optional:
            if optional_prop_name is None:
                continue
            gridprops[prop_key] = xtgeo.gridproperty_from_roxar(
                self.project,
                self.grid_name,
                optional_prop_name,
                realisation=self.realisation,
            )

        validate_code_names_vs_cfg_names(gridprops["swfunc_region"], self.cfg)
        return grid, gridprops

    def write(self, props: dict[str, xtgeo.GridProperty]) -> None:
        """Write output properties back to RMS."""

        output_names = {
            "sw": self.cfg.output.sw,
            "sw_h": self.cfg.output.sw_h,
            "swl": self.cfg.output.swl,
            "so": self.cfg.output.so,
            "sg": self.cfg.output.sg,
        }
        selected_output_names = [output_names[prop_key] for prop_key in props]
        duplicate_output_names = sorted(
            {
                output_name
                for output_name in selected_output_names
                if selected_output_names.count(output_name) > 1
            }
        )
        if duplicate_output_names:
            raise ValueError(
                "RMS output property names must be unique for the selected outputs; "
                f"duplicates: {duplicate_output_names}"
            )
        existing_properties = self._property_names()
        for prop_key, prop in props.items():
            output_name = output_names[prop_key]
            action = "Updated" if output_name in existing_properties else "Created"
            prop.to_roxar(
                self.project,
                self.grid_name,
                output_name,
                realisation=self.realisation,
            )
            logger.info(
                "%s RMS parameter %r in grid model %r (realisation %s)",
                action,
                output_name,
                self.grid_name,
                self.realisation,
            )
            existing_properties.add(output_name)
