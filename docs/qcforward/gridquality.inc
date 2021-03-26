
.. _qcforward-gridqualindicators:

Grid quality indicators
-----------------------

This methods checks the grid quality in various ways, similar to the methods
RMS use (with some exceptions). If worse than a given set of limits, either are
warning is given or a full stop of the workflow is forced.

The input to this method is a python dictionary with some defined keys. Note that
the order of keys does not matter.


Grid quality indicators keys
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

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
  level. An explanation is given below.

report
  Result will be written in a CSV file (which e.g. can be used in plotting) on disk.
  (optional)

dump_yaml
  If present, should be a file name where the current data structure is dumped to YAML
  format. Later this YAML file can be edited and applied for a single line input

nametag
  A string to identify the data set. Recommended.

The actions field explained
^^^^^^^^^^^^^^^^^^^^^^^^^^^

The action field in the examples below can be explained likes this:

.. code-block:: python

    "minangle_topbase": [{"warn": "all > 1% when < 80", "stop": "all > 1% when < 50"}]

The first warning is triggered if the perecentage of cells which minimum angle is
less than than 80 degrees, is greater than 1%. Note that:

* The first word must contain ``all`` or ``any``, e.g. ``allcells`` will also work
* There must be spaces between words as shown in example above
* The use of ``%`` is not required, e.g. ``"all > 1 when < 80"`` will also work
* The ``when`` word can be replaces with e.g. ``if`` or ``given``; the important issue
  is that a single word is present

Keys if ran inside RMS
^^^^^^^^^^^^^^^^^^^^^^

grid
  Name of grid icon in RMS (required)
writeicon:
  If inside RMS will write an icon under the given grid if True.


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

    ACTIONS = {
        "minangle_topbase": [
            {"warn": "allcells > 1% when < 80", "stop": "allcells > 1% when < 50"},
            {"warn": "allcells > 50% when < 85", "stop": "all > 10% when < 50"},
            {"warn": "allcells > 50% when < 85"},
        ],
        "collapsed": [{"warn": "all > 20%", "stop": "all > 50%"}],
        "faulted": [{"warn": "all > 20%", "stop": "all > 50%"}],
    }

    QCJOB = qcforward.GridQuality()

    def check():

        usedata = {
            "grid": GRIDNAME,
            "actions": ACTIONS,
            "report": {"file": "../output/qc/gridquality.csv", "mode": "write"},
            "nametag": "ZONELOG",
        }

        QCJOB.run(usedata, project=project)

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
            "actions": ACTIONS,
            "report": {"file": "../output/qc/gridquality.csv", "mode": "write"}
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
