The qcforward class (in prep.)
==================================

The ``qcforward`` class provides a set of methods (functions) to check the result
of various issues during an ensemble run.

Design philosophy
-----------------

* The scripts shall be small and simple and easy to use also for modellers with
  little Python experience.
* Input will be a python dictionary, or a YAML file
* The ``qcforward`` methods shall be possible to run both inside RMS and outside RMS
  (e.g. from an ERT job)
* All methods shall have a similar appearance (... as similar as possible)


wellzonation_vs_grid
---------------------

This method check how the zonelog and/or a perforation log matches with zonation in
the 3D grid. If worse than a given set of limits, either are warning is given or a
full stop of the workflow is forced.


Signature
~~~~~~~~~

The input to this method is a python dictionary with the following keys:

If ran inside RMS:

* wells: A list of wellnames which in turn can have wildcards.
* zonelog: Name of zonelog
* perflog: Perforations shall be present as flag log, where values > 0 means that a
  perforation is present
* trajectory: Name of trajectory in RMS
* logrun: Name of logrun
* grid: Name of grid (if inside RMS) or name of grid file (outside RMS)
* zone: Name of "Zone" property (if inside RMS) or dictionary with name of Zone and
  assosiated filename (if outside RMS)
* limits: This is a new dictionary...

If ran outside RSM:

* wells: Outside RMS, wells must be on RMS ascii well format and a separate log
  representing measured depth (MD) must be present.
* zonelog: Name of zonelog
* mdlog: Name of log representing measured depth (MD)
* perflog: Perforations shall be present as flag log, where values > 0 means that a
  perforation is present
* grid: Name of grid file
* zone: A dictionary with name of Zone and assosiated filename
* limits: This is a new dictionary...


Known issues
~~~~~~~~~~~~

* The code evaluates of a well sample is inside a grid cell. However, such evaluation
  is non-unique as corner point cells are not necessarly well defined in 3D. Hence
  one may encounter different results if another tool is applied.


Examples
~~~~~~~~

Example when ran inside RMS:

.. code-block:: python

    from fmu.tools import QCForward

    WELLS = ["33_10*", "34_11-*A*"]
    ZONELOGNAME = "Zonelog"
    PERFLOGNAME = "PERF"
    TRAJ = "Drilled trajectory"
    LOGRUN = "log"

    GRIDNAME = "SIMGRID"
    ZONEGRIDNAME = "Zone"

    LIMITS = {
        80: "warn",  # warn if less than 80% match
        60: "halt",  # halt if less than 60% match
    }

    def check():
        qc = QCForward()

        usedata = {
            wells: WELLS,
            zonelog: ZONELOGNAME,
            trajectory: TRAJ,
            logrun: LOGRUN,
            grid: GRIDNAME,
            zone: ZONEGRIDNAME,
            limits: LIMITS
        }

        qc.wellzonation_vs_grid(usedata)

    if  __name__ == "__main__":
        check()

Example when ran from python script in terminal:

.. code-block:: python

    from fmu.tools import QCForward

    WPATH = "../output/wells/"
    WELLS = [WPATH + "33_10*.rmswell", WPATH + "34_11-*A*"]
    ZONELOGNAME = "Zonelog"
    PERFLOGNAME = "PERF"

    GRIDNAME = "../output/checks/simgrid.roff"
    ZONEGRIDNAME = {"Zone": "../output/checks/simgrid_zone.roff"}

    LIMITS = {
        80: "warn",  # warn if less than 80% match
        60: "halt",  # halt if less than 60% match
    }

    def check():
        qc = QCForward()

        usedata = {
            wells: WELLS,
            zonelog: ZONELOGNAME,
            grid: GRIDNAME,
            zone: ZONEGRIDNAME,
            limits: LIMITS
        }

        qc.wellzonation_vs_grid(usedata)

    if  __name__ == "__main__":
        check()

Example when ran from python script in terminal with setting from a YAML file:

.. code-block:: python

    from fmu.tools import QCForward
    import yaml

    USEDATA = yaml.load("somefile.yml")

    def check():
        qc = QCForward()
        qc.wellzonation_vs_grid(USEDATA)

    if  __name__ == "__main__":
        check()

The YAML file will be in this case look like:

.. code-block:: yaml

    wells:
      - "../output/wells/33_10*.rmswell"
      - "../output/wells/34_11-*A*.rmswell"
    zonelog: Zonelog
    grid: ../output/checks/simgrid.roff
    zone:
      Zone: ../output/checks/simgrid_zone.roff
    limits:
      80: "warn"
      60: "halt"



grid_statistics
---------------

in prep.
