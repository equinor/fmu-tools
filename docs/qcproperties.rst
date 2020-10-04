The qcproperties class
==================================

The ``qcproperties`` class provides a set of methods for extracting property 
statistics from 3D Grids, Raw and Blocked wells.

If several methods of statistics extraction has been run within the instance,
a merged dataframe is available through the 'dataframe' property. 

The methods for statistics extraction can be run individually, or a yaml-configuration
file can be used to enable an automatic run of the methods.

All methods can be run from either RMS python, or from files (e.g. from an ERT job). 

XTGeo is being utilized to get a dataframe from the input parameter data. XTGeo data 
can be reused in the instance to increase performance.


Methods for extracting property statistics
-----------------------------------------------

Three methods exists for extracting property statistics. The method to select 
is dependent on the input data source (3D grid properties, wells or blocked wells). 
Arguments for the methods are similar and described in section below. 

* ``get_grid_statistics``: This method extract property statistics from 3D grid data.
* ``get_well_statistics``: This method extract property statistics from well logs.
* ``get_bwell_statistics``: This method extract property statistics from blocked well logs.


All methods returns a PropStat instance (see decription further down).

.. seealso:: The `Using yaml input for auto execution` section for description of how to use 
             a yaml-configuration file to run the different methods automatically.

Arguments
^^^^^^^^^^
The input `data` is given in a python dictionary (or a YAML file) and will be somewhat 
different for the three methods, and for the two run environments (inside/outside RMS).

**Input arguments:**

* ``data``: The input data as a Python dictionary (required). See valid keys below.
* ``reuse``: Bool to define if XTGeo data should be reused in the instance (optional). 
  Default is False. Alternatively it can be a list for more fine grained control, 
  e.g. ``["grid", "gridprops", "wells"]``
* ``project``: Required for usage inside RMS 


**Valid fields in the 'data' argument:**

Method specific fields:
    grid
         Name of grid icon in RMS, or name of grid file if run outside RMS. Required with the 
         ``get_grid_statistics`` method.
    
    wells
        Required with the ``get_well_statistics`` and the ``get_bwell_statistics`` methods.
        Outside RMS, "wells" is a list of files on RMS ascii well format.

        Inside RMS, "wells" is a dictionary whith 3 fields that depend on the method: 
        
        **get_well_statistics**: 

        ``names``: List of wellnames (optional). Default is all wells.
        ``logrun``: Name of logrun. 
        ``trajectory``: Name of trajectory.

        **get_bwell_statistics**: 

        ``names``: List of wellnames (optional). Default is all wells.
        ``bwname``: Name of BW object in RMS.
        ``grid``: Name of grid that contains the BW object.

        .. note:: Wildcards are supported when running from files, and python valid regular 
                  expressions are supported in "names", see examples.     
        

Common fields:
    properties
        Properties to compute statistics for. Can be given as list or as dictionary.
        If dictionary the key will be the column name in the output dataframe, and
        the value will be a dictionary with valid options:
    
        ``name``: The actual name (or path) of the property / log.
    
        ``weight``: A weight parameter (name or path if outside RMS) (optional)
    
    selectors
        Selectors are discrete properties/logs e.g. Zone. that are used to extract
        statistics for groups of the data (optional). 
        
        Can be given as list or as dictionary.
        If dictionary the key will be the column name in the output dataframe, and
        the value will be a dictionary with valid options:
    
        ``name``: The actual name (or path) of the property / log.
    
        ``include``: List of values to include (optional)
    
        ``exclude``: List of values to exclude (optional)
    
        ``codes``: A dictionary of codenames to update some/all existing codenames (optional). 

        .. note:: The "codes" field can be used to merge code values that the user wants to extract 
                  combined statistics from. This is done by setting the same name on several code 
                  values, as it is the name that are used to group the data.
    
    filters
        Dictionary with additional filter (optional). 
        
        Only discrete parameters are supported. A selector can be input as a filter, this will 
        override any existing filters specified directly on the selector. 
        The key is the name (or path) to the filter parameter / log, and the
        value is a dictionary with one of two options:
        
        ``include``: List of values to include (optional)
    
        ``exclude``: List of values to exclude (optional)

        .. seealso:: Option ``"multiple_filters"`` below which can be used to extract statistics 
                     multiple times with different filters.

    multiple_filters
        Option for extract statistics multiple times with different filters (optional).

        The input is a dictionariy where the keys are the "name" (ID string) for the dataset,
        and the value is the dictionary of filters (Same format as ``filters`` above)

        See examples.
    
    path
        Path to where files are located (optional)
    
    selector_combos
        Bool to turn on/off calculation of statistics for every combination of selectors 
        (optional). Default is True.
        For example, if True and both a ZONE and a REGION parameter is given as selectors,
        statistics for three groups will be calculated: ``["ZONE", "FACIES"], ["ZONE"] and ["REGION"]``. 
        If False the data will only be extracted for one group: ``["ZONE", "FACIES"]``, hence 
        no data is available if the user wants to evaluate statistics per ZONE (or REGION) for the global 
        grid. 
        
        Depending on number of selectors and size of grid, this process may be
        time consuming. 
    
    source
        Source string (optional). Default values depend on the method being executed:
        
        * For **grid statistics** default is the `gridname`
        * For **blocked wells statistics** default is the `name of the blocked wells object` if inside 
          RMS and `blocked_wells` if outside
        * For **well statistics** default is `wells`
    
    name
        ID string for the dataset (optional). Recommended, if not given it will be set equal 
        to the source string. 
    
    csvfile
        Path to output csvfile (optional). A csv-file will only be written, if argument is provided.
    
    verbosity
      Level of output while running None, "info" or "debug", default is None. (optional)



