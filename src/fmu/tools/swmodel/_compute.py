from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np

from fmu.tools.properties import SwFunction

if TYPE_CHECKING:
    import xtgeo

    from ._config import SwConfig

logger = logging.getLogger(__name__)


def _get_z_values(grid: xtgeo.Grid) -> np.ndarray | np.ma.MaskedArray:
    """Return cell-center z values for the grid."""

    _, _, zc = grid.get_xyz(asmasked=True)
    return zc.values


def _filled_false(mask: np.ndarray | np.ma.MaskedArray) -> np.ndarray:
    """Convert a boolean mask-like array to plain bools, treating masked as False."""

    return np.asarray(np.ma.filled(mask, False), dtype=bool)


def compute_sqrt_perm_over_poro(
    poro: xtgeo.GridProperty,
    perm: xtgeo.GridProperty,
    epsilon: float,
) -> xtgeo.GridProperty:
    """Compute x = sqrt(perm/poro) with safeguards."""

    x = poro.copy()
    x.values[x.values == 0.0] = epsilon
    x.values = np.sqrt(np.divide(perm.values, x.values))
    x.values[x.values < epsilon] = epsilon
    x.name = "x"
    return x


def compute_sw_func_parameters(
    grid: xtgeo.Grid,
    gridprops: dict[str, xtgeo.GridProperty],
    cfg: SwConfig,
    phase_types: set[str],
    z_values: np.ndarray | np.ma.MaskedArray | None = None,
) -> tuple[xtgeo.GridProperty, xtgeo.GridProperty, xtgeo.GridProperty]:
    """Calculate a, b and swirr for each sw-function group."""

    a: xtgeo.GridProperty = gridprops["poro"].copy()
    b: xtgeo.GridProperty = gridprops["poro"].copy()
    swirr: xtgeo.GridProperty = gridprops["poro"].copy()
    a.values.fill(0.0)
    b.values.fill(0.0)
    swirr.values.fill(0.0)

    group_prop = gridprops["swfunction_region"]

    for group_idx, group_name in group_prop.codes.items():
        logger.info("Computing sw-function parameters for group %s", group_name)

        group_mask = _filled_false(group_prop.values == group_idx)
        jf = cfg.sw_functions[group_name]

        if "oil" in phase_types and jf.oil is not None:
            a.values[group_mask] = jf.oil.a
            b.values[group_mask] = jf.oil.b
            swirr.values[group_mask] = jf.oil.swirr

        if "gas" in phase_types and jf.gas is not None and jf.oil is None:
            a.values[group_mask] = jf.gas.a
            b.values[group_mask] = jf.gas.b
            swirr.values[group_mask] = jf.gas.swirr

        if (
            "oil" in phase_types
            and "gas" in phase_types
            and jf.oil is not None
            and jf.gas is not None
        ):
            if z_values is None:
                z_values = _get_z_values(grid)
            goc_mask = _filled_false(z_values < gridprops["goc"].values)
            group_goc_mask = goc_mask & group_mask
            group_goc_mask_flat = group_goc_mask[group_mask]

            a.values[group_mask] = np.where(
                group_goc_mask_flat,
                jf.gas.a,
                a.values[group_mask],
            )
            b.values[group_mask] = np.where(
                group_goc_mask_flat,
                jf.gas.b,
                b.values[group_mask],
            )
            swirr.values[group_mask] = np.where(
                group_goc_mask_flat,
                jf.gas.swirr,
                swirr.values[group_mask],
            )

    return a, b, swirr


def clip_swl(
    swl: xtgeo.GridProperty,
    swl_min: float | None,
    swl_max: float | None,
) -> xtgeo.GridProperty:
    """Clip swl to [swl_min, swl_max], defaulting to [0, 1]."""

    swl_min = 0.0 if swl_min is None else swl_min
    swl_max = 1.0 if swl_max is None else swl_max
    logger.info("Clipping swl to [%s, %s]", swl_min, swl_max)
    np.clip(swl.values, swl_min, swl_max, out=swl.values)
    return swl


