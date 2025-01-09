from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Generator

import numpy as np
import xtgeo

_logger = logging.getLogger(__name__)


@dataclass
class DomainConversion:
    """
    Domain conversion, tailored for fmu-sim2seis, but also works as standalone.

    The principle is to use matching sets of time and depth surfaces to create a
    velocity (and slowness) model, and use that further to domain convert either
    seismic cubes or surfaces, time <=> depth.

    Args:
        depth_surfaces: List of depth surfaces.
        time_surfaces: List of time surfaces.
        names: Optional list of names for the surfaces. If not
            provided, the names will be inferred from the input object, or
            (if missing) generated as "surf_0", "surf_1", etc.
        template: Optional template surface to use for resampling the input surfaces.
            If not provided, the last time surface will be used as template.

    Note:
        The input surfaces must be in the same sorted order, and the number
        of depth and time surfaces must be equal. The first surface does not need
        to be MSL. The surfaces must extend the full area of the model, and the
        subsequent surfaces or cubes to be converted must be inside the area of
        the surfaces that define the model.

    Example:
        >>> from xtgeo import RegularSurface, Cube
        >>> from fmu.tools.domainconversion import DomainConversion
        >>> # read input surfaces into lists...
        >>> depth_surfaces_list = [xtgeo.surface_from_file("depth1.gri"), ...]
        >>> time_surfaces_list = [xtgeo.surface_from_file("time1.gri"), ...]
        >>> dc = DomainConversion(depth_surfaces_list, time_surfaces_list)
        >>> # read a cube... and convert the cube from time to depth
        >>> input_cube_in_time = xtgeo.cube_from_file("input_cube.segy")
        >>> result_cube_in_depth = dc.depth_convert_cube(input_cube_in_time)
    """

    # input
    depth_surfaces: list[xtgeo.RegularSurface]
    time_surfaces: list[xtgeo.RegularSurface]
    names: list[str] | None = None
    template: xtgeo.RegularSurface | None = None

    # Instance variables (private)
    _time_cube: xtgeo.Cube = field(default=None, init=False)  # ~ extended to MSL
    _depth_cube: xtgeo.Cube = field(default=None, init=False)  # ~ extended to MSL
    _vcube_t: xtgeo.Cube = field(default=None, init=False)  # avg velocity cube in time
    _scube_d: xtgeo.Cube = field(default=None, init=False)  # avg slowness cube in depth

    _v_surfaces: list[xtgeo.RegularSurface] = field(default_factory=list, init=False)
    _s_surfaces: list[xtgeo.RegularSurface] = field(default_factory=list, init=False)
    _d_surfaces: list[xtgeo.RegularSurface] = field(default_factory=list, init=False)
    _t_surfaces: list[xtgeo.RegularSurface] = field(default_factory=list, init=False)

    _names: list[str] = field(default_factory=list, init=False)  # names of surfaces
    _nlay_cropper: tuple[int, int] = (0, 0)  # cropping of depth cube

    def __post_init__(self) -> None:
        _logger.debug("Running post init")
        self._check_deprecated_args_order()

        self._get_surface_names()
        self._check_fix_surfaces()

        self._velo_maps_average()
        self._slow_maps_average()

    def _check_deprecated_args_order(self) -> None:
        if isinstance(self.depth_surfaces, xtgeo.Cube):
            raise ValueError(
                "In the very first version of this, the first argument was a Cube. "
                "However this is not needed as the velocity or slowness model is "
                "stored internally as special surfaces."
            )

    def _get_surface_names(self) -> None:
        """Get names of surfaces."""
        if self.names:
            if len(self.names) == len(self.depth_surfaces):
                self._names = self.names
            else:
                raise ValueError(
                    "Surface names are provided but number of names do not match."
                )

        else:
            for num, surf in enumerate(self.depth_surfaces):
                if not surf.name:
                    self._names.append(f"surf_{num}")
                else:
                    self._names.append(surf.name)

    def _check_fix_surfaces(self) -> None:
        """Check that depth and time surfaces are consistent and fix if needed."""

        _logger.debug("Check and fix surfaces...")

        template_surf = self.template if self.template else self.time_surfaces[-1]

        if len(self.depth_surfaces) != len(self.time_surfaces):
            raise ValueError("The number of depth and time surfaces must be equal.")

        _logger.debug("Depth and time input surfaces seems to be equal in number, OK")

        self._d_surfaces = self._resample_check_surfaces(
            self.depth_surfaces, template_surf, fill=True, ensure_consistency=True
        )
        self._t_surfaces = self._resample_check_surfaces(
            self.time_surfaces, template_surf, fill=True, ensure_consistency=True
        )
        self._ensure_surfaces_has_msl()
        _logger.debug("Check and fix surfaces... DONE")

    @staticmethod
    def _recreate_cube_from_msl(
        incube: xtgeo.Cube, resample: bool = False
    ) -> xtgeo.Cube:
        """If input cube does does start from MSL; create a cube where zori=0"""
        _logger.debug("Recreate cube from MSL (if needed)...")
        if incube.zori != 0.0:
            zmax = DomainConversion.max_depth_for_cube(incube)
            new_nlay = int(zmax / incube.zinc) + 1

            rounding = 4 if incube.zinc > 0.5 else 6
            shift_mapping = round(incube.zori / incube.zinc, rounding)
            shift_mapping = int(shift_mapping) if shift_mapping.is_integer() else 0

            new_cube = xtgeo.Cube(
                ncol=incube.ncol,
                nrow=incube.nrow,
                nlay=new_nlay,
                xinc=incube.xinc,
                yinc=incube.yinc,
                zinc=incube.zinc,
                xori=incube.xori,
                yori=incube.yori,
                zori=0.0,
                yflip=incube.yflip,
                rotation=incube.rotation,
                ilines=incube.ilines,
                xlines=incube.xlines,
                values=0.0,
            )
            if resample:
                if shift_mapping:
                    _logger.debug("Resampling with shift mapping...")
                    new_cube.values[..., shift_mapping:] = incube.values[..., :]
                else:
                    _logger.debug("Resampling with xtgeo resample...")
                    new_cube.resample(incube)  # slower!
            _logger.debug("Recreate cube from MSL (if needed)... DONE")
            return new_cube

        _logger.debug("Recreate cube from MSL (if needed)... not needed!")
        return incube.copy()

    @staticmethod
    def _resample_check_surfaces(
        surflist: list[xtgeo.RegularSurface],
        template: xtgeo.RegularSurface,
        fill: bool = False,
        ensure_consistency: bool = False,
    ) -> list[xtgeo.RegularSurface]:
        """Resample surfaces to match the template surface."""

        # local function
        def _ensure_consistency(
            slist: list[xtgeo.RegularSurface],
        ) -> list[xtgeo.RegularSurface]:
            """Ensure consistensy and check order for depth or time surfaces"""
            for inum in range(1, len(slist)):
                s0 = slist[inum - 1]
                s1 = slist[inum]
                diff = s1 - s0
                if diff.values.mean() < 0:
                    raise ValueError(
                        "Depth/time surfaces must be increasing in depth/time."
                    )

                slist[inum].values = np.where(
                    slist[inum].values < s0.values, s0.values, slist[inum].values
                )

            return slist

        new_surfs = []
        tmpl = template.copy()
        for surf in surflist:
            tmpl.resample(surf)
            if fill:
                tmpl.fill()
            new_surfs.append(tmpl.copy())

        if ensure_consistency:
            return _ensure_consistency(new_surfs)

        return new_surfs

    def _ensure_surfaces_has_msl(self) -> None:
        """Ensure resampled (internal) surface input has a MSL surface.

        If so, it will still insert a __MSL surface as the first surface in the list
        to avoid potential issues.
        """
        _logger.debug("Ensure surfaces has __MSL (for internal consistency)")

        msl = self._d_surfaces[0].copy()
        msl.values = 0.0
        self._d_surfaces.insert(0, msl)
        self._names.insert(0, "__MSL")

        msl = self._t_surfaces[0].copy()
        msl.values = 0.0
        self._t_surfaces.insert(0, msl)
        if self._names[0] != "__MSL":
            self._names.insert(0, "__MSL")

    def _velo_maps_average(self) -> None:
        """Create average velocities from MSL to surface N"""

        _logger.debug("Create velocity maps for average velocities from MSL...")
        vel = []
        for no in range(1, len(self._d_surfaces)):
            t0 = self._t_surfaces[0]
            t1 = self._t_surfaces[no]
            d0 = self._d_surfaces[0]
            d1 = self._d_surfaces[no]

            vspeed = d1.copy()
            tdiff = t1.values - t0.values
            tdiff = np.where(tdiff == 0.0, 1e-06, tdiff)
            vspeed.values = np.divide((d1.values - d0.values), tdiff)
            vspeed.values *= 2000
            vel.append(vspeed)

        vel.insert(0, vel[0])
        self._v_surfaces = vel
        _logger.debug("Create velocity maps for average velocities from MSL...  DONE")

    def _slow_maps_average(self) -> None:
        """Create average slowness from MSL to surface N"""

        _logger.debug("Create slowness maps averages from MSL...")
        slow = []
        for no in range(1, len(self._d_surfaces)):
            t0 = self._t_surfaces[0]
            t1 = self._t_surfaces[no]
            d0 = self._d_surfaces[0]
            d1 = self._d_surfaces[no]

            vslow = t1.copy()
            ddiff = d1.values - d0.values
            ddiff = np.where(ddiff == 0.0, 1e-06, ddiff)
            vslow.values = np.divide((t1.values - t0.values), ddiff)
            vslow.values /= 2000
            slow.append(vslow)

        slow.insert(0, slow[0])
        self._s_surfaces = slow
        _logger.debug("Create slowness maps for average from MSL...  DONE")

    def _check_surfaces_are_inside_area(
        self, insurfs: list[xtgeo.RegularSurface]
    ) -> None:
        """Check that the input surfaces are inside the area that makes the DC model.

        This is to ensure that the domain conversion becomes correct, and will raise
        an error if the input surfaces (edges) are not inside the surfaces that made
        the area for domain conversion.

        See also `_domain_convert_surfaces`.
        """
        _logger.debug("Check that the input surfaces are inside the model area.")

        tmpl = self._d_surfaces[0].copy()
        for num, surf in enumerate(insurfs):
            # need to fill here as internal holles in input is ok. It is the outer
            # area that is important:
            filled_surf = surf.copy()
            filled_surf.fill()
            tmpl.resample(filled_surf)
            # check if masked values are present
            if tmpl.values.mask.any():
                raise ValueError(
                    f"Input surface no. {num} ({surf.name}) is not fully inside "
                    "the model area."
                )

    def _check_cube_is_inside_surfaces(self, incube: xtgeo.Cube) -> None:
        """Check that the input cube is inside the surfaces that makes the DC model.

        This is to ensure that the domain conversion becomes correct, and will raise
        an error if the input cube is not inside the surfaces.
        """
        _logger.debug("Check that the input cube is inside the surfaces")

        tmpl = xtgeo.surface_from_cube(incube, value=-999)

        tmpl.resample(self._d_surfaces[0])
        # check if masked values are present
        if tmpl.values.mask.any():
            raise ValueError("Input cube is not fully inside the model area.")

    def _resample_surfaces_to_cube(
        self, incube: xtgeo.Cube, time2depth: bool = True
    ) -> tuple[list[xtgeo.RegularSurface], list[xtgeo.RegularSurface]]:
        """Resample surfaces to match the input cube.

        The time and velocity surfaces do already exist, but they are not sampled the
        actual cube, so we do that here.
        """
        _logger.debug("Resample surfaces to cube")
        xsurfs = self._t_surfaces if time2depth else self._d_surfaces  # time or depth
        ssurfs = self._v_surfaces if time2depth else self._s_surfaces  # "speed"

        incube_template = xtgeo.surface_from_cube(incube, value=0)

        x_surfaces = self._resample_check_surfaces(
            xsurfs, incube_template, fill=True, ensure_consistency=True
        )
        s_surfaces = self._resample_check_surfaces(
            ssurfs, incube_template, fill=True, ensure_consistency=False
        )  # intended: do not ensure consistency of velocities

        return x_surfaces, s_surfaces

    @staticmethod
    def max_depth_for_cube(cube: xtgeo.Cube) -> float:
        """Calculate the maximum depth for a cube."""
        return cube.zori + (cube.nlay - 1) * cube.zinc

    def _extend_incube_create_speed_cube_average(
        self, incube: xtgeo.Cube, time2depth: bool = True
    ) -> None:
        """Extend incube to MSL and from that create speed cube with avg speed.

        A "speed" cube is either a velocity cube in time or a slowness cube in depth.
        """

        _logger.debug("Incube dimensions: %s", incube.values.shape)

        _incube = self._time_cube if time2depth else self._depth_cube
        result_description = "velocity" if time2depth else "slowness"
        _speed = self._vcube_t if time2depth else self._scube_d

        _incube = self._recreate_cube_from_msl(incube, resample=True)

        _logger.debug("Incube extended to MSL dimensions: %s", _incube.values.shape)

        _logger.debug("Create average %s cube", result_description)
        _speed = _incube.copy()

        incube_arr = [
            _incube.zori + n * _incube.zinc for n in range(_incube.values.shape[2])
        ]

        speedcube_values = np.zeros_like(_incube.values)

        # resample surfaces to match the input cube
        x_surfaces, s_surfaces = self._resample_surfaces_to_cube(_incube, time2depth)

        xlen = len(x_surfaces)
        slen = len(s_surfaces)

        assert xlen == slen

        for i in range(speedcube_values.shape[0]):
            for j in range(speedcube_values.shape[1]):
                xmap = [x_surfaces[num].values[i, j] for num in range(xlen)]
                smap = [s_surfaces[num].values[i, j] for num in range(slen)]

                speedcube_values[i, j, :] = np.interp(incube_arr, xmap, smap)

        _speed.values = speedcube_values

        # update references
        if time2depth:
            _logger.debug("Update internal time cube and velocity cube")
            self._time_cube = _incube
            self._vcube_t = _speed
        else:
            _logger.debug("Update internal depth cube and slowness cube")
            self._depth_cube = _incube
            self._scube_d = _speed

    def _derive_result_cube_design(
        self,
        incube: xtgeo.Cube,
        zinc_proposed: float | None,
        zmin_proposed: float | None,
        zmax_proposed: float | None,
        time2depth: bool = True,
    ) -> None:
        """Derive a result cube from a time/depth cube, optional params etc."""
        _logger.debug("Derive result cube design...")

        compare_surfs = self._d_surfaces if time2depth else self._t_surfaces
        scube = self._vcube_t if time2depth else self._scube_d

        # next, the initial proposed zori and zmax for the depth cube; from the surfaces
        zmin_estimated = compare_surfs[1].values.min()
        zmax_estimated = compare_surfs[-1].values.max()
        _logger.debug(
            "Zmin and zmax for relevant surfaces is %s %s (time2deph: %s)",
            zmin_estimated,
            zmax_estimated,
            time2depth,
        )

        zdiff = zmax_estimated - zmin_estimated
        zmin_new = zmin_proposed if zmin_proposed else zmin_estimated - zdiff * 0.1
        zmin_new = 0.0 if zmin_new < 0.0 else zmin_new

        zmax_new = zmax_proposed if zmax_proposed else zmax_estimated + zdiff * 0.1

        if not zinc_proposed:
            # e.g. if time2depth:
            # the zinc from the time cube corresponds to the TWT in ms, and can be used
            # to derive the depth cube zinc in meters based on the average velocity cube
            # (or the slowness cube if depth2time).
            median = np.median(scube.values)
            if time2depth:
                zinc_actual = median * incube.zinc / 2000
            else:
                zinc_actual = median * incube.zinc * 2000
            # round to nearest 0.1
            zinc_actual = round(zinc_actual, 1)
        else:
            zinc_actual = zinc_proposed

        _logger.debug("Estimated or hard set (actual) zinc is %s", zinc_actual)

        zori = round(zmin_new, 1)
        # this is the amount of cells above zori
        nlay_above = int(zori / zinc_actual)
        # assure that zori is a whole number multiple of zinc_depth starting from 0.0
        zori = nlay_above * zinc_actual
        nlay = int((zmax_new - zori) / zinc_actual) + 1 + nlay_above

        zmax_new = zori + (nlay - 1) * zinc_actual

        _logger.debug("Proposed vs actual ZINC: %s : %s", zinc_proposed, zinc_actual)
        _logger.debug("Proposed vs actual ZMIN: %s : %s", zmin_proposed, zori)
        _logger.debug("Proposed vs actual ZMAX: %s : %s", zmax_proposed, zmax_new)
        _logger.debug(
            "NLAY (from MSL) vs NLAY (when cropped): %s : %s", nlay, nlay - nlay_above
        )

        # now create the depth cube, but from 0, not zori
        # (to later be cropped with nlay_above)
        xinv_cube = xtgeo.Cube(
            xori=incube.xori,
            yori=incube.yori,
            zori=0.0,
            ncol=incube.ncol,
            nrow=incube.nrow,
            nlay=nlay,
            xinc=incube.xinc,
            yinc=incube.yinc,
            zinc=zinc_actual,
            rotation=incube.rotation,
            yflip=incube.yflip,
            ilines=incube.ilines,
            xlines=incube.xlines,
            values=0.0,
        )
        if time2depth:
            self._depth_cube = xinv_cube
        else:
            self._time_cube = xinv_cube

        self._nlay_cropper = (nlay_above, 0)

    def _domain_convert_surfaces(
        self, insurfs: list[xtgeo.RegularSurface], time2depth: bool = True
    ) -> list[xtgeo.RegularSurface]:
        """Use current average model to perform generic domain conversion for surfaces.

        Args:
            insurfs: List of xtgeo surface objects (in time or depth domain) to convert.
            time2depth: If True, convert time to depth, otherwise depth to time.
        """
        _logger.info("Domain convert surfaces... time->depth is: %s", time2depth)

        self._check_surfaces_are_inside_area(insurfs)

        # Assuming the first surface in the list is the time surface

        xsurfs = self._t_surfaces if time2depth else self._d_surfaces
        ssurfs = self._v_surfaces if time2depth else self._s_surfaces

        original_surf = insurfs[0].copy()
        insurfs_resampled = self._resample_check_surfaces(
            insurfs, xsurfs[0], fill=True, ensure_consistency=False
        )

        # Stack the time and velocity surfaces for vectorized operations
        x_stack = np.stack([srf.values for srf in xsurfs], axis=-1)
        s_stack = np.stack([srf.values for srf in ssurfs], axis=-1)
        x_stack_flat = x_stack.reshape(-1, x_stack.shape[-1])
        s_stack_flat = s_stack.reshape(-1, s_stack.shape[-1])

        for surf in insurfs_resampled:
            in_values = surf.values.data

            # Flatten the arrays for interpolation
            in_flat = in_values.flatten()

            # Interpolate velocities for all points at once
            speed_flat = np.array(
                [
                    np.interp(xin, x_stack_flat[i], s_stack_flat[i])
                    for i, xin in enumerate(in_flat)
                ]
            )

            # Reshape the interpolated velocities back to the original shape
            speed_values = speed_flat.reshape(in_values.shape)

            # Calculate depth and update resampled surface values
            if time2depth:
                result_values = in_values * speed_values / 2000
            else:
                result_values = in_values * speed_values * 2000

            surf.values = np.ma.array(result_values, mask=surf.values.mask)

        result = []
        # Resample back to original topology for surfaces
        for srf in insurfs_resampled:
            smp = original_surf.copy()
            smp.resample(srf, mask=True)
            result.append(smp)

        _logger.info("Domain convert surfaces... DONE")
        return result

    def _domain_convert_cube(
        self,
        incube: xtgeo.Cube,
        zinc_proposed: float | None = None,
        zmin_proposed: float | None = None,
        zmax_proposed: float | None = None,
        undefined: float = -999.25,
        time2depth: bool = True,
    ) -> xtgeo.Cube:
        """Generic domain conversion of a cube.

        From the time or depth incube, create a an average speed cube and convert.
        """
        _logger.info("Domain convert cube... time->depth is: %s", time2depth)

        self._check_cube_is_inside_surfaces(incube)

        # create a velocity cube from the input time cube (incube)
        self._extend_incube_create_speed_cube_average(incube, time2depth=time2depth)

        # create a depth cube from the time cube (incube) in the best manner
        self._derive_result_cube_design(
            incube, zinc_proposed, zmin_proposed, zmax_proposed, time2depth=time2depth
        )

        xcube = self._time_cube if time2depth else self._depth_cube
        scube = self._vcube_t if time2depth else self._scube_d

        # do the actual depth conversion...
        assert scube.values.shape == xcube.values.shape

        delta = xcube.zinc / 2000 if time2depth else xcube.zinc * 2000
        vertical = xcube.copy()  # "vertical" is "times" if time2depth is True
        varr = [0 + n * delta for n in range(xcube.values.shape[2])]
        vertical.values[:, :, :] = varr
        result_values = scube.values * vertical.values

        rcube = self._depth_cube if time2depth else self._time_cube

        zmax_actual = self.max_depth_for_cube(rcube)

        _logger.debug("Zmax for depth cube is %s", zmax_actual)

        start = rcube.zori
        stop = zmax_actual + rcube.zinc
        num_steps = int((stop - start) / (rcube.zinc - np.finfo(np.float32).eps))
        new_vertical_axis = np.linspace(start, stop, num_steps)

        seismic_attribute_result_cube = np.full(rcube.values.shape, undefined)
        # Perform the interpolation for each (x, y) location
        for i in range(xcube.values.shape[0]):
            for j in range(xcube.values.shape[1]):
                result_trace = result_values[i, j, :]
                seismic_trace = xcube.values[i, j, :]

                seismic_attribute_result_cube[i, j, :] = np.interp(
                    new_vertical_axis,
                    result_trace,
                    seismic_trace,
                )

        if np.isnan(seismic_attribute_result_cube.sum()):
            _logger.warning(
                "Result cube contains NAN, will be replaced with %s", undefined
            )
            seismic_attribute_result_cube[np.isnan(seismic_attribute_result_cube)] = (
                undefined
            )

        rcube.values = seismic_attribute_result_cube

        _logger.info("Cropping result cube with %s", self._nlay_cropper)
        rcube.do_cropping((0, 0), (0, 0), self._nlay_cropper)
        _logger.info("Domain convert cube... DONE")

        return rcube

    # ==================================================================================
    # Public methods and properties
    # ==================================================================================

    def surface_names(self) -> Generator[str]:
        """Return a generator of surface names."""
        for name in self._names:
            yield name

    def velocity_surfaces(self) -> Generator[xtgeo.RegularSurface]:
        """Return a generator of velocity surfaces."""
        for surf in self._v_surfaces:
            yield surf

    def slowness_surfaces(self) -> Generator[xtgeo.RegularSurface]:
        """Return a generator of slowness surfaces."""
        for surf in self._s_surfaces:
            yield surf

    @property
    def average_velocity_cube_in_time(self) -> xtgeo.Cube | None:
        return self._vcube_t

    @property
    def average_slowness_cube_in_depth(self) -> xtgeo.Cube | None:
        return self._scube_d

    def depth_convert_surfaces(
        self, insurfs: list[xtgeo.RegularSurface]
    ) -> list[xtgeo.RegularSurface]:
        """Use the current average velocity model/surfaces to perform depth conversion.

        Args:
            insurfs: List of xtgeo surface objects (in time domain) to depth convert.
        """
        return self._domain_convert_surfaces(insurfs, time2depth=True)

    def time_convert_surfaces(
        self, insurfs: list[xtgeo.RegularSurface]
    ) -> list[xtgeo.RegularSurface]:
        """Use the average slowness model/cube to perform depth to time conversion.

        Args:
            insurfs: List of xtgeo surface objects to time convert.

        """
        return self._domain_convert_surfaces(insurfs, time2depth=False)

    def depth_convert_cube(
        self,
        incube: xtgeo.Cube,
        zinc: float | None = None,
        zmin: float | None = None,
        zmax: float | None = None,
        undefined: float = -999.25,
    ) -> xtgeo.Cube:
        """Depth convert a cube (time to depth).

        Args:
            incube: Input cube (in time domain) to convert.
            zinc: Proposed z increment for the output cube.
            zmin: Proposed z minimum for the output cube.
            zmax: Proposed z maximum for the output cube.
            undefined: Value to use for undefined values in the output cube.

        Note:
            The proposed zinc, zmin, zmax are optional and will be calculated from the
            existing input surfaces (making the velocity/slowness model) if not
            provided. If given, the actual values may differ from the proposed values,
            for technical reasons.

        """
        return self._domain_convert_cube(
            incube,
            zinc_proposed=zinc,
            zmin_proposed=zmin,
            zmax_proposed=zmax,
            undefined=undefined,
            time2depth=True,
        )

    def time_convert_cube(
        self,
        incube: xtgeo.Cube,
        tinc: float | None = None,
        tmin: float | None = None,
        tmax: float | None = None,
        undefined: float = -999.25,
    ) -> xtgeo.Cube:
        """Time convert a cube (depth to time).

        Args:
            incube: Input cube (in depth domain) to convert.
            tinc: Proposed time increment for the output cube.
            tmin: Proposed time minimum for the output cube.
            tmax: Proposed time maximum for the output cube.
            undefined: Value to use for undefined values in the output cube.

        Note:
            The proposed tinc, tmin, tmax are optional and will be calculated from the
            existing input surfaces (making the velocity/slowness model) if not
            provided. If given, the values may be adjusted for technical
            reasons.
        """
        return self._domain_convert_cube(
            incube,
            zinc_proposed=tinc,
            zmin_proposed=tmin,
            zmax_proposed=tmax,
            undefined=undefined,
            time2depth=False,
        )