The returned PropStat instance
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
All methods above returns a PropStat instance, with different properties:

dataframe
    The dataframe with statistical data. 

property_dataframe    
    The full dataframe for the properties which is used as input to the statistical 
    aggregations. Note: If filters are used as input, this dataframe will be the filtered. 


Examples
^^^^^^^^^

get_grid_statistics examples
""""""""""""""""""""""""""""""""

**Example in RMS (basic):**

Example extracting statistics for porosity and permeability for each zone and facies. 
Result is written to csv.

.. code-block:: python

    from fmu.tools import QCProperties

    GRID = "GeoGrid"
    PROPERTIES = ["PORO", "PERM"]
    SELECTORS = ["ZONE", "FACIES"]
    REPORT = "../output/qc/somefile.csv"

    usedata = {
        "properties": PROPERTIES,
        "selectors": SELECTORS,
        "grid": GRID,
        "csvfile": REPORT,
    }

    def check():

        qcp = QCProperties()
        qcp.get_grid_statistics(data=usedata, project=project)

    if  __name__ == "__main__":
        check()


**Example in RMS (detailed):**

Example extracting statistics for porosity for each region. Filters 
are used to extract statistics for HC zone and Water zone separately.
Statistics will be combined for regions with code values 2 and 3.
The porosity is weighted on a Total_Bulk parameter.

.. code-block:: python

    from fmu.tools import QCProperties

    GRID = "GeoGrid"
    PROPERTIES = {"PORO": {"name": "PHIT", "weight": "Total_Bulk"}}
    SELECTORS = {
        "REGION": {
            "name": "Regions",
            "exclude": ["Surroundings"],
            "codes": {2: "NS", 3: "NS",},
        }
    }
    REPORT = "../output/qc/somefile.csv"

    FLUID_FILTERS = {
        "HC_zone": {"Fluid": {"include": ["oil", "gas"]}},
        "Water_zone": {"Fluid": {"include": ["water"]}},
    }

    def extract_statistics():

        qcp = QCProperties()

        usedata = {
            "properties": PROPERTIES,
            "selectors": SELECTORS,
            "grid": GRID,
            "multiple_filters": FLUID_FILTERS,
        }
    
        qcp.get_grid_statistics(data=usedata, reuse=True, project=project)

        qcp.to_csv(REPORT)

    if  __name__ == "__main__":
        extract_statistics()

.. note:: The code is executed twice, filtering on the HC-zone first then the water-zone 
          in a second run. Alternatively the fluid parameter could have been used as a 
          selector, for extracting statistics in one run.


**Example when executed from files:**

.. code-block:: python

    from fmu.tools import QCProperties

    PATH = "../input/qc/"
    GRID = "grid.roff"
    PROPERTIES = {"PORO": {"name": "poro.roff"}}
    SELECTORS = {
        "ZONE": {
            "name": "zone.roff",
        },
        "FACIES": {
            "name": "facies.roff",
            "exclude": ["Carbonate"],
        },        
    }
    REPORT = "../output/qc/somefile.csv"

    usedata = {
        "properties": PROPERTIES,
        "selectors": SELECTORS,
        "path": PATH,
        "grid": GRID,
        "name": "MYDATA",
    }

    def check():

        qcp = QCProperties()
        qcp.get_grid_statistics(data=usedata)

    if  __name__ == "__main__":
        check()



