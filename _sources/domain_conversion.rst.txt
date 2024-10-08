Domain conversion
=================

In RMS it is possible to do domain conversion using the menu option, but in
some cases it convenient to be able to convert domains using a script. This
module provides a method to convert domains in pure python.

The functions are based on that we have matching pairs of surfaces for the two
domains. The code will then interpolate the data from the source domain to
the target domain.

Examples
--------

Example 1
^^^^^^^^^

Depth convert a cube from time to depth domain.

.. code-block:: python

    import xtgeo
    from fmu.tools import DomainConversion

    cube = xtgeo.cube_from_file("path/to/time_cube/file.segy")  # assume this is in time domain

    depth1 = xtgeo.surface_from_file("path/to/depth/file1.gri")
    depth2 = xtgeo.surface_from_file("path/to/depth/file2.gri")
    time1 = xtgeo.surface_from_file("path/to/time/file1.gri")
    time2 = xtgeo.surface_from_file("path/to/time/file2.gri")

    dc = DomainConversion(cube, [depth1, depth2], [time1, time2])

    # now depth convert cube
    cube_depth = dc.depth_convert_cube(cube, zinc=2)

    cube_depth.to_file("path/to/output/cube_depth.segy")


Example 2
^^^^^^^^^

Time convert a cube and a surface from depth to time domain.

.. code-block:: python

    import xtgeo
    from fmu.tools import DomainConversion

    cube = xtgeo.cube_from_file("path/to/depth_cube/file.segy")  # assume this is in depth domain

    depth1 = xtgeo.surface_from_file("path/to/depth/file1.gri")
    depth2 = xtgeo.surface_from_file("path/to/depth/file2.gri")
    time1 = xtgeo.surface_from_file("path/to/time/file1.gri")
    time2 = xtgeo.surface_from_file("path/to/time/file2.gri")


    depth_other = xtgeo.surface_from_file("path/to/depth_other.gri")

    dlist = [depth1, depth2]
    tlist = [time1, time2]


    slowness = DomainConversion(cube, dlist, tlist, time_to_depth=False)

    time_cube = slowness.time_convert_cube(cube, zinc=2)

    time_other_aslist = slowness.time_convert_surfaces([depth_other])

Example 3
^^^^^^^^^

A larger example with cubes and surfaces in RMS python environment.

