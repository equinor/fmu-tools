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

<https://xtgeo.readthedocs.io/en/latest/_images/zone-well-mismatch-plain.svg>


Signature
~~~~~~~~~

The input to this method is a python dictionary with some defined keys. Note that
the order of keys does not matter.


Common fields (same input inside or outside RMS)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

verbosity
  Level of output while running None, "info" or "debug", default is None. (optional)

zonelog:
  A dictionary with keys ``name``, ``range`` and ``shift``, see examples (required)

perflog:
  The name of the perforation log. A dictionary with keys ``name``, ``range``,
  see examples (optional). If present, zonelog matching will be performed only
  in perforation intervals.

well_resample:
  To speed up calulations (but on cost of less precision), the wells are resampled
  every N.n units along the well path. E.g. the value of 3.0 means every 3 meter if a
  metric unit system.

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

nametag
  A string to identify the data set. Recommended.

Keys if ran inside RMS
^^^^^^^^^^^^^^^^^^^^^^

wells
  In RMS this is a dictionary with 3 fields: ``names``, ``logrun`` and ``trajectory``.
  The names is a list of wellnames which in turn can have python valid regular
  expressions. See examples. (required)

grid
  Name of grid icon in RMS (required)

gridprops
  A list of grid properties, in this case the name of zone icon in RMS (required)


If ran in normal python (terminal or ERT job)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

wells
  Outside RMS, wells is a list of files on RMS ascii well format. File wildcards are
  allowed, se example. (required)

grid
  Name of file with grid (on ROFF or EGRID or GRDECL format) (required)

gridprops
  A list of list where the inner list is a pair with name of Zone and assosiated
  filename, for example ``[["Zone", "zone.roff"]]``


Known issues
~~~~~~~~~~~~

* The code evaluates of a well sample is inside a grid cell. However, such evaluation
  is non-unique as corner point cells are not necessarly well defined in 3D. Hence
  one may encounter different results if another tool is applied.


Examples
~~~~~~~~

Example when ran inside RMS
^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    from fmu.tools import qcforward

    # will match all wells starting with 33_10 and all 34_11 wells containing "A"
    # Note that these are python regular expressions!
    WELLS = ["33_10.*", "34_11-.*A.*"]

    ZONELOGNAME = "Zonelog"
    TRAJ = "Drilled trajectory"
    LOGRUN = "log"

    GRIDNAME = "SIMGRID"
    ZONEGRIDNAME = "Zone"
    DRANGE = [2100, 3200]

    ACT_EACH = {"warnthreshold": 90, "stopthreshold": 70}
    ACT_ALL = {"warnthreshold": 95, "stopthreshold": 80}

    QCJOB = qcforward.WellZonationVsGrid()

    def check():

        usedata = {
            "wells": {"names": WELLS, "logrun": LOGRUN, "trajectory": TRAJ},
            "zonelog": {"name": ZONELOGNAME, "range": ZLOGRANGE, "shift": -1},
            "grid": GRIDNAME,
            "depthrange": DRANGE,
            "gridprops": [ZONEGRIDNAME],
            "actions_each": ACT_EACH,
            "actions_all": ACT_ALL,
            "report": "../output/qc/well_vs_grid.csv",
            "nametag": "ZONELOG",
        }

        qcf.run(usedata, project=project)

    if  __name__ == "__main__":
        check()


Example when ran from python script in terminal:
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    from fmu.tools import qcforward

    WPATH = "../output/wells/"

    # Here typical linux "file globbing" is used
    WELLS = [WPATH + "33_10*.rmswell", WPATH + "34_11-*A*"]
    ZONELOGNAME = "Zonelog"
    PERFLOGNAME = "PERF"

    GRIDNAME = "../output/checks/simgrid.roff"
    ZONEGRIDNAME = ["Zone", "../output/checks/simgrid_zone.roff"]

    QCJOB = qcforward.WellZonationVsGrid()

    def check():

        usedata = {
            "wells": WELLS"
            "grid": GRIDNAME,
            "gridprops": [ZONEGRIDNAME],
            "actions_each": ACT_EACH
            "actions_all": ACT_ALL
            "report": "../output/qc/well_vs_grid.csv",
        }

        QCJOB.run(usedata)

    if  __name__ == "__main__":
        check()