get_well_statistics examples
""""""""""""""""""""""""""""""""

**Example in RMS:**

Example extracting statistics for permeability for each zone and facies.
All wells starting with 34_10-A or 34_10-B will be included in statistics.
Result is written to csv.

.. code-block:: python

    from fmu.tools import QCProperties

    WELLS = {
      "names": ["34_10-A.*$", "34_10-B.*$"],
      "logrun": "log",
      "trajectory": "Drilled trajectory",
    }
    PROPERTIES = {"PERM": {"name": "Klogh"}}
    SELECTORS = ["Zonelog", "Facies_log"]
    REPORT = "../output/qc/somefile.csv"

    usedata = {
        "properties": PROPERTIES,
        "selectors": SELECTORS,
        "wells": WELLS,
        "csvfile": REPORT,
    }

    def check():

        qcp = QCProperties()
        qcp.get_well_statistics(data=usedata, project=project)

    if  __name__ == "__main__":
        check()


**Example when executed from files:**

Example extracting statistics for permeability for each zone and facies.
First extracting statistics for wells starting with "34_10-A", then wells 
starting with "34_10-B" in a subsequent run.
Result is written to csv.

.. code-block:: python

    from fmu.tools import QCProperties

    WELLS = ["34_10-A.*$"]
    PATH = "../input/qc/"
    PROPERTIES = ["Phit", "Klogh"]
    SELECTORS = ["Zonelog", "Facies_log"]
    REPORT = "../output/qc/somefile.csv"

    usedata = {
        "properties": PROPERTIES,
        "selectors": SELECTORS,
        "wells": WELLS,
        "path": PATH,
        "name": "A-wells",
    }

    def check():

        qcp = QCProperties()
        qcp.get_well_statistics(data=usedata)

        usedata2 = usedata.copy()
        usedata2["wells"] = ["34_10-B.*$"]
        usedata2["name"] = "B-wells"
        qcp.get_grid_statistics(data=usedata2, project=project)

        qcp.to_csv(REPORT)

    if  __name__ == "__main__":
        check()

get_bwell_statistics examples
""""""""""""""""""""""""""""""""

**Example in RMS:**

To come....

**Example when executed from files:**

To come....


Comparison of data from different sources
-------------------------------------------

Advice when comparing data from different sources
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

When extracting statistics from different sources there are several tips for enabling easy comparison 
in the post-analysis of the data in e.g. WebViz:

* Input "properties" and "selectors" as dictionaries and keep property and selector keys identical 
  between the sources. The keys will be the names seen in the dataframe.

* Try to use the same selectors for all sources 

* Keep the option "selector_combos" at True to get as much overlapping data as possible. 
  For example, if well statistics only have ZONE as selector and the grid properties are calculated with 
  selectors ZONE and REGION and "selector_combos" where True, the ZONE level statistics can be compared.

* Use the "codes" field on the selectors to align and match the codenames for each selector. For example 
  if the zone codes are coarser in the grid than in the zonelogs from the wells, this field can be used 
  to merge codes in the zonelog together under one name.

Example 
^^^^^^^^^

Example below collects statistical data from four different sources and writes result to a csv-file.
Several steps have been to ensure consistency between the sources, making the resulting csv-file easy to compare:

* "Poro" and "Perm" will be the property names 

* "ZONE" will be the column name for the selector 

* The zone codes "UpperReek", "MidReek", "LowerReek" is present in the two grids, to get the same codes in the wells
  the codes are updated and redundant codes are excluded.