.. code-block:: python

    import xtgeo
    from fmu.tools import DomainConversion

    HORIZONS = ["MSL", "TopVolantis", "BaseVolantis", "BaseVelmodel"]
    MAINHORIZONS = ["TopVolantis", "BaseVolantis"]

    TEMPLATE_CUBE = "seismic--amplitude_far_time--20180101"
    TIME_CUBE = TEMPLATE_CUBE

    AICUBE = "seismic--relai_near_time--20180101"

    DEPTH_CATEGORY = "DS_velmod"

    TIME_CATEGORY = "TS_time_extracted"

    TIME_CATEGORY_OTHER = "TS_interp"

    # for sampling
    ZINC = 2
    MAXDEPTH = 2000

    RESULT_AMPL_DEPTH_CUBE = "seismic--amplitude_far_depth_alt1--20180101"
    RESULT_AICUBE_DEPTH_CUBE = "seismic--relai_near_depth_alt1--20180101"
    RESULT_AICUBE_TIME_CUBE = "seismic--relai_near_time_alt1--20180101"

    CLIP_CATALOG = "testing_dconv"
    GENERIC_DEPTH_HORIZON = "testing_dconv_depth"
    GENERIC_TIME_HORIZON = "testing_dconv_time"


    PRJ = project


    def load_input():
        """Load input data, such as cubes and surfaces."""
        tmplcube = xtgeo.cube_from_roxar(PRJ, TEMPLATE_CUBE)

        aicube = xtgeo.cube_from_roxar(PRJ, AICUBE)

        depthsurfs = []
        timesurfs = []
        for ds in HORIZONS:
            dsrf = xtgeo.surface_from_roxar(PRJ, ds, DEPTH_CATEGORY)
            depthsurfs.append(dsrf)
            tsfr = xtgeo.surface_from_roxar(PRJ, ds, TIME_CATEGORY)
            timesurfs.append(tsfr)

        return tmplcube, aicube, depthsurfs, timesurfs


    def create_velocity_model(tmplcube, dsurfs, tsurfs):
        """Create a velicity model from a template cube and surfaces."""
        print("Create velocity model...")
        vm = DomainConversion(tmplcube, depth_surfaces=dsurfs, time_surfaces=tsurfs)
        print("Create velocity model... DONE")

        return vm


    def create_slowness_model(dcube, dsurfs, tsurfs):
        """Create a slowness model (inverse of velocity model) for depth to time conv."""
        print("Create slowness model...")
        sm = DomainConversion(
            dcube, depth_surfaces=dsurfs, time_surfaces=tsurfs, time_to_depth=False
        )
        print("Create slowness model... DONE")

        return sm


    def depth_convert_cube(vm, mycube):
        """Depht convert a cube."""
        print("Depth convert cube...")
        dcube = vm.depth_convert_cube(mycube, zinc=ZINC, maxdepth=MAXDEPTH)
        print("Depth convert cube... DONE")

        return dcube


    def time_convert_cube(sm, dcube):
        """Time convert a cube using the slowness model."""
        print("Time convert cube...")
        tcube = sm.time_convert_cube(dcube, maxdepth=2000)
        print("Time convert cube... DONE")

        return tcube


    def domain_convert_cubes():
        """Back and forth, to demonstrate the conversion of cubes."""
        tmplcube, aicube, dsurfs, tsurfs = load_input()
        vm = create_velocity_model(tmplcube, dsurfs, tsurfs)  # tmplcube is in time
        dcube = depth_convert_cube(vm, aicube)

        sm = create_slowness_model(dcube, dsurfs, tsurfs)
        tcube = time_convert_cube(sm, dcube)  # going back again, for demonstration

        # do cropping after "work" but prior to save to RMS (limits are just examples)
        dcube.do_cropping((0, 0), (0, 0), (700, 60))
        dcube.to_roxar(PRJ, RESULT_AICUBE_DEPTH_CUBE)

        tcube.do_cropping((0, 0), (0, 0), (1400, 120))
        tcube.to_roxar(PRJ, RESULT_AICUBE_TIME_CUBE)
        print("Crop and save cubes in RMS... DONE")

        return vm, sm  # return velocity and slowness model for further use


    def domain_convert_surfaces(vm, sm):
        """Use velocity and slowness model to depth and time convert some other surfaces."""

        # read some other time surfaces
        othertimesurfs = []
        for surf in MAINHORIZONS:
            tsfr = xtgeo.surface_from_roxar(PRJ, surf, TIME_CATEGORY_OTHER)
            othertimesurfs.append(tsfr)

        depthsurfaces = vm.depth_convert_surfaces(othertimesurfs)

        # store on clipboard
        for no, name in enumerate(MAINHORIZONS):
            ds = depthsurfaces[no]
            ds.to_roxar(
                PRJ, f"{no}_{GENERIC_DEPTH_HORIZON}", CLIP_CATALOG, stype="clipboard"
            )

        # surfaces back to time
        new_timesurfaces = sm.time_convert_surfaces(depthsurfaces)

        # store new timesurfaces on clipboard
        for no, name in enumerate(MAINHORIZONS):
            ts = new_timesurfaces[no]
            ts.to_roxar(
                PRJ, f"{no}_{GENERIC_TIME_HORIZON}", CLIP_CATALOG, stype="clipboard"
            )


    # entry point for script
    if __name__ == "__main__":
        vm, sm = domain_convert_cubes()
        domain_convert_surfaces(vm, sm)

        print("Done")