Example in RMS with setting from a YAML file:
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    from fmu.tools import qcforward as qcf
    import yaml

    USEDATA = yaml.load("../input/qc/somefile.yml", project=project)

    def check():
        qcf.wellzonation_vs_grid(USEDATA, project=project)

    if  __name__ == "__main__":
        check()

The YAML file may in case look like:

.. code-block:: yaml

    actions_all: {stopthreshold: 20, warnthreshold: 80}
    actions_each: {stopthreshold: 30, warnthreshold: 50}
    depthrange: [1300, 1900]
    grid: Mothergrid
    gridprops: [Zone]
    nametag: TST2
    perflog: null
    report: {file: chk.csv, mode: write}
    verbosity: info
    well_resample: 3
    wells:
      logrun: log
      names: [31_2-D-1_B.*$]
      trajectory: Drilled trajectory
    zonelog:
      name: ZONELOG
      range: [1, 18]
      shift: -1


Example when ran inside RMS with different settings for wells
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

It may be the case where some wells are less important to match strict
than other wells.

.. code-block:: python

    import fmu.tools.qcforward as qcf

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

    QCJOB = qcf.WellZonationVsGrid()


    def check():

        usedata1 = {
            "wells": {"names": WELLS1, "logrun": LOGRUN, "trajectory": TRAJ},
            "zonelog": {"name": ZONELOGNAME, "range": [1, 5], "shift": -2},
            "grid": GRIDNAME,
            "gridzones": [ZONEGRIDNAME],
            "actions_each": ACT_EACH1,
            "actions_all": ACT_ALL1,
            "report": {"file": "../output/qc/well_vs_grid.csv", mode: "write"},
            "nametag": "SET1",
        }

        # make a copy and modify selected items
        usedata2 = usedata1.copy()
        usedata2["wells"]["names"] = WELLS2
        usedata2["actions_each"] = ACT_EACH2
        usedata2["actions_all"] = ACT_ALL2
        usedata2["report"] = {"file": "../output/qc/well_vs_grid.csv", mode: "append"}
        usedata2["nametag"] = "SET2"

        qcf.wellzonation_vs_grid(usedata1, project=project)
        qcf.wellzonation_vs_grid(usedata2, project=project, reuse = True)

    if  __name__ == "__main__":
        check()



grid_statistics
---------------


This method checks if property statistics from 3D grids are within user specified
thresholds. If worse than a given set of limits, either a warning is given or a 
full stop of the workflow is forced.


Signature
~~~~~~~~~~

The input to this method is a python dictionary with some defined keys. Note that
the order of keys does not matter.


Required keys 
^^^^^^^^^^^^^

grid
  Name of grid icon if run inside RMS, or name of file with grid (on ROFF or EGRID or GRDECL format)

actions
  This is a list of dictionaries. Each dictionary specifies a condition to check statistics for,
  and what action should be performed if outside a given thresholds (either warn or stop the workflow). 
  
  Input keys:

  property
    Name of property (either a property icon in RMS, or a file name)

  calculation
    Name of statistical value to check (optional). Default option is "Avg" for continous properties, 
    while other valid options are "Min, Max and Stddev". Default option for discrete properties is "Percent".
    
  
  selectors
    A dictionary of conditions to extract statistics from. e.g. a specific zone and/or region (optional). 

    The key is the name of the property (either a property icon in RMS, or a file name), and the
    value is the code name. 
  
  filters
    A dictionary of filters (optional). The key is the name (or path) to the filter parameter, and the
    value is a dictionary with options "include" or "exclude" where key are the list of values to include/exclude.
    Only discrete parameters are supported.

    For example ``{"ZONE": {"include: ["Zone_1", "Zone_2"]}}``

  stop_outside
    This is a list with two values which defines the minimum and maximum threshold for when to trigger a stop
    of the workflow (required).

    For example ``[0.05, 0.35]`` will give a warning if the statistic is < than 0.05 and > than 0.35.
  
  warn_outside
    Same as warn_outside key above, but instead defines when to give a warning (optional).
  
  description
    A string to describe each action (optional).


Optional fields
^^^^^^^^^^^^^^^

path
  Path to grid property files and grid if run outside RMS (optional)

verbosity
  Level of output while running None, "info" or "debug" (optional). Default is None. 

report
  Name of CSV file to write results to (optional)

dump_yaml
  File name where the current data structure is dumped to YAML format (optional).
  Later this YAML file can be edited and applied for a single line input

nametag
  A string to identify the data set (optional). Recommended.
  

Examples
~~~~~~~~

Example when executed inside RMS (basic):
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    from fmu.tools import qcforward as qcf

    # Check average grid statistics for porosity and permeability

    GRIDNAME = "SimGrid"
    REPORT = "somefile.csv"
    ACTIONS = [
        {
            "property": "PORO",
            "warn_outside": [0.10, 0.25],
            "stop_outside": [0.05, 0.35],
        },
        {
            "property": "PERM",
            "stop_outside": [100, 2000],
        },
    ]

    def check():

        usedata = {
            "grid": GRIDNAME,
            "actions": ACTIONS,
            "report": REPORT,
        }

        qcf.grid_statistics(usedata, project=project)

    if  __name__ == "__main__":
        check()



Example when executed inside RMS (more settings):
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    from fmu.tools import qcforward as qcf

    # Check average grid statistics for the porosity in HC-zone
    # Separate checks for the different zones

    GRIDNAME = "SimGrid"
    REPORT = "somefile.csv"

    ZONE_STOPS = {
        "Top_Zone": [0.05, 0.25],
        "Mid_Zone": [0.15, 0.4],
        "Bottom_Zone": [0.1, 0.3],
    }

    def check():

        actions = []
        for zone, limits in ZONE_STOPS.items():
            actions.append(
                {
                    "property": "PORO",
                    "selectors": {"ZONE": zone},
                    "filters": {"FLUID": {"include": ["Gas", "Oil"]}},
                    "stop_outside": limits,
                },
            )

        usedata = {
            "nametag": "MYDATA1",
            "path": PATH,
            "grid": GRIDNAME,
            "report": REPORT,
            "actions": actions,
        }

        qcf.grid_statistics(usedata, project=project)

    if  __name__ == "__main__":
        check()


Example when executed from python script in terminal:
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.. code-block:: python

    from fmu.tools import qcforward as qcf

    # Check average grid statistics for a porosity

    PATH = "../output/checks/"
    GRIDNAME = "simgrid.roff"
    REPORT = "somefile.csv"

    ACTIONS = [
        {
            "property": "poro.roff",
            "selectors": {"zone.roff": "Top_Zone"},
            "warn_outside": [0.10, 0.25],
            "stop_outside": [0.05, 0.35],
        },
    ]

    def check():

        usedata = {
            path: PATH,
            grid: GRIDNAME,
            actions: ACTIONS,
            report: REPORT,
        }

        qcf.grid_statistics(usedata)

    if  __name__ == "__main__":
        check()


Example in RMS with setting from a YAML file:
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    from fmu.tools import qcforward as qcf
    import yaml

    USEDATA = yaml.load("../input/qc/somefile.yml", project=project)

    def check():
        qcf.grid_statistics(USEDATA, project=project)

    if  __name__ == "__main__":
        check()


The YAML file may in case look like:

.. code-block:: yaml

    grid: Mothergrid
    actions:
    - property: PORO
      stop_outside: [0, 1]
      warn_outside: [0.18, 0.25]
    - property: PORO
      selectors:
        ZONE: Top_Zone
      filters:
        REGION:
          exclude: ["Surroundings"]
      stop_outside: [0, 1]
      warn_outside: [0.18, 0.25]
    path: ../input/qc_files/
    report: somefile.csv
    nametag: QC_PORO
    verbosity: info