.. code-block:: python

    from fmu.tools import QCProperties

    REPORT = "somefile.csv"

    GEOGRIDDATA = {
        "properties": ["Poro", "Perm"],
        "selectors": {"ZONE": {"name":"Zone"}},
        "grid": "Geogrid",
    }
    SIMGRIDDATA = {
        "properties": {"Poro":{"name":"PORO"}, "Perm":{"name":"PERMX"}},
        "selectors": {"ZONE": {"name":"Zone"}},
        "grid": "Simgrid",
    }
    BWDATA = {
        "properties": ["Poro", "Perm"],
        "selectors": {"ZONE": {"name":"Zonelog", "codes":{1:"UpperReek", 2:"MidReek", 3:"LowerReek"}, "exclude":["Above_TopUpperReek", "Below_BaseLowerReek"]}},
        "wells": {"bwname": "BW", "grid": "Geogrid"},
    }
    WDATA = {
        "properties": ["Poro"],
        "selectors": {"ZONE": {"name":"Zonelog", "codes":{1:"UpperReek", 2:"MidReek", 3:"LowerReek"}, "exclude":["Above_TopUpperReek", "Below_BaseLowerReek"]}},
        "wells": {"logrun": "log", "trajectory": "Drilled trajectory"},
    }

    def extract_statistics():

        qcp = QCProperties()

        qcp.get_grid_statistics(data=GEOGRIDDATA, project=project)
        qcp.get_grid_statistics(data=SIMGRIDDATA, project=project)
        qcp.get_bwell_statistics(data=BWDATA, project=project)
        qcp.get_well_statistics(data=WDATA, project=project)

        qcp.to_csv(REPORT)

    if  __name__ == "__main__":
        extract_statistics()



Using yaml input for auto execution
-----------------------------------
A yaml-configuration file can be used with the method ``from_yaml`` to enable an automatic run of the methods.
This is especially useful if the user wants to run multiple extractions of statistics with minimal 
code input. 

The code evaluates what method to execute based on the value of the first level in the yaml file.
The second level is a list of input 'data' objects, and statistics will be calculated for each list 
element.

**Three fields are available for the first level:**

* ``grid``: the get_grid_statistics method are executed on elements in this level

* ``wells``: the get_well_statistics method are executed on elements in this level

* ``blocked_wells``: the get_bwell_statistics method are executed on elements in this level


Example in RMS with setting from a YAML file:
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Example using yaml input in RMS for extracting statistics for porosity and permeability from
four data sources (geogrid, simgrid, wells and blocked wells). The resulting combined 
dataframe are written to csv.

.. code-block:: python

    from fmu.tools import QCProperties

    YAML_PATH = "../input/qc/somefile.yml"
    REPORT = "../output/qc/somefile.csv"

    def check():
        qcp = QCProperties()        
        qcp.from_yaml(YAML_PATH, project=project)
        qcp.to_csv(REPORT)

    if  __name__ == "__main__":
        check()


The YAML file may in case look like:

.. code-block:: yaml

    grid:
      - grid: GeoGrid
        properties:
          PORO:
            name: PHIT
          PERM:
            name: KLOGH
        selectors:
          ZONE:
            name: Zone
          FACIES:
            name: Facies
    
      - grid: SimGrid
        properties:
          PORO:
            name: PORO
          PERM:
            name: PERMX
        selectors:
          ZONE:
            name: Zone
          FACIES:
            name: Facies
    
    wells:
      - wells:  
          logrun: log
          names: [34_10-A.*$]
          trajectory: Drilled trajectory
        properties:
          PORO:
            name: Phit
          PERM:
            name: Klogh
        selectors:
          ZONE:
            name: Zonelog
          FACIES:
            name: Facies_log
    
    blockedwells:
      - wells:  
          grid: GeoGrid
          names: [34_10-A.*$]
          bwname: BW
        properties:
          PORO:
            name: Phit
          PERM:
            name: Klogh
        selectors:
          ZONE:
            name: Zonelog
          FACIES:
            name: Facies_log






Additional Notes
---------------------

Advice on performance
^^^^^^^^^^^^^^^^^^^^^^^^^

There are several settings that has an influence perfomance:

* Keep the option ``reuse = True`` to avoid reloading data to XTGeo if it is previously used, 
  e.g. extracting statistics from the same grid but with different filters. 

* Filters can be used to remove unnecessary data, this will limit the input data before statistics
  is calculated and will speed up execution.

* If many selectors, the option ``selector_combos = False`` will have a large impact on performance 

* Avoid using 

* weights

Comparison with statistics in RMS
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

* To avoid bias in the calculation, the code removes duplicates from both well and blocked well 
  data before calculating statistics. Duplicates are data points that have the same coordinates  
  and property values. For blocked wells this refers to cells that are penetrated by multiple wells, 
  for raw wells this can happen if branches of multilateral wells have overlapping logs. 
  
  This is the same as RMS does when calculating statistics for blocked wells, and statistical values 
  extracted with this code will be identical to RMS. However RMS does not remove duplicates when 
  calculating statistics for raw wells, and minor differences in statistical values are possible. 
