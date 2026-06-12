Nested Hybrid Grids
====================

.. admonition:: 🧪 Experimental Feature
   :class: warning

   This module is currently experimental. It may undergo breaking changes 
   in future versions without notice.

.. contents:: Table of Contents
   :local:
   :depth: 2

Overview
--------

The ``nestedhybridgrid`` module creates **nested hybrid grids** where a
selected region of a coarse grid is replaced by a refined (subdivided)
sub-grid.  The two grids are merged into a single grid and connected
through Non-Neighbour Connections (NNCs).

The typical workflow is:

1. Define a coarse grid and a region property that marks which cells to
   refine.
2. Call :func:`~fmu.tools.nestedhybridgrid.create_nested_hybrid_grid` to
   produce the merged grid and an NNC table. You may need to export the NNC file to csv
   at this stage.
3. Do rescaling from the original gridmodel (e.g. a finer geogrid) to the merged grid,
   e.g. by using software like RMS.
4. Make another script, that computes transmissibilities with
   :meth:`xtgeo.Grid.get_transmissibilities` passing the NNC table.
5. Export the NNC transmissibilities for the flow simulator.

Quick-start example
-------------------

The example here runs within RMS, but similar workflows can be created for file i/o.

.. code-block:: python

    import xtgeo
    from fmu.tools.nestedhybridgrid import (
        create_nested_hybrid_grid,
    )

    # Load grid and region property
    grid = xtgeo.grid_from_roxar(project, "Simgrid")
    region = xtgeo.gridproperty_from_roxar(project, "Simgrid", "REGION")
    
    # Optionally load any other parameter you wish to preserve on grid
    #zone = xtgeo.gridproperty_from_roxar(project, "Simgrid", "Zone")
    #grid.append_prop(zone)

    # Create nested hybrid grid (e.g. refine region 2 by 2×2×1)
    merged, nnc_table = create_nested_hybrid_grid(
        grid, region, target_region_id=2, refinement=(2, 2, 1)
    )

    # store merged grid in RMS (or file)
    merged.to_roxar(project, "NestedHybrid")

    # Optionally extract and store any necessary parameters from grid
    region2 = merged.get_prop_by_name("REGION")
    region2.to_roxar(project, "NestedHybrid", region2.name)

    # write the NNC pandas to disk; this will be applied for computing NNC's in the next script
    nnc_table.to_csv("path_to_some_csv_file.csv", index=False)


The next step is to do a rescaling from the original geogrid to the merged grid
using e.g. the RMS tool.

Further, we need to create NNC transmissibilities and generate file for flow simulator:

.. code-block:: python

    import pandas as pd
    import xtgeo
    from fmu.tools.nestedhybridgrid import (
        nnc_to_flowsimulator_input,
        nnc_to_gridproperty,
    )

    GNAME = "NestedHybrid"

    # Load grid and region property which may be stored in RMS
    nested = xtgeo.grid_from_roxar(project, GNAME)

    # load the NNC table
    nnc_table = pd.read_csv("path_to_some_nnc_file.csv")


    # Load rescaled property input for transmissibilities and compute
    permx = xtgeo.gridproperty_from_roxar(project, GNAME,"PERMX")
    permy = xtgeo.gridproperty_from_roxar(project, GNAME,"PERMY")
    permz = xtgeo.gridproperty_from_roxar(project, GNAME,"PERMZ")
    ntg   = xtgeo.gridproperty_from_roxar(project, GNAME,"NTG")  # defaults to 1 if no NTG

    # compute transmissibilities. Note that flow simulators do this for the normal cells/faults
    # so strictly speaking, only nnc_hybrid is needed here.
    tranx, trany, tranz, nnc_fault, nnc_hybrid, rbnd = nested.get_transmissibilities(
        permx, permy, permz, ntg, nnc_table=nnc_table
    )

    # Export NNC keyword for Eclipse / OPM Flow
    nnc_to_flowsimulator_input(nnc_hybrid, "some_path/NNC_HYBRID.INC")

    # Or map NNCs onto grid properties for visualisation
    tx_nnc, ty_nnc, tz_nnc = nnc_to_gridproperty(nested, nnc_hybrid)
    tx_nnc.to_roxar(project, GNAME, "TRANX_NNC_QC")  # etc

Concepts
--------

NNC table
^^^^^^^^^

The NNC table is a :class:`~pandas.DataFrame` returned by
``create_nested_hybrid_grid`` with columns:

.. list-table::
   :header-rows: 1
   :widths: 15 60

   * - Column
     - Description
   * - ``I1, J1, K1``
     - Mother cell indices (1-based)
   * - ``I2, J2, K2``
     - Refined cell indices (1-based)
   * - ``DIRECTION``
     - Face direction from the mother cell toward the refined cell
       (``I+``, ``I-``, ``J+``, ``J-``, ``K+``, ``K-``)

This table is passed to :meth:`xtgeo.Grid.get_transmissibilities` via the
``nnc_table`` parameter.  The transmissibility computation uses geometric
face-overlap calculations (Sutherland–Hodgman algorithm) and two-point flux
approximation (TPFA).

Eclipse / OPM Flow export
^^^^^^^^^^^^^^^^^^^^^^^^^^

:func:`~fmu.tools.nestedhybridgrid.nnc_to_flowsimulator_input` writes the
``NNC`` keyword in Eclipse format.  The output file can be included in the
simulator deck:

.. code-block:: text

    INCLUDE
      'NNC_HYBRID.INC' /
