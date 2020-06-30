The qcforward class (in prep.)
==================================

The ``qcforward`` class provides a set of methods (function) to check the result
of various issues during an ensemble run.

Design philosophy
-----------------

* The ``qcforward`` shall be possible to run both inside RMS and outside RMS
* All method shall have a similar appearance
* etc


wellzonation_vs_grid
---------------------------

This method check how the zonelog matches with zonation in the 3D grid. If worse than
a given set of limits, either are warning is given or a full stop of the workflow
is forced.

This workflow will work both in RMS (using ``rmsproject`` key) or outside RMS (using
``gridfile`` and ``wellfiles`` keys).

.. code-block:: python

    from fmu.tools import QCForward

    WELLS = ["WELL1", "WELLS2", "WELL3"]
    ZONELOGNAME = "Zonelog"

    GRIDNAME = "SIMGRID"
    ZONEGRIDNAME = "Zone"

    LIMITS = {
        80: "warn",  # warn if less than 80% match
        60: "halt",  # halt if less than 60% match
    }

    def check():
        qc = QCForward()

        qc.wellzonation_vs_grid(
            rmsproject=project,
            wells=WELLS,
            zonelog=ZONELOGNAME,
            grid=GRIDNAME,
            limits= LIMITS,
        )

    if  __name__ == "__main__":
        check()

grid_statistics
---------------

in prep.
