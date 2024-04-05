The properties package
======================

The fmu.tools ``properties`` package provides functionality (methods) to special calculations
in e.g. RMS. Currently a library for computing water saturation is present.

Generic water saturation calculations
-------------------------------------

Water saturation in RMS user interface is limited to Leverett J functions and lookup functions.
However there is a need to extend this to Leverett J function which has an additional constant term,
and to BVW and Brooks-Corey methods. The function offers several options:

* Using direct methods (cell mid-point) or integrate across cell thickness
* Look at the center line (vertically) through cells, og use cells corners.
* Both normal and inverse formulation of Leverett J is supported.
* Normalization is supported.

The theory is given in the PDF file provided here: :download:`pdf <pdf/sw_calc.pdf>`.

Note that this library will not give exact same values as RMS built-in Sw GUI will give.
This is partly due to computing height across a cell is a bit different implemented.

The library input is documented here: :meth:`.SwFunction`


Example: Using simple Sw Leverett J
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The Leverett J is given as $S_w = a J^b$, where $J$ is $h\sqrt(k/\phi)$. In this example, the
factors are constant numbers:

.. code-block:: python

    import numpy as np
    import xtgeo
    from fmu.tools.properties import SwFunction

    GRIDNAME = "Geogrid"
    A = 1
    B = -2
    FWL = 1700

    PORONAME = "PHIT"
    PERMNAME = "KLOGH"

    CALC = "integrated"
    METHOD = "cell_corners_above_ffl"

    SW_RESULT = "SwJ"


    def compute_saturation():
        grid = xtgeo.grid_from_roxar(project, GRIDNAME)
        poro = xtgeo.gridproperty_from_roxar(project, GRIDNAME, PORONAME)
        perm = xtgeo.gridproperty_from_roxar(project, GRIDNAME, PERMNAME)

        # avoid zero porosities in the division below
        poro.values[poro.values == 0.0] = 0.01
        x = poro.copy()
        x.values = np.sqrt(np.divide(perm.values, poro.values))

        sw_func = SwFunction(
            grid=grid,
            x=x,
            a=A,
            b=B,
            ffl=FWL,
            invert=True,
            method=METHOD,
        )
        sw = sw_func.compute(CALC)
        sw.values[poro.values < 0.05] = 1.0  # 100% water when low porosity
        sw.to_roxar(project, GRIDNAME, SW_RESULT)


    if __name__ == "__main__":
        compute_saturation()
        print("Done")
