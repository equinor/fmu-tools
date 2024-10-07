from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np
import xtgeo

_logger = logging.getLogger(__name__)


@dataclass
class DomainConversion:
    """Domain conversion, tailored for fmu-sim2seis but also works as standalone.

    The principle is to use matching sets of time and depth surfaces to create a
    velocity (or slowness) cube, and use that further to domain convert either
    seismics or surfaces.
    """

    # input
    cube_template: xtgeo.Cube  # shall be in TWT if time_to_depth
    depth_surfaces: list
    time_surfaces: list
    use_interval_velocity: bool = False
    time_to_depth: bool = True  # if False, it shall make a slowness cube in Depth

    # instance variables (private)
    _cube_tmpl: xtgeo.Cube = field(default=None, init=False)  # actual template cube
    _vcube_t: xtgeo.Cube = field(default=None, init=False)  # avg velocity cube in time
    _vcube_i_t: xtgeo.Cube = field(default=None, init=False)  # intv vel. cube time
    _scube_d: xtgeo.Cube = field(default=None, init=False)  # avg slowness cube in depth
    _v_surfaces: list = field(default_factory=list, init=False)  # velocities
    _s_surfaces: list = field(default_factory=list, init=False)  # slowness
    _d_surfaces: list = field(default_factory=list, init=False)  # depth
    _t_surfaces: list = field(default_factory=list, init=False)  # time

    def __post_init__(self) -> None:
        _logger.debug("Initialize post init")
        self._set_cube_input()

        if self.time_to_depth:
            self._vcube_t = self._cube_tmpl.copy()
            self._vcube_t.values = 0.0
        else:
            self._scube_d = self._cube_tmpl.copy()
            self._scube_d.values = 0.0

        self._d_surfaces = self._resample_surfaces(
            self.depth_surfaces,
            self._cube_tmpl,
            fill=True,
            ensure_consistency=True,
        )
        self._t_surfaces = self._resample_surfaces(
            self.time_surfaces,
            self._cube_tmpl,
            fill=True,
            ensure_consistency=True,
        )

        self._ensure_surfaces_has_msl()
        self._check_cube_input_vs_surfaces()

        # create velocity or slowness cube(s)
        if self.time_to_depth:
            if self.use_interval_velocity:
                self._velo_maps_interval()
                self._create_velo_cubes_interval()
                self._create_velo_cube_average_from_interval()
            else:
                self._velo_maps_average()
                self._create_velo_cubes_average()
        else:
            self._slow_maps_average()
            self._create_slow_cubes_average()

    @staticmethod
    def _recreate_cube_from_msl(incube, resample=False) -> xtgeo.Cube:
        """If input cube does does start from MSL; create a cube where zori=0"""

        if incube.zori != 0.0:
            zmax = incube.zori + (incube.nlay - 1) * incube.zinc
            new_nlay = int(zmax / incube.zinc) + 1

            # assume mapping is unique
            shift_mapping = incube.zori / incube.zinc
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
                values=0.0,
            )
            if resample:
                if shift_mapping:
                    new_cube.values[..., shift_mapping:] = incube.values[..., :]
                else:
                    new_cube.resample(incube)  # slower!
            return new_cube

        return incube

    @staticmethod
    def _resample_surfaces(
        surflist: list[xtgeo.RegularSurface],
        cube: xtgeo.Cube,
        fill: bool = False,
        ensure_consistency: bool = False,
    ) -> list[xtgeo.RegularSurface]:
        # local function
        def _ensure_consistency(
            slist: list[xtgeo.RegularSurface],
        ) -> list[xtgeo.RegularSurface]:
            """Ensure consistensy for depth or time surfaces"""
            for inum in range(1, len(slist)):
                values0 = slist[inum - 1]
                slist[inum].values = np.where(
                    slist[inum].values < values0.values,
                    values0.values,
                    slist[inum].values,
                )

            return slist

        tmpl = xtgeo.surface_from_cube(cube, cube.zori)
        new_surfs = []
        for surf in surflist:
            tmpl.resample(surf)
            tmpl.fill()
            new_surfs.append(tmpl.copy())

        if ensure_consistency:
            return _ensure_consistency(new_surfs)

        return new_surfs

    def _set_cube_input(self) -> None:
        """Set template cube, checking basic requirements on cube input.

        If the input cube does does start from MSL; create a new cube based on the
        geometries from input, ensuring zori is 0.0.
        """
        _logger.debug("Check input data, cube")

        self._cube_tmpl = self._recreate_cube_from_msl(self.cube_template)

    def _ensure_surfaces_has_msl(self) -> None:
        """Ensure resampled surface input has a MSL surface."""
        if self._d_surfaces[0].values.mean() != 0.0:
            msl = self._d_surfaces[0].copy()
            msl.values = 0.0
            self._d_surfaces.insert(0, msl)

        if self._t_surfaces[0].values.mean() != 0.0:
            msl = self._t_surfaces[0].copy()
            msl.values = 0.0
            self._t_surfaces.insert(0, msl)

    def _check_cube_input_vs_surfaces(self) -> None:
        cb = self._cube_tmpl

        # find min and max of depth and time surfaces
        dmin = self._d_surfaces[0].values.min()
        # dmax = self._d_surfaces[-1].values.max()
        tmin = self._t_surfaces[0].values.min()
        tmax = self._t_surfaces[-1].values.max()

        if not tmin == 0.0 and not dmin == 0.0:
            raise ValueError("First time and depth surface must start at 0.0")
        if tmax > cb.zori + cb.zinc * (cb.nlay - 1):
            raise ValueError(
                "The deepest point on the input time surfaces is deeper "
                "than the template cube."
            )

    def _velo_maps_interval(self) -> None:
        """Create velocity maps per interval"""
        _logger.debug("Create velocity maps per interval (for intv velocity)")

        vel = []
        for no in range(1, len(self._d_surfaces)):
            t0 = self._t_surfaces[no - 1]
            t1 = self._t_surfaces[no]
            d0 = self._d_surfaces[no - 1]
            d1 = self._d_surfaces[no]

            vspeed = d1.copy()
            tdiff = t1.values - t0.values
            tdiff[tdiff < 0.1] = 0.1
            vspeed.values = (d1.values - d0.values) / tdiff
            vspeed.values *= 2000
            stddev = np.ma.std(vspeed.values)
            mean = np.ma.mean(vspeed.values)
            low = mean - 2 * stddev
            hig = mean + 2 * stddev

            vspeed.values[vspeed.values < low] = low
            vspeed.values[vspeed.values > hig] = hig
            vel.append(vspeed)

        self._v_surfaces = vel
        _logger.debug("Create velocity maps per interval (for intv velocity) DONE")

    def _create_velo_cubes_interval(self) -> None:
        """Create velocity cubes (in Depth/Time) as interval"""

        self._vcube_i_t = self._vcube_t.copy()
        tc = self._vcube_i_t
        vcube = tc.values.copy()
        darr = [tc.zori + n * tc.zinc for n in range(vcube.shape[2])]
        vcube[:, :, :] = darr

        for num, _ in enumerate(self._v_surfaces):
            vmap = self._v_surfaces[num].copy()
            surf = self._t_surfaces[num].copy()
            tval = np.expand_dims(surf.values, axis=2)
            vval = np.expand_dims(vmap.values, axis=2)
            self._vcube_i_t.values = np.where(vcube >= tval, vval, self._vcube_t.values)

    def _create_velo_cube_average_from_interval(self) -> None:
        """Create average velocity cube from interval velocity cube."""

        arr = self._vcube_i_t.values
        cum = np.cumsum(arr, axis=2)
        cnt = np.arange(1, arr.shape[2] + 1)
        cnt = cnt.reshape(1, 1, -1)
        avg = cum / cnt

        self._vcube_t.values = avg

    def _velo_maps_average(self) -> None:
        """Create average velocities from MSL to surface N"""

        _logger.debug("Create velocity maps for average velocities from MSL -->")
        vel = []
        for no in range(1, len(self._d_surfaces)):
            t0 = self._t_surfaces[0]
            t1 = self._t_surfaces[no]
            d0 = self._d_surfaces[0]
            d1 = self._d_surfaces[no]

            vspeed = d1.copy()
            tdiff = t1.values - t0.values
            vspeed.values = np.divide((d1.values - d0.values), tdiff)
            vspeed.values *= 2000
            vel.append(vspeed)

        vel.insert(0, vel[0])
        self._v_surfaces = vel
        _logger.debug("Create velocity maps for average velocities from MSL...  DONE")

    def _create_velo_cubes_average(self) -> None:
        """Create velocity cubes (in Depth/Time) as average"""

        _logger.debug("Create average velocity cube")
        tc = self._vcube_t
        tcube = tc.values.copy()
        time_arr = [tc.zori + n * tc.zinc for n in range(tcube.shape[2])]

        vcube = np.zeros_like(tcube)
        tlen = len(self._t_surfaces)
        vlen = len(self._v_surfaces)

        assert vlen == tlen

        for i in range(tcube.shape[0]):
            for j in range(tcube.shape[1]):
                tmap = [self._t_surfaces[num].values[i, j] for num in range(tlen)]
                vmap = [self._v_surfaces[num].values[i, j] for num in range(vlen)]

                vcube[i, j, :] = np.interp(time_arr, tmap, vmap)

        self._vcube_t.values = vcube

    def _slow_maps_average(self) -> None:
        """Create average slowness from MSL to surface N"""

        _logger.debug("Create slowness maps averages from MSL -->")
        slow = []
        for no in range(1, len(self._d_surfaces)):
            t0 = self._t_surfaces[0]
            t1 = self._t_surfaces[no]
            d0 = self._d_surfaces[0]
            d1 = self._d_surfaces[no]

            vslow = t1.copy()
            ddiff = d1.values - d0.values
            vslow.values = np.divide((t1.values - t0.values), ddiff)
            vslow.values /= 2000
            slow.append(vslow)

        slow.insert(0, slow[0])
        self._s_surfaces = slow
        _logger.debug("Create slowness maps for average from MSL...  DONE")

    def _create_slow_cubes_average(self) -> None:
        """Create slowness cubes (in Depth) as average"""

        _logger.debug("Create average slowness cube")
        dc = self._scube_d
        dcube = dc.values.copy()
        depth_arr = [dc.zori + n * dc.zinc for n in range(dcube.shape[2])]

        scube = np.zeros_like(dcube)
        dlen = len(self._d_surfaces)
        slen = len(self._s_surfaces)

        assert slen == dlen

        for i in range(dcube.shape[0]):
            for j in range(dcube.shape[1]):
                dmap = [self._d_surfaces[num].values[i, j] for num in range(dlen)]
                smap = [self._s_surfaces[num].values[i, j] for num in range(slen)]

                scube[i, j, :] = np.interp(depth_arr, dmap, smap)

        self._scube_d.values = scube

    @property
    def average_velocity_cube_in_time(self) -> xtgeo.Cube:
        return self._vcube_t

    @property
    def average_slowness_cube_in_depth(self) -> xtgeo.Cube:
        return self._scube_d

    @property
    def interval_velocity_cube_in_time(self) -> xtgeo.Cube:
        return self._vcube_i_t

    @property
    def cube_template_applied(self) -> xtgeo.Cube:
        return self._cube_tmpl

    def depth_convert_cube(
        self,
        incube: xtgeo.Cube,
        zinc: float = 1.0,
        maxdepth: float | None = None,
        undefined: float = -999.25,
    ) -> xtgeo.Cube:
        """Use the current average velocity model/cube to perform depth conversion.

        If the user wants a cropped cube, that can be performed by using xtgeo's
        cropping of the output.

        """
        _logger.info("Depth convert cube...")

        _incube = self._recreate_cube_from_msl(incube, resample=True)

        seismic_attribute_cube = _incube.values
        velocity_cube = self._vcube_t.values

        dt = _incube.zinc / 2000  # TWT in ms. to one way time in s.
        times = _incube.copy()
        tarr = [_incube.zori + n * dt for n in range(_incube.values.shape[2])]
        times.values[:, :, :] = tarr
        depth_cube = velocity_cube * times.values

        new_nlay = int(maxdepth / zinc) + 1 if maxdepth else _incube.nlay

        _logger.debug("NEW NLAY is %s, in vcube %s", new_nlay, self._vcube_t.nlay)
        _logger.debug(self._vcube_t)

        dcube = xtgeo.Cube(
            xori=_incube.xori,
            yori=_incube.yori,
            zori=0.0,
            ncol=_incube.ncol,
            nrow=_incube.nrow,
            nlay=new_nlay,
            xinc=_incube.xinc,
            yinc=_incube.yinc,
            zinc=zinc,
            rotation=_incube.rotation,
            yflip=_incube.yflip,
            values=0.0,
        )
        _logger.debug(dcube)
        zmax = dcube.zori + (dcube.nlay - 1) * dcube.zinc
        _logger.debug("Zmax is %s", zmax)
        new_depth_axis = np.arange(0, zmax + zinc, zinc).astype("float")
        seismic_attribute_depth_cube = dcube.values

        # Perform the interpolation for each (x, y) location
        for i in range(seismic_attribute_cube.shape[0]):
            for j in range(seismic_attribute_cube.shape[1]):
                depth_trace = depth_cube[i, j, :]
                seismic_trace = seismic_attribute_cube[i, j, :]

                seismic_attribute_depth_cube[i, j, :] = np.interp(
                    new_depth_axis,
                    depth_trace,
                    seismic_trace,
                )

        if np.isnan(seismic_attribute_depth_cube.sum()):
            _logger.warning(
                "Result cube contains NAN, will be replaced with %s", undefined
            )
            seismic_attribute_depth_cube[np.isnan(seismic_attribute_depth_cube)] = (
                undefined
            )

        dcube.values = seismic_attribute_depth_cube
        _logger.info("Depth convert cube... DONE")

        return dcube

    # TODO: time_convert... and depth_convert in one generic function
    def time_convert_cube(
        self,
        incube: xtgeo.Cube,
        zinc: float = 1.0,
        maxdepth: float | None = None,
        undefined: float = -999.25,
    ) -> xtgeo.Cube:
        """Use the current average slowness model/cube to perform time conversion.

        If the user wants a cropped cube, that can be performed by using xtgeo's
        cropping of the output.

        """
        _logger.info("Time convert cube...")

        _incube = self._recreate_cube_from_msl(incube, resample=True)

        seismic_attribute_cube = incube.values
        slowness_cube = self._scube_d.values

        dz = _incube.zinc * 2000  # TWT in ms. to one way time in s.
        depths = _incube.copy()
        darr = [_incube.zori + n * dz for n in range(_incube.values.shape[2])]
        depths.values[:, :, :] = darr
        time_cube = slowness_cube * depths.values

        new_nlay = int(maxdepth / zinc) + 1 if maxdepth else _incube.nlay

        _logger.debug("NEW NLAY is %s, in vcube %s", new_nlay, self._scube_d.nlay)

        tcube = xtgeo.Cube(
            xori=_incube.xori,
            yori=_incube.yori,
            zori=0.0,
            ncol=_incube.ncol,
            nrow=_incube.nrow,
            nlay=new_nlay,
            xinc=_incube.xinc,
            yinc=_incube.yinc,
            zinc=zinc,
            rotation=_incube.rotation,
            yflip=_incube.yflip,
            values=0.0,
        )
        zmax = tcube.zori + (tcube.nlay - 1) * tcube.zinc
        new_time_axis = np.arange(0, zmax + zinc, zinc).astype("float")
        seismic_attribute_time_cube = tcube.values

        # Perform the interpolation for each (x, y) location
        for i in range(seismic_attribute_cube.shape[0]):
            for j in range(seismic_attribute_cube.shape[1]):
                time_trace = time_cube[i, j, :]
                seismic_trace = seismic_attribute_cube[i, j, :]

                seismic_attribute_time_cube[i, j, :] = np.interp(
                    new_time_axis,
                    time_trace,
                    seismic_trace,
                )

        if np.isnan(seismic_attribute_time_cube.sum()):
            _logger.warning(
                "Result cube contains NAN, will be replaced with %s", undefined
            )
            seismic_attribute_time_cube[np.isnan(seismic_attribute_time_cube)] = (
                undefined
            )

        tcube.values = seismic_attribute_time_cube
        _logger.info("Time convert cube... DONE")
        return tcube

    def depth_convert_surfaces(
        self, insurfs: list[xtgeo.RegularSurface]
    ) -> list[xtgeo.RegularSurface]:
        """Use the current average velocity model/cube to perform depth conversion.

        Args:
            insurfs: List of xtgeo surface objects to depth convert.

        """
        _logger.info("Depth convert surfaces...")
        vcube = self._vcube_t  # velocity cube in TWT
        tarr = vcube.zori + np.arange(vcube.values.shape[2]) * vcube.zinc  # TWT array
        original_surf = insurfs[0].copy()
        insurfs_resampled = self._resample_surfaces(insurfs, vcube)

        for surf in insurfs_resampled:
            # Extract TWT values and mask
            twt_values = surf.values.data
            mask = surf.values.mask

            # Vectorized interpolation
            depths = np.zeros_like(twt_values)
            valid_mask = ~mask

            # Use advanced indexing for valid TWT values
            twt_valid = twt_values[valid_mask].flatten()
            i_indices, j_indices = np.nonzero(valid_mask)

            # Interpolate velocities
            velocities = np.array(
                [
                    np.interp(t, tarr, vcube.values[i, j, :])
                    for t, i, j in zip(twt_valid, i_indices, j_indices)
                ]
            )

            # Calculate depth
            depths[valid_mask] = twt_valid * velocities / 2000

            # Update surface values with depth-converted values
            surf.values = np.ma.array(depths, mask=mask)

        result = []
        # resample back to original topology for surfaces
        for srf in insurfs_resampled:
            smp = original_surf.copy()
            smp.resample(srf)
            result.append(smp)

        _logger.info("Depth convert surfaces... DONE")
        return result

    def time_convert_surfaces(
        self, insurfs: list[xtgeo.RegularSurface]
    ) -> list[xtgeo.RegularSurface]:
        """Use the average slowness model/cube to perform depth to time conversion.

        Args:
            insurfs: List of xtgeo surface objects to time convert.

        """
        _logger.info("Time convert surfaces...")
        vcube = self._scube_d  # velocity cube in TWT
        tarr = vcube.zori + np.arange(vcube.values.shape[2]) * vcube.zinc  # TWT array
        original_surf = insurfs[0].copy()
        insurfs_resampled = self._resample_surfaces(insurfs, vcube)

        for surf in insurfs_resampled:
            # Extract TWT values and mask
            dep_values = surf.values.data
            mask = surf.values.mask

            # Vectorized interpolation
            times = np.zeros_like(dep_values)
            valid_mask = ~mask

            # Use advanced indexing for valid TWT values
            dep_valid = dep_values[valid_mask].flatten()
            i_indices, j_indices = np.nonzero(valid_mask)

            # Interpolate velocities
            velocities = np.array(
                [
                    np.interp(t, tarr, vcube.values[i, j, :])
                    for t, i, j in zip(dep_valid, i_indices, j_indices)
                ]
            )

            # Calculate depth
            times[valid_mask] = dep_valid * velocities * 2000

            # Update surface values with depth-converted values
            surf.values = np.ma.array(times, mask=mask)

        result = []
        # resample back to original topology for surfaces
        for srf in insurfs_resampled:
            smp = original_surf.copy()
            smp.resample(srf)
            result.append(smp)

        _logger.info("Time convert surfaces... DONE")
        return result