def compute_sw(
    grid: xtgeo.Grid,
    gridprops: dict[str, xtgeo.GridProperty],
    cfg: SwConfig,
    hcenter: xtgeo.GridProperty | None = None,
    htop: xtgeo.GridProperty | None = None,
    hbottom: xtgeo.GridProperty | None = None,
    z_values: np.ndarray | np.ma.MaskedArray | None = None,
) -> tuple[xtgeo.GridProperty, xtgeo.GridProperty, xtgeo.GridProperty | None]:
    """Calculate water saturation and sw height parameters."""

    phase_types = cfg.phase_types
    if z_values is None and phase_types == {"oil", "gas"}:
        z_values = _get_z_values(grid)

    sqrt_k_phi = compute_sqrt_perm_over_poro(
        poro=gridprops["poro"],
        perm=gridprops["perm"],
        epsilon=cfg.algorithm.epsilon,
    )

    a, b, swirr = compute_sw_func_parameters(
        grid,
        gridprops,
        cfg,
        phase_types,
        z_values=z_values,
    )

    ffl = (gridprops["fwl"] if "oil" in phase_types else gridprops["fwlwg"]).copy()
    if "oil" in phase_types and "gas" in phase_types:
        below_goc_mask = z_values >= gridprops["goc"].values
        ffl.values = np.ma.where(
            below_goc_mask,
            ffl.values,
            gridprops["fwlwg"].values,
        )

    sw = SwFunction(
        grid=grid,
        x=sqrt_k_phi,
        ffl=ffl,
        a=a.copy(),
        b=b.copy(),
        invert=cfg.algorithm.invert_jfunc,
        swira=swirr,
        method=cfg.algorithm.method,
        htop=htop,
        hcenter=hcenter,
        hbot=hbottom,
    ).compute(compute_method=cfg.algorithm.calc)

    sw["SW"].name = "sw"
    sw["HCENTER"].name = "sw_hcenter"

    if cfg.swl_height is not None:
        swl_h = sw["HCENTER"].copy()
        swl_h.values.fill(cfg.swl_height)
        swl = SwFunction(
            grid=grid,
            x=sqrt_k_phi,
            ffl=ffl,
            a=a.copy(),
            b=b.copy(),
            invert=cfg.algorithm.invert_jfunc,
            swira=swirr,
            method="cell_center_above_ffl",
            htop=swl_h,
            hcenter=swl_h,
            hbot=swl_h,
        ).compute(compute_method="direct")
        swl["SW"].name = "swl"
        clip_swl(swl["SW"], cfg.swl_min, cfg.swl_max)
        return sw["SW"], sw["HCENTER"], swl["SW"]

    return sw["SW"], sw["HCENTER"], None


def compute_so_sg(
    grid: xtgeo.Grid,
    gridprops: dict[str, xtgeo.GridProperty],
    sw: xtgeo.GridProperty,
    cfg: SwConfig,
    z_values: np.ndarray | np.ma.MaskedArray | None = None,
) -> tuple[xtgeo.GridProperty, xtgeo.GridProperty]:
    """Compute oil and gas saturations from water saturation."""

    phase_types = cfg.phase_types
    hc = 1.0 - sw.values

    so = sw.copy()
    sg = sw.copy()
    so.name = "so"
    sg.name = "sg"
    so.values.fill(0.0)
    sg.values.fill(0.0)

    if phase_types == {"oil"}:
        so.values[...] = hc
    elif phase_types == {"gas"}:
        sg.values[...] = hc
    elif phase_types == {"oil", "gas"}:
        goc_prop = gridprops.get("goc")
        if goc_prop is None:
            raise ValueError(
                "Gas phase present but no 'goc' grid property loaded; "
                "cannot split HC between so and sg."
            )

        if z_values is None:
            z_values = _get_z_values(grid)
        gas_cap_mask = _filled_false(z_values < goc_prop.values)
        sg.values[gas_cap_mask] = hc[gas_cap_mask]
        oil_zone_mask = ~gas_cap_mask
        so.values[oil_zone_mask] = hc[oil_zone_mask]
    else:
        raise ValueError(f"Unsupported phase_types combination: {phase_types}")

    np.clip(so.values, 0.0, 1.0, out=so.values)
    np.clip(sg.values, 0.0, 1.0, out=sg.values)
    return so, sg


def compute(
    cfg: SwConfig,
    *,
    grid: xtgeo.Grid,
    gridprops: dict[str, xtgeo.GridProperty],
    output_all: bool = False,
) -> tuple[str, dict[str, xtgeo.GridProperty]]:
    """Compute saturation properties for a given configuration."""

    gridname = grid.name or "unnamed_grid"
    z_values = _get_z_values(grid) if cfg.phase_types == {"oil", "gas"} else None

    sw, sw_h, swl = compute_sw(grid, gridprops, cfg, z_values=z_values)
    props: dict[str, xtgeo.GridProperty] = {"sw": sw, "sw_h": sw_h}
    if swl is not None:
        props["swl"] = swl

    if output_all:
        so, sg = compute_so_sg(
            grid=grid,
            gridprops=gridprops,
            sw=sw,
            cfg=cfg,
            z_values=z_values,
        )
        props["so"] = so
        props["sg"] = sg

    return gridname, props
