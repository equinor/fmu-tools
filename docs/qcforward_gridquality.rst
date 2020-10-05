Grid quality indicators
-----------------------

This methods checks the grid quality. If worse than a given set of limits, either are
warning is given or a full stop of the workflow is forced.


Signature
~~~~~~~~~

The input to this method is a python dictionary with some defined keys. Note that
the order of keys does not matter.

Grid quality indicators keys
~~~~~~~~~~~~~~~~~~~~~~~~~~~~
minangle_topbase
  Minimum angle per cell for top and base, in degrees
maxangle_topbase
  Maximum angle per cell for top and base, in degress
etc...



Common fields (same input inside or outside RMS)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

verbosity
  Level of output while running None, "info" or "debug", default is None. (optional)

actions
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

nametag
  A string to identify the data set. Recommended.

Keys if ran inside RMS
^^^^^^^^^^^^^^^^^^^^^^

grid
  Name of grid icon in RMS (required)


If ran in normal python (terminal or ERT job)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

grid
  Name of file with grid (on ROFF or EGRID or GRDECL format) (required)

Known issues
~~~~~~~~~~~~

* Not all RMS grid quality indicators are present.


Examples
~~~~~~~~

Example when ran inside RMS
^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    from fmu.tools import qcforward

    GRIDNAME = "SIMGRID"

    # criteria per cell; if a single cell breaks limits
    ACTIONS_CELL = {"minangle_top_base: {"warnthreshold<": 60, "stopthreshold<": 40},
                    "maxangle_top_base: {"warnthreshold>": 110, "stopthreshold>": 130}
                    }

    ACTIONS_AVG = {"minangle_top_base: {"warnthreshold<": 80, "stopthreshold<": 75},
                   "maxangle_top_base: {"warnthreshold>": 100, "stopthreshold>": 105}
                   }

    QCJOB = qcforward.GridQuality()

    def check():

        usedata = {
            "grid": GRIDNAME,
            "actions_each": ACTIONS_CELL,
            "actions_all": ACTIONS_AVG,
            "report": {"file": "../output/qc/gridquality.csv", mode: "write"},
            "nametag": "ZONELOG",
        }

        qcf.run(usedata, project=project)

    if  __name__ == "__main__":
        check()


Example when ran from python script in terminal:
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    from fmu.tools import qcforward


    GRIDNAME = "../output/checks/simgrid.roff"
    ZONEGRIDNAME = ["Zone", "../output/checks/simgrid_zone.roff"]

    QCJOB = qcforward.GridQuality()

    def check():

        usedata = {
            "grid": GRIDNAME,
            "actions_each": ACTIONS_CELL,
            "actions_all": ACTIONS_AVG,
            "report": {"file": "../output/qc/gridquality.csv", mode: "write"}
        }

        QCJOB.run(usedata)

    if  __name__ == "__main__":
        check()

Example in RMS with setting from a YAML file:
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    from fmu.tools import qcforward as qcf
    import yaml

    USEDATA = yaml.load("../input/qc/gridquality.yml", project=project)

    def check():
        qcf.wellzonation_vs_grid(USEDATA, project=project)

    if  __name__ == "__main__":
        check()

The YAML file may in case look like:

  TODO:


