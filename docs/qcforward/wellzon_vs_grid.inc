.. _qcforward-welzonvsgrid:

Compare well zonation and grid
------------------------------

This method check how the zonelog and/or a perforation log matches with zonation in
the 3D grid. If worse than a given set of limits, either are warning is given or a
full stop of the workflow is forced.

<https://xtgeo.readthedocs.io/en/latest/_images/zone-well-mismatch-plain.svg>


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

actions
  This is a list of dictionaries that shows what actions which shall be
  performed per well (any) or for the average (all), for example ``{"warn": "all < 50", "stop": "all < 30"}``
  which means that match < than 50% will trigger a warning, while a
  match < 30% will trigger a stop in work flow. Note that ``any`` and ``all``
  shall not be mixed in the same record (required).

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


.. _welzon-vs-grid-known-issues:

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
    ZLOGRANGE = [1,3]
    ZLOGSHIFT = -1
    REPORTPATH = "/tmp/well_vs_grid.csv"

    ACT = [
      {"warn": "any < 90", "stop": "any < 70"},
      {"warn": "all < 95", "stop": "all < 80"},
    ]

    QCJOB = qcforward.WellZonationVsGrid()

    def check():

        usedata = {
            "wells": {"names": WELLS, "logrun": LOGRUN, "trajectory": TRAJ},
            "zonelog": {"name": ZONELOGNAME, "range": ZLOGRANGE, "shift": ZLOGSHIFT},
            "grid": GRIDNAME,
            "depthrange": DRANGE,
            "gridprops": [ZONEGRIDNAME],
            "actions": ACT,
            "report": REPORTPATH,
            "nametag": "ZONELOG",
        }

        QCJOB.run(usedata, project=project)

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
            "actions": ACT,
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

    ACT = [
      {"warn": "any < 90", "stop": "any < 70"},
      {"warn": "all < 95", "stop": "all < 80"},
    ]

    def check():
        qcf.wellzonation_vs_grid(USEDATA, project=project)

    if  __name__ == "__main__":
        check()

The YAML file may in case look like:

.. code-block:: yaml

    actions:
      - {"warn": "all < 70", "stop": "all < 60"}
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

    ACT1 = [
      {"warn": "any < 90", "stop": "any < 70"},
      {"warn": "all < 95", "stop": "all < 80"},
    ]

    ACT2 = [
      {"warn": "any < 80", "stop": "any < 70"},
      {"warn": "all < 75", "stop": "all < 60"},
    ]

    ACT_EACH1 = {"warn<": 90, "stop<": 70}
    ACT_ALL1 = {"warn<": 95, "stop<": 80}

    QCJOB = qcf.WellZonationVsGrid()


    def check():

        usedata1 = {
            "wells": {"names": WELLS1, "logrun": LOGRUN, "trajectory": TRAJ},
            "zonelog": {"name": ZONELOGNAME, "range": [1, 5], "shift": -2},
            "grid": GRIDNAME,
            "gridzones": [ZONEGRIDNAME],
            "actions": ACT1,
            "report": {"file": "../output/qc/well_vs_grid.csv", "mode": "write"},
            "nametag": "SET1",
        }

        # make a copy and modify selected items
        usedata2 = usedata1.copy()
        usedata2["wells"]["names"] = WELLS2
        usedata2["actions"] = ACT2,
        usedata2["report"] = {"file": "../output/qc/well_vs_grid.csv", "mode": "append"}
        usedata2["nametag"] = "SET2"

        # note the "reuse" use to avoid duplicate loading of data like the grid
        qcf.wellzonation_vs_grid(usedata1, project=project)
        qcf.wellzonation_vs_grid(usedata2, project=project, reuse=True)

    if  __name__ == "__main__":
        check()
