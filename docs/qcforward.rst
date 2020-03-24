The qcforward class (DOC PREVIEW!)
==================================

The ``qcforwards`` class provides a set of methods (function) to check the result
of various issues during an ensemble run.


Check: wellzonation_vs_grid
---------------------------

This method check how the zonelog matches with zonation in the 3D grid. If worse than
a given set of limits, either are warning is given or a full stop of the workflow
is forced.

This workf low will work both in RMS (using ``rmsproject`` key) or outside RMS (using
``gridfile`` and ``wellfiles`` keyes).

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


That is all for now, folks.







