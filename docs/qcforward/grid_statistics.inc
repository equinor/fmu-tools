.. _qcforward-gridstatistics:

Running grid_statistics
-----------------------


This method checks if property statistics from 3D grids are within user specified
thresholds. If worse than a given set of limits, either a warning is given or a
full stop of the workflow is forced.

Both discrete and continous properties are supported.

Signature
^^^^^^^^^

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

  codename
    The discrete property code name to check value for (optional).
    .. note:: A codename is only needed for discrete properties 

  calculation
    Name of statistical value to check (optional). Default option is "Avg",
    while other valid options for continous properties are "Min", "Max" and "Stddev".

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

    .. note:: For discrete properties the statistical value will be reported in fractions. 

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

Example when executed inside RMS (continous properties - basic):
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

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


Example when executed inside RMS (discrete properties - basic):
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    from fmu.tools import qcforward as qcf

    # Check average grid statistics for porosity and permeability

    GRIDNAME = "SimGrid"
    REPORT = "somefile.csv"
    ACTIONS = [
        {
            "property": "Facies",
            "codename": "Sand",
            "selectors": {"Zone": "Top_Zone"},
            "stop_outside": [0.4, 0.8],
        },
        {
            "property": "Facies",
            "codename": "Sand",
            "selectors": {"Zone": "Mid_Zone"},
            "stop_outside": [0.2, 0.5],
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

Example when executed inside RMS (continous properties - more settings):
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

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
                    "selectors": {"Zone": zone},
                    "filters": {"FLUID": {"include": ["Gas", "Oil"]}},
                    "stop_outside": limits,
                },
            )

        usedata = {
            "nametag": "MYDATA1",
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
        Zone: Top_Zone
      filters:
        REGION:
          exclude: ["Surroundings"]
      stop_outside: [0, 1]
      warn_outside: [0.18, 0.25]
    report: somefile.csv
    nametag: QC_PORO
    verbosity: info
