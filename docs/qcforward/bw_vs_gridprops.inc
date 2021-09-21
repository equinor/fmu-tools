.. _qcforward-bwvsprops:

Compare blocked wells with corresponding grid properties
--------------------------------------------------------

This method checks how the blocked well cell properties match with corresponding grid
properties in the 3D grid. If worse than a given set of limits, either a warning is
given or a full stop of the workflow is forced.

The input to this method is a python dictionary with some defined keys. Note that
the order of keys does not matter. It is advised to study the examples further below.


Common fields (same input inside or outside RMS)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

verbosity
  Level of output while running None, "info" or "debug", default is None (optional).

compare:
  A dictionary on the form ``{"Facies": "FACIES", "PHIT": "POROSITY"}`` where the first
  elements are the property name in blocked wells (here ``"Facies, "PHIT"``) and the
  second elements (after the colon) are the corresponding name in the grid properties
  (here ``"FACIES", "POROSITY"``). Note that names can of course be equal.


actions
  This is a list of dictionaries that shows what actions which shall be performed per
  well (any) or for the average (all), for example ``{"warn": "all < 50", "stop": "all <
  30"}`` which means that match < than 50% will trigger a warning, while a match < 30%
  will trigger a stop in work flow. Note that ``any`` and ``all`` shall not be mixed in
  the same record (required). Also both lines are (currently) required.
  Finaly note that these are all equivalent::

    {"warn": "all < 50", "stop": "all <30"}
    {"warn": "allwells < 50", "stop": "allwells <30"}
    {"warn": "allfoo < 50", "stop": "allfoo <30"}

  Hence it is the substrings ``all`` or ``any`` that matters.

report
  Result will be written in a CSV file (which e.g. can be used in plotting) on disk.
  (optional).

dump_yaml
  If present, should be a file name where the current data structure is dumped to YAML
  format. Later this YAML file can be edited and applied for a single line input
  (optional).

nametag
  A string to identify the data set. Recommended.

tolerance
  Provide the tolerance for the match between a blocked well cell and the corresponding
  grid property cell. This tolerance can be given either as an absolute tolerance or a
  relative tolerance. An asolute tolerance can be given on the form ``0.01`` or as a
  dictionary: ``{"abs": 0.01}`` while a relative tolerance shall be given as ``{"rel":
  0.01}``. An absolute tolerance just looks at the absolute value of the difference,
  while a relative tolerance will do a weighting on the mean value from the blocked
  logs, and is thus more sensible to use for input logs with varying average values
  (e.g. porosity and permeability).

show_data
  A string or a dict (or None) if the processed dataset shall be shown to screen as a
  dataframe (table). This can be useful when investigating what wells that trigger e.g.
  a stop. Possible values are None (default, means no output), "yes" just to show all.
  However for a more fine-grained control, using a dict is recommended::

    # show FAIL lines for wells that have status STOP:
    "show_data": {"lines": "FAIL", "wellstatus": "stop"}

    # show FAIL lines for wells that have status WARN:
    "show_data": {"lines": "FAIL", "wellstatus": "warn"}

tvd_range
  A list of two numbers can be applied to limit the vertical range of the comparison.
  The numbers shall represent minimum and maximum depth, and the range is inclusive,
  e.g.::

    "tvd_range" [1200, 2300]

  Note that this setting can exclude whole wells from being evaluated.

Keys if run inside RMS
^^^^^^^^^^^^^^^^^^^^^^

bwells
  In RMS this is a dictionary with 3 fields: ``names``, ``grid`` and ``bwname``.
  The names is a list of wellnames which in turn can have python valid regular
  expressions. See examples. (required).

grid
  Name of grid icon in RMS (required).


If run in normal python (terminal or ERT job)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

bwells
  Outside RMS, wells is a list of files on RMS ascii well format. File wildcards are
  allowed, se example. (required).

grid
  Name of file with grid (in ROFF, EGRID or GRDECL format) (required).

gridprops
  A list of list where the inner list is a pair with name of Zone and assosiated
  filename, for example ``[["Zone", "zone.roff"]]``. This is required when running
  outside RMS but not needed when run inside RMS.


Example when run inside RMS
^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    from pathlib import Path
    import fmu.tools

    GNAME = "Geogrid_Valysar"

    # dict showing "mappings", blocked well version first
    COMPARE1 = {"Facies": "FACIES", "PHIT": "PHIT"}

    BWDATA = {
        "names": ["55.*"],
        "grid": GNAME,
        "bwname": "BW",
    }

    REPORTPATH1 = "../output/qc/bw_vs_prop.csv"

    ACTIONS1 = [
        {"warn": "any < 95%", "stop": "any < 80%"},
        {"warn": "all < 95%", "stop": "all < 90%"},
    ]

    QCJOB = fmu.tools.qcforward.BlockedWellsVsGridProperties()


    def check():

        # make report folder if not present
        reportpath = Path(REPORTPATH1)
        reportpath.parent.mkdir(parents=True, exist_ok=True)

        usezonedata = {
            "bwells": BWDATA,
            "grid": GNAME,
            "actions": ACTIONS1,
            "report": REPORTPATH1,
            "compare": COMPARE1,
            "verbosity": "info",
            "tolerance": {"rel": 0.1},
            "nametag": "BWCHECK",
            "show_data": {"lines": "FAIL", "wellstatus": "stop"},
            "tvd_range": [0, 2700],
        }

        QCJOB.run(usezonedata, project=project)


    if __name__ == "__main__":
        check()

Example when run from python script in terminal
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    from pathlib import Path
    import fmu.tools

    GFILE = "../output/qc/grid/geogrid_valysar.roff"  # has both grid and props
    BWELLFILES = ["../qc/output/wells/bw/valysar*.bw"]

    # dict showing "mappings", blocked well version first
    COMPARE1 = {"Facies": "FACIES", "PHIT": "PHIT"}

    GPROPS = [["FACIES", GFILE], ["PHIT", GFILE]]

    REPORTPATH1 = "../output/qc/bw_vs_prop.csv"

    ACTIONS1 = [
        {"warn": "any < 95%", "stop": "any < 80%"},
        {"warn": "all < 95%", "stop": "all < 90%"},
    ]

    QCJOB = fmu.tools.qcforward.BlockedWellsVsGridProperties()

    def check():

        # make report folder if not present
        reportpath = Path(REPORTPATH1)
        reportpath.parent.mkdir(parents=True, exist_ok=True)

        usezonedata = {
            "bwells": BWELLFILES,
            "grid": GFILE,
            "gridprops": GPROPS,
            "actions": ACTIONS1,
            "report": REPORTPATH1,
            "compare": COMPARE1,
            "verbosity": "info",
            "tolerance": {"rel": 0.1},
            "nametag": "BWCHECK",
            "show_data": "yes",
        }

        QCJOB.run(usezonedata, project=project)


    if __name__ == "__main__":
        check()
