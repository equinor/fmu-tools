Domain conversion
=================

In RMS it is possible to do domain conversion using the menu option, but in
some cases it convenient to be able to convert domains using a script. This
module provides a method to convert domains in pure python.

The functions are based on that we have matching pairs of surfaces for the two
domains. The code will then interpolate the data from the source domain to
the target domain. This will be based on *average* velocity or slowness, in constrast to
the RMS domain conversion which is based on an *interval* velocity model.

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

    dc = DomainConversion([depth1, depth2], [time1, time2])

    # now depth convert cube
    cube_in_depth = dc.depth_convert_cube(cube, zinc=2)

    cube_in_depth.to_file("path/to/output/cube_in_depth.segy")


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


    dc = DomainConversion(dlist, tlist)

    time_cube = dc.time_convert_cube(cube, tinc=4)

    time_other_aslist = dc.time_convert_surfaces([depth_other])

Example 3
^^^^^^^^^

A larger example with cubes and surfaces in RMS python environment.

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
        """Depht convert a cube (generic)."""
        print("Depth convert cube...")
        dcube = dc.depth_convert_cube(mycube, zinc=ZINC, zmin=MINDEPTH, zmax=MAXDEPTH)
        print("Depth convert cube... DONE")
        return dcube
    
    
    def _time_convert_cube(dc, dcube):
        """Time convert a cube using the slowness model (generic)."""
        print("Time convert cube...")
        tcube = dc.time_convert_cube(dcube, tinc=TINC, tmin=MINTIME, tmax=MAXTIME)
        print("Time convert cube... DONE")
        return tcube
    
    
    def domain_convert_some_cube(dc, tcube, nickname="something"):
        """Back and forth with some cube (here AI); demonstrate the conv. of cubes."""
        dcube = _depth_convert_cube(dc, tcube)
        tcube_again = _time_convert_cube(dc, dcube)  # going back again, for demonstration
        dcube.to_roxar(PRJ, nickname + "_depth")
        tcube_again.to_roxar(PRJ, nickname + "_time_again")
        print(f"Save cubes in RMS... ({nickname}...) DONE")
    
    
    def domain_convert_surfaces(dc, othertimesurfs):
        """Use domain model to depth and time convert some other surfaces."""
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
    
    
    