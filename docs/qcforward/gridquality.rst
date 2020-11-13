
.. _qcforward-gridqualindicators:

Grid quality indicators
-----------------------

This methods checks the grid quality in various ways, similar to the methods
RMS use (with some exceptions). If worse than a given set of limits, either are
warning is given or a full stop of the workflow is forced.

The input to this method is a python dictionary with some defined keys. Note that
the order of keys does not matter.


Grid quality indicators keys
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The following qridquality measures are currently supported:

minangle_topbase
  Minimum angle per cell for top and base, in degrees.
maxangle_topbase
  Maximum angle per cell for top and base, in degrees.
minangle_topbase_proj
  Minimum angle per cell for top and base, in degrees, projected in XY view.
maxangle_topbase
  Maximum angle per cell for top and base, in degrees, projected in XY view.
minangle_sides
  Minimum angle for all side surfaces.
maxangle_sides
  Maximum angle for all side surfaces.
collapsed
  One or more corners are collapsed in Z.
faulted
  Grid cell is faulted (which is very OK in most cases).
negative_thickness
  Assign value 1 if cell has negative thickness in one or more corners, 0 else.
concave_proj
  Assign value 1 if a cell is concave in projected XY (bird) view, 0 else.



Common fields (same input inside or outside RMS)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

verbosity
  Level of output while running None, "info" or "debug", default is None. (optional)

actions
  This is a dictionary that shows what actions which shall be performed at well average
  level, for example ``{"warn<": 50, "stop<": 30}`` which means that
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

* Not all RMS grid quality indicators are currently present.


Examples
~~~~~~~~

Example when ran inside RMS
^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    from fmu.tools import qcforward

    GRIDNAME = "SIMGRID"

    # criteria per cell; if a single cell breaks limits
    ACTIONS_CELL = {"minangle_topbase: {"warn<": 60, "stop<": 40},
                    "maxangle_topbase: {"warn>": 110, "stop>": 130}
                    }

    ACTIONS_AVG = {"minangle_topbase: {"warn<": 80, "stop<": 75},
                   "maxangle_topbase: {"warn>": 100, "stop>": 105}
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
