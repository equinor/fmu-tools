Domain conversion
=================

In RMS, domain conversion can be performed through the right-click menu or
dedicated jobs. However, in some cases it is convenient to perform domain
conversion from a script. This module provides pure Python implementations for
converting cubes and surfaces between the time and depth domains.

The functions are based on matching pairs of surfaces in the time and depth
domains. Data is interpolated from the source domain to the target domain using
*average* velocity or slowness. This differs from the RMS domain conversion,
which uses an *interval* velocity model.

For domain conversion of cubes, two trace interpolation methods are available:

- **linear**: Quick, but not fully amplitude preserving. The degree of
  amplitude loss depends on the sampling interval and frequency content. This
  is currently the default method.  
- **fft**: Amplitude preserving, but computationally more expensive. This
  method is planned to become the default in a future release.

Examples
--------

Example 1
^^^^^^^^^

Convert a cube from the time domain to the depth domain.

.. code-block:: python

    import xtgeo
    from fmu.tools import DomainConversion

    cube = xtgeo.cube_from_file("path/to/time_cube/file.segy")  # assume this is in time domain

    depth1 = xtgeo.surface_from_file("path/to/depth/file1.gri")
    depth2 = xtgeo.surface_from_file("path/to/depth/file2.gri")
    time1 = xtgeo.surface_from_file("path/to/time/file1.gri")
    time2 = xtgeo.surface_from_file("path/to/time/file2.gri")

    dc = DomainConversion([depth1, depth2], [time1, time2])

    # now depth convert cube with fft method
    cube_in_depth = dc.depth_convert_cube(cube, zinc=2, method="fft")

    cube_in_depth.to_file("path/to/output/cube_in_depth.segy")


Example 2
^^^^^^^^^

Convert a cube and a surface from the depth domain to the time domain.

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


    dc = DomainConversion(dlist, tlist)

    time_cube = dc.time_convert_cube(cube, tinc=4, method="fft")

    time_other_aslist = dc.time_convert_surfaces([depth_other])

Example 3
^^^^^^^^^

A larger example using cubes and surfaces in an RMS Python environment.

.. code-block:: python

    import xtgeo
    from fmu.tools import DomainConversion


    HORIZONS = ["TopVolantis", "BaseVolantis"]
    AMPL_TIME_CUBE = "seismic--amplitude_far_time--20180101"
    AI_TIME_CUBE = "seismic--relai_near_time--20180101"
    DEPTH_CATEGORY = "DS_velmod"
    TIME_CATEGORY = "TS_time_extracted"
    TIME_CATEGORY_OTHER = "TS_interp"

    # for depth conversion of cubes
    ZINC = 2
    MINDEPTH = 1200
    MAXDEPTH = 2000
    TINC = 3
    MINTIME = 1500
    MAXTIME = 1900
    METHOD = "fft"

    CLIP_CATALOG = "testing_dconv"
    PRJ = project


    def load_input():
        """Load input data, such as cubes and surfaces."""
        amplcube = xtgeo.cube_from_roxar(PRJ, AMPL_TIME_CUBE)
        aicube = xtgeo.cube_from_roxar(PRJ, AI_TIME_CUBE)
        print(f"Loading cubes {AMPL_TIME_CUBE} and {AI_TIME_CUBE}... DONE")

        depthsurfs = []
        timesurfs = []
        for ds in HORIZONS:
            depthsurfs.append(xtgeo.surface_from_roxar(PRJ, ds, DEPTH_CATEGORY))
            timesurfs.append(xtgeo.surface_from_roxar(PRJ, ds, TIME_CATEGORY))
        # read some other time surfaces to be converted
        othertimesurfs = []
        for surf in HORIZONS:
            tsfr = xtgeo.surface_from_roxar(PRJ, surf, TIME_CATEGORY_OTHER)
            othertimesurfs.append(tsfr)

        print("Loading surfaces... DONE")
        return amplcube, aicube, depthsurfs, timesurfs, othertimesurfs


    def create_domain_conversion_model(dsurfs, tsurfs):
        """Create a domain model from matching depth and time surfaces."""
        print("Create domain conversion (velocity/slowness) model...")
        dc = DomainConversion(depth_surfaces=dsurfs, time_surfaces=tsurfs)
        print("Create domain conversion model... DONE")
        return dc


    def _depth_convert_cube(dc, mycube):
        """Depth convert a cube (generic)."""
        print("Depth convert cube...")
        dcube = dc.depth_convert_cube(mycube, zinc=ZINC, zmin=MINDEPTH, zmax=MAXDEPTH, method=METHOD)
        print("Depth convert cube... DONE")
        return dcube


    def _time_convert_cube(dc, dcube):
        """Time convert a cube using the slowness model (generic)."""
        print("Time convert cube...")
        tcube = dc.time_convert_cube(dcube, tinc=TINC, tmin=MINTIME, tmax=MAXTIME, method=METHOD)
        print("Time convert cube... DONE")
        return tcube


    def domain_convert_some_cube(dc, tcube, nickname="something"):
        """Convert a cube to depth and back again for demonstration."""
        dcube = _depth_convert_cube(dc, tcube)
        tcube_again = _time_convert_cube(dc, dcube)  # going back again, for demonstration
        dcube.to_roxar(PRJ, nickname + "_depth")
        tcube_again.to_roxar(PRJ, nickname + "_time_again")
        print(f"Save cubes in RMS... ({nickname}...) DONE")


    def domain_convert_surfaces(dc, othertimesurfs):
        """Convert surfaces between time and depth domains."""
        print("Depth and time convert surfaces...")
        depthsurfaces = dc.depth_convert_surfaces(othertimesurfs)
        # store on clipboard
        for ds, name in zip(depthsurfaces, HORIZONS):
            ds.to_roxar(PRJ, f"{name}_depth", CLIP_CATALOG, stype="clipboard")
        # surfaces back to time domain
        new_timesurfaces = dc.time_convert_surfaces(depthsurfaces)
        # store new timesurfaces on clipboard
        for ts, name in zip(new_timesurfaces, HORIZONS):
            ts.to_roxar(PRJ, f"{name}_time", CLIP_CATALOG, stype="clipboard")
        print("Depth and time convert surfaces... DONE")


    # entry point for script
    if __name__ == "__main__":
        ampl, ai, ds, ts, other = load_input()
        dc = create_domain_conversion_model(ds, ts)

        for nickname, cube in zip(["ampl_test", "ai_test"], [ampl, ai]):
            domain_convert_some_cube(dc, cube, nickname)
        domain_convert_surfaces(dc, other)

        print("Done")



