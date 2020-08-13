The qcforward class (in prep.)
==================================

The ``qcforward`` class provides a set of methods (functions) to check the result
of various issues during an ensemble run.

Design philosophy
-----------------

* The client (user) scripts shall be small and simple and easy to use also
  for modellers with little Python experience.
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


Common fields (same input inside or outside RMS)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

verbosity
  Level of output while running None, "info" or "debug", default is None. (optional)

zonelogname
  Name of zonelog, default is "Zonelog" (required)

zonelogrange
  A list with two entries, defining minimum and maximum zone to use (both ends
  are inclusive). Default is [1, 99]. It is recommended to set range explicitly.

depthrange
  A list with two entries, defining minimum and maximum depth to use (both ends
  are inclusive). Default is [0, 9999]. Setting this range to reservoir gross
  interval (e.g. [2200, 3400] will speed up calculations, so it is recommended.

actions_each
  This is a dictionary that shows what actions which shall be performed per well,
  for example ``{"warnthreshold": 50, "stopthreshold": 30}`` which means that match
  < than 50% will trigger a warning, while a match < 30% will trigger
  a stop in work flow. (required)

actions_all
  This is a dictionary that shows what actions which shall be performed at well average
  level, for example ``{"warnthreshold": 50, "stopthreshold": 30}`` which means that
  match < 50% will trigger a warning, while a match < 30% will trigger
  a stop in work flow. (required)

report
  Result will be written in a CSV file (which e.g. can be used in plotting) on disk.
  (optional)

dump_yaml
  If present, should be a file name where the current data structure is dumped to YAML
  format. Later this YAML file can be edited and applied for a single line input


Keys if ran inside RMS
^^^^^^^^^^^^^^^^^^^^^^

wells
  A list of wellnames which in turn can have python valid regular expressions,
  see examples. (required)

logrun
  Name of logrun in RMS, default is "log" (required)

trajectory
  Name of trajectory in RMS, default is "Drilled trajectory" (required)

grid
  Name of grid icon in RMS (required)

zone
  Name of zone icon in RMS (required)


If ran in normal python (terminal or ERT job)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

wells
  Outside RMS, wells must be on RMS ascii well format. File wildcards are
  allowed, se example. (required)

grid
  Name of file with grid (on ROFF or EGRID or GRDECL format) (required)

zone
  A dictionary with name of Zone and assosiated filename, for example
  ``{"Zone", "zone.roff"}``



Known issues
~~~~~~~~~~~~

* The code evaluates of a well sample is inside a grid cell. However, such evaluation
  is non-unique as corner point cells are not necessarly well defined in 3D. Hence
  one may encounter different results if another tool is applied.

* Current only cover ZONELOG match; PERFORATIONS will come


Examples
~~~~~~~~

Example when ran inside RMS:
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    from fmu.tools import QCForward

    # will match all wells starting with 33_10 and all 34_11 wells containing "A"
    # Note that these are python regular expressions!
    WELLS = ["33_10.*", "34_11-.*A.*"]

    ZONELOGNAME = "Zonelog"
    TRAJ = "Drilled trajectory"
    LOGRUN = "log"

    GRIDNAME = "SIMGRID"
    ZONEGRIDNAME = "Zone"

    ACT_EACH = {"warnthreshold": 90, "stopthreshold": 70}
    ACT_ALL = {"warnthreshold": 95, "stopthreshold": 80}

    QCJOB = QCForward()

    def check():

        usedata = {
            wells: WELLS,
            zonelogname: ZONELOGNAME,
            trajectory: TRAJ,
            logrun: LOGRUN,
            grid: GRIDNAME,
            zone: ZONEGRIDNAME,
            actions_each: ACT_EACH
            actions_all: ACT_ALL
            report: {"file": "../output/qc/well_vs_grid.csv", mode: "write"}
        }

        QCJOB.wellzonation_vs_grid(usedata)

    if  __name__ == "__main__":
        check()


Example when ran from python script in terminal:
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    from fmu.tools import QCForward

    WPATH = "../output/wells/"

    # Here typical linux "file globbing" is used
    WELLS = [WPATH + "33_10*.rmswell", WPATH + "34_11-*A*"]
    ZONELOGNAME = "Zonelog"
    PERFLOGNAME = "PERF"

    GRIDNAME = "../output/checks/simgrid.roff"
    ZONEGRIDNAME = {"Zone": "../output/checks/simgrid_zone.roff"}

    QCJOB = QCForward()

    def check():

        usedata = {
            wells: WELLS,
            zonelog: ZONELOGNAME,
            grid: GRIDNAME,
            zone: ZONEGRIDNAME,
            actions_each: ACT_EACH
            actions_all: ACT_ALL
            report: {"file": "../output/qc/well_vs_grid.csv", mode: "write"}
        }

        QCJOB.wellzonation_vs_grid(usedata)

    if  __name__ == "__main__":
        check()

Example in terminal with setting from a YAML file:
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    from fmu.tools import QCForward
    import yaml

    USEDATA = yaml.load("../input/qc/somefile.yml")
    QCJOB = QCForward()

    def check():
        QCJOB.wellzonation_vs_grid(USEDATA)

    if  __name__ == "__main__":
        check()

The YAML file may in case look like:

.. code-block:: yaml

    actions_all: {stopthreshold: 20, warnthreshold: 80}
    actions_each: {stopthreshold: 20, warnthreshold: 50}
    depthrange: [1580, 9999]
    grid: ../xtgeo-testdata/3dgrids/reek/reek_sim_grid.roff
    path: /home/jan/work/git/fmu-tools
    report: {file: somereport.csv, mode: write}
    verbosity: debug
    wells: [../xtgeo-testdata/wells/reek/1/OP*.w, ../xtgeo-testdata/wells/reek/1/WI*.w]
    zone: {Zone: ../xtgeo-testdata/3dgrids/reek/reek_sim_zone.roff}
    zonelogname: Zonelog
    zonelogrange: [1, 3]


Example when ran inside RMS with different settings for wells
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

It may be the case where some wells are less important to match strict
than other wells.

.. code-block:: python

    from copy import deepcopy
    from fmu.tools import QCForward

    # will match all wells starting with 33_10 and all 34_11 wells containing "A"
    # Note that these are python regular expressions!
    WELLS1 = ["33_10.*", "34_11-.*A.*"]
    WELLS2 = ["34_11-.*B.*"]


    ZONELOGNAME = "Zonelog"
    TRAJ = "Drilled trajectory"
    LOGRUN = "log"

    GRIDNAME = "SIMGRID"
    ZONEGRIDNAME = "Zone"

    ACT_EACH1 = {"warnthreshold": 90, "stopthreshold": 70}
    ACT_ALL1 = {"warnthreshold": 95, "stopthreshold": 80}

    ACT_EACH2 = {"warnthreshold": 60, "stopthreshold": 40}
    ACT_ALL2 = {"warnthreshold": 65, "stopthreshold": 50}

    QCJOB = QCForward()

    def check():

        usedata1 = {
            wells: WELLS1,
            zonelogname: ZONELOGNAME,
            trajectory: TRAJ,
            logrun: LOGRUN,
            grid: GRIDNAME,
            zone: ZONEGRIDNAME,
            actions_each: ACT_EACH1
            actions_all: ACT_ALL1
            report: {"file": "../output/qc/well_vs_grid.csv", mode: "write"}
        }

        # make a copy and modify selected items
        usedata2 = deepcopy(usedata1)
        usedata2["wells"] = WELLS2
        usedata2["actions_each"] = ACT_EACH2
        usedata2["actions_all"] = ACT_ALL2
        usedata2["report"] = {"file": "../output/qc/well_vs_grid.csv", mode: "append"}

        QCJOB.wellzonation_vs_grid(usedata1)
        QCJOB.wellzonation_vs_grid(usedata2)


    if  __name__ == "__main__":
        check()



grid_statistics
---------------

in prep!

Example when ran inside RMS:
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

This is just a prototype example (no code yet)

.. code-block:: python

    from fmu.tools import QCForward

    # Provide grid statistics for a selected set of properties


    GRIDNAME = "SIMGRID"
    GRIDPROPS = ["PORO", "PERMX", "SWATINIT"]

    ACT_MEAN = {"PORO": {"warn_outside": [0.2, 0.25], "stop_outside": [0.15, 0.27]}}

    QCJOB = QCForward()

    def check():

        usedata = {
            grid: GRIDNAME,
            props: GRIDPROPS,
            actions_mean: ACT_MEAN,
            report: {"file": "../output/qc/gridstats.csv", mode: "write"},
        }

        QCJOB.grid_statistics(usedata)

    if  __name__ == "__main__":
        check()

