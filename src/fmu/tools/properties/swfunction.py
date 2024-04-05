"""Sw J or BVW or Brooks-Corey general functions, by direct or integration.

Solve a system on form:

sw = a(m + x*h)^b

The "x" can e.g. be the J term in the Leverett equation, but without the height term.

In many cases m is zero.

Note:
The public library `xtgeo` must be available.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import xtgeo

# custom logger for this module
logger = logging.getLogger(__name__)

ALLOWED_METHODS = [
    "cell_center",
    "cell_center_above_ffl",
    "cell_corners_above_ffl",
]


@dataclass
class SwFunction:
    """Generic Sw calc for formulation Sw = a * (m + x * h)^b.

    Some theory for this is shown here: :download:`pdf <pdf/sw_calc.pdf>`.

    Args:
        grid: The xtgeo grid object
        x: The ``x`` term in the generic saturation. For a simplified J function, this
            will be sqrt(perm/poro).
        a: The ``a`` term in the generic saturation.
        b: The ``b`` term in the generic saturation.
        ffl: The free fluid level, either as a number or a 3D xtgeo gridproperty
            object.
        m: The ``m`` term in the equation above, either as a number or a 3D xtgeo
            gridproperty object. Defaults to zero.
        swira: The absolute irreducable satuation applied as asymptote in the equation.
            Defaults to zero.
        swmax: The maximum applied as asymptote in the equation.
            Defaults to 1.
        method: How to look at cell geometry. There are three options: 'cell_center',
            'cell_center-above_ffl' and 'cell_corners_above_ffl'.
        gridname: Optional - only needed when debug keyword is True.
        project: Optional. Must be included when working in RMS.
        invert: Optional, will in case invert ``a`` and ``b`` in case the J function
            (or similar) is formulated as Sw = (J/A)^(1/B). This is the case in e.g.
            RMS
        zdepth: Optional. May speed up computation if provided, in case the function
            is called several time for the same grid.
        hcenter: Optional. May speed up computation if provided, in case the function
            is called several time for the same grid, or hcenter is pre-computed in a
            special way. The hcenter will work with direct method only, not integration.
        htop: Optional. May speed up computation if provided, in case the function
            is called several time for the same grid.
        hbot: Optional. May speed up computation if provided, in case the function
            is called several time for the same grid.
        debug: If True, several "check parameters" will we given, either as grid
            properties (if working in RMS) or as ROFF files (if working outside RMS).
        tag: Optional string to identify debug parameters.


    """

    grid: xtgeo.Grid
    # all input are constants or xtgeo grid or gridproperty
    x: float | xtgeo.GridProperty = 0.0
    a: float | xtgeo.GridProperty = 1.0
    b: float | xtgeo.GridProperty = -1.0
    ffl: float | xtgeo.GridProperty = 999.0

    m: float | xtgeo.GridProperty = 0.0

    swira: float | xtgeo.GridProperty = 0.0
    swmax: float | xtgeo.GridProperty = 1.0

    method: str = "cell_center_above_ffl"
    gridname: str = ""  # only used when debugging in RMS
    project: Any | None = None
    invert: bool = False  # if the SwJ function is on "reverse" form

    # if None they will be computed here; otherwise they can be given explicitly:
    hcenter: xtgeo.GridProperty = None
    htop: xtgeo.GridProperty = None
    hbot: xtgeo.GridProperty = None

    # debug flag for additional parameters. Given in RMS if project is given; otherwise
    # as files on your working folder
    debug: bool = False
    tag: str = ""  # identification tag to add to debug params

    # derived and internal
    _swval: np.ma.MaskedArray = field(init=False)
    _sw: Any = field(init=False)

    def __post_init__(self) -> None:
        """Post init."""

        if self.tag and not self.tag.startswith("_"):
            self.tag = "_" + self.tag

        self._process_input()

        if all([self.hcenter, self.htop, self.hbot]):
            logger.info("Essential geometries are pre-computed")
        else:
            self._compute_htop_hbot()

        if self.debug:
            if self.project:
                self.grid.to_roxar(self.project, "DEBUG_" + self.gridname)
            else:
                self.grid.to_file("debug_grid.roff")

    def _process_input(self) -> None:
        """Work with a, b, x, ie. inversing and convert from float."""
        logger.info("Process a, b, etc")

        if self.method not in ALLOWED_METHODS:
            raise ValueError(
                f"The method <{self.method}> is invalid. Allowed: {ALLOWED_METHODS}"
            )

        if isinstance(self.a, (int, float)):
            self.a = xtgeo.GridProperty(self.grid, values=self.a)
        if isinstance(self.b, (int, float)):
            self.b = xtgeo.GridProperty(self.grid, values=self.b)
        if isinstance(self.x, (int, float)):
            self.x = xtgeo.GridProperty(self.grid, values=self.x)
        if isinstance(self.m, (int, float)):
            self.m = xtgeo.GridProperty(self.grid, values=self.m)
        if isinstance(self.ffl, (int, float)):
            self.ffl = xtgeo.GridProperty(self.grid, values=self.ffl)
        if isinstance(self.swira, (int, float)):
            self.swira = xtgeo.GridProperty(self.grid, values=self.swira)
        if isinstance(self.swmax, (int, float)):
            self.swmax = xtgeo.GridProperty(self.grid, values=self.swmax)

        if self.invert:
            orig_a = self.a.values.mean()
            orig_b = self.b.values.mean()
            self.b.values = 1.0 / self.b.values
            self.a.values = np.ma.power(1.0 / self.a.values, self.b.values)
            new_a = self.a.values.mean()
            new_b = self.b.values.mean()
            logger.info(
                "Inverted a and b; original average was %s %s, new is %s %s",
                orig_a,
                orig_b,
                new_a,
                new_b,
            )

    def _compute_htop_hbot(self) -> None:
        """Setting geometries for 'bottom' and 'top' cell.

        All these values are relative to the given contact, as "height above". For
        cells under the contact, zero or a negative number will be applied.
        """
        assert isinstance(self.ffl, xtgeo.GridProperty)  # mypy

        htop, hbot, hmid = self.grid.get_heights_above_ffl(self.ffl, option=self.method)

        self.htop = htop
        self.hbot = hbot
        self.hcenter = hmid
        logger.info("Use method %s", self.method)

        if self.debug:
            htop.name = "TOP_SW" + self.tag
            hbot.name = "BOT_SW" + self.tag
            hmid.name = "CENTER_SW" + self.tag
            if self.project:
                logger.debug("TAG is ", self.tag)
                htop.to_roxar(self.project, self.gridname, "HTOP" + self.tag)
                hbot.to_roxar(self.project, self.gridname, "HBOT" + self.tag)
                hmid.to_roxar(self.project, self.gridname, "HCENTER" + self.tag)
            else:
                htop.to_file(f"debug_htop{self.tag}.roff")
                hbot.to_file(f"debug_hbot{self.tag}.roff")
                hmid.to_file(f"debug_hcenter{self.tag}.roff")

    def _sw_function_direct(self) -> None:
        """Use function on form Sw = A*(M + X*h)^B; generic function!"""
        assert isinstance(self.a, xtgeo.GridProperty)  # mypy
        assert isinstance(self.b, xtgeo.GridProperty)  # mypy
        assert isinstance(self.x, xtgeo.GridProperty)  # mypy
        assert isinstance(self.m, xtgeo.GridProperty)  # mypy
        assert isinstance(self.swira, xtgeo.GridProperty)  # mypy
        assert isinstance(self.swmax, xtgeo.GridProperty)  # mypy

        # the direct function is mostly used to compare with integrated approach, as QC
        height = self.hcenter.values
        xh_val = self.x.values * height

        self._swval = self.a.values * np.ma.power(self.m.values + xh_val, self.b.values)

        # normalize before any limitations
        self._swval = (
            self.swira.values + (self.swmax.values - self.swira.values) * self._swval
        )

        self._swval = np.ma.where(height <= 0.0, 1, self._swval)
        self._swval = np.ma.where(self._swval > 1.0, 1.0, self._swval)

        # store result
        self._sw = xtgeo.GridProperty(self.grid, values=self._swval)

    def _sw_function_integrate_w_mterm(self) -> None:
        """Integrate a function on form Sw = A*(M + JX*H)^B; generic function!

        It assumes here:
        * A: self.a
        * B: self.b
        * X: self.x
        * M: self.m
        * self.ffl is the free fluid level for the phase under investigation
        """
        assert isinstance(self.a, xtgeo.GridProperty)  # mypy
        assert isinstance(self.b, xtgeo.GridProperty)  # mypy
        assert isinstance(self.x, xtgeo.GridProperty)  # mypy
        assert isinstance(self.m, xtgeo.GridProperty)  # mypy
        assert isinstance(self.swira, xtgeo.GridProperty)  # mypy
        assert isinstance(self.swmax, xtgeo.GridProperty)  # mypy
        ht = (
            ((1.0 / self.a.values) ** (1.0 / self.b.values)) - self.m.values
        ) / self.x.values  # threshold height

        h2 = self.htop.values.copy()  # h_top or H2 in integration
        h1 = self.hbot.values.copy()  # h_bot or H1 in integration

        if self.debug:
            tmp = xtgeo.GridProperty(self.grid, values=ht, name="HT" + self.tag)
            if self.project:
                tmp.to_roxar(self.project, self.gridname, "THRESHOLD HEIGHT" + self.tag)
            else:
                tmp.to_file(f"debug_ht{self.tag}.roff")

        water = h2 * 0.0
        water = np.ma.where(h2 < ht, 1.0, water)
        water = np.ma.where(h2 <= 0.0, 1.0, water)  # may occur for negative ht

        # get all possible corner cases when a cell is close to free fluid level
        # some of these are probably hitting twice or more; the point is to integrate
        # over correct interval
        h1x = np.ma.where(h1 <= 0.0, 0.0, h1)
        h2x = np.ma.where(h2 <= h1x, h1x, h2)
        htx = ht - h1x
        htx = np.ma.where(htx <= 0.0, 0.0, htx)
        htx = np.ma.where(h2x <= 0.0, 0.0, htx)
        hxx = np.ma.where(ht > h1x, ht, h1x)

        dh = h2x - h1x
        dh = np.ma.where(dh < 0.001, 0.001, dh)  # avoid zero division

        self._swval = (
            htx
            + self.a.values
            / (self.x.values * (self.b.values + 1))
            * (
                np.ma.power(self.m.values + self.x.values * h2x, self.b.values + 1)
                - np.ma.power(self.m.values + self.x.values * hxx, self.b.values + 1)
            )
        ) / dh

        # mark collapsed cells, where direct calulation is needed
        mark = (h2x - h1x) * 0.0
        mark = np.ma.where(dh <= 0.001, 1.0, mark)
        jval = self.x.values * h2x
        coll_swval = self.a.values * np.ma.power(self.m.values + jval, self.b.values)
        self._swval = np.ma.where(mark > 0.5, coll_swval, self._swval)

        # normalize before any limitations
        self._swval = (
            self.swira.values + (self.swmax.values - self.swira.values) * self._swval
        )

        # limit
        self._swval = np.ma.where(water > 0.5, 1.0, self._swval)
        self._swval = np.ma.where(self._swval > 1.0, 1.0, self._swval)
        self._swval = np.ma.where(self._swval < 0.00099, 0.00099, self._swval)

        self._sw = xtgeo.GridProperty(self.grid, values=self._swval)

    def _compute_integrated(self) -> None:
        """Compute Sw, integrated version."""
        logger.info("Integration, do integration over height of cell...")
        self._sw_function_integrate_w_mterm()

        if self._sw.values.max() > 1.0:
            raise RuntimeError(f"SW max out of range: {self._sw.values.max()}")
        if self._sw.values.min() < 0.0:
            raise RuntimeError(f"SW min out of range: {self._sw.values.min()}")

    def _compute_direct(self) -> None:
        """Compute Sw, direct version (less precise wiht thick cells)."""
        logger.info("Direct, no integration over height...")
        self._sw_function_direct()

        if self._sw.values.max() > 1.0:
            raise RuntimeError(f"SW max out of range: {self._sw.values.max()}")
        if self._sw.values.min() < 0.0:
            raise RuntimeError(f"SW min out of range: {self._sw.values.min()}")

    def compute(self, compute_method: str = "integrated") -> xtgeo.GridProperty:
        """Common compute function for saturation, and returns the Sw property"""
        if compute_method == "integrated":
            self._compute_integrated()
        else:
            self._compute_direct()

        return self._sw
