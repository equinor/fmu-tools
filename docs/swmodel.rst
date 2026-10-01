swmodel
=======

The ``fmu.tools.swmodel`` package creates initial saturation properties from
Simplified-J functions. It supports both file-based workflows (ROFF in/ROFF out)
and RMS workflows (RMS grid model + property names in, properties written back to RMS).

It uses :class:`fmu.tools.properties.SwFunction` for the saturation calculations.

Key features
------------

* YAML-driven configuration
* Oil-only, gas-only, or combined oil+gas workflows
* Group-specific J-function parameters
* Optional ``swl`` output from a configured height above free fluid level
* Optional ``so``/``sg`` output
* Same config schema for file mode and RMS mode

File-based CLI usage
--------------------

Create a YAML configuration file:

.. code-block:: yaml

   grid: grids/geogrid.roff

   gridparameter:
     swfunction_region: grids/geogrid--swfunction_region.roff
     poro: grids/geogrid--poro.roff
     perm: grids/geogrid--perm.roff
     fwl: grids/geogrid--fwl.roff
     goc: grids/geogrid--goc.roff
     fwlwg: grids/geogrid--fwlwg.roff

   sw_functions:
     Channel:
       oil:
         a: 4.5
         b: -2.2
         swirr: 0.0
       gas:
         a: 3.8
         b: -1.9
         swirr: 0.0

Run it from the command line:

.. code-block:: bash

   swmodel swmodel.yml
   swmodel swmodel.yml --output_all
   swmodel swmodel.yml --key_path global.swmodel

CLI output files are written to ``./share/results/grids`` by default, using:

* ``<gridname>--sw.roff``
* ``<gridname>--sw_h.roff``
* ``<gridname>--swl.roff`` when ``swl_height`` is configured
* ``<gridname>--so.roff`` and ``<gridname>--sg.roff`` with ``--output_all``

The default output folder is resolved relative to the current working
directory, not relative to the configuration file location. Use
``--output_folder`` to override the default location.

RMS usage
---------

In RMS mode the same schema is used, but ``grid`` and ``gridparameter`` values
are RMS grid-model and property names instead of file paths:

.. code-block:: yaml

   swmodel:
     geogrid:
       grid: Geogrid

       gridparameter:
         swfunction_region: SWFUNC_REGION
         poro: PORO
         perm: PERM
         fwl: FWL
         goc: GOC
         fwlwg: FWLWG

       sw_functions:
         Channel:
           oil:
             a: 4.5
             b: -2.2
             swirr: 0.0
           gas:
             a: 3.8
             b: -1.9
             swirr: 0.0

In this example, ``swmodel.geogrid`` is a user-defined nested key path. The
section names ``swmodel`` and ``geogrid`` are only examples; you may use any
key names as long as ``key_path`` matches them.

Run from an RMS Python job:

.. code-block:: python

   from fmu.tools.swmodel import run_swmodel

   run_swmodel(
       project,
       "../input/config/swmodel.yml",
       key_path="swmodel.geogrid",
       output_all=True,
       debug=True,
   )

If the YAML configuration is stored at the root instead of under a nested key,
``key_path`` can be omitted. Note that ``key_path`` must be a quoted string,
for example ``"swmodel.geogrid"``, not Python attribute syntax.

``run_swmodel()`` configures INFO logging by default in RMS/Python mode. Pass
``debug=True`` for verbose debug output. Third-party ``xtgeo`` INFO chatter is
suppressed by default and only enabled in debug mode. Optionally, an
``output`` section can be used to override the default RMS property names
(``sw``, ``sw_hcenter``, ``swl``, ``so``, ``sg``).

Configuration reference
-----------------------

.. list-table::
   :header-rows: 1
   :widths: 24 12 26 19 19

   * - Key
     - Required
     - Meaning
     - File mode
     - RMS mode
   * - ``grid``
     - Yes
     - Grid to process.
     - ROFF grid file path.
     - RMS grid model name.
   * - ``gridparameter.swfunction_region``
     - Yes
     - Discrete region selector. Code names must match the keys under
       ``sw_functions``.
     - Grid property file path.
     - RMS property name.
   * - ``gridparameter.poro`` / ``gridparameter.perm``
     - Yes
     - Porosity and permeability inputs.
     - Grid property file paths.
     - RMS property names.
   * - ``gridparameter.fwl``
     - Oil
     - Free-water level used by oil J-functions.
     - Grid property file path.
     - RMS property name.
   * - ``gridparameter.goc`` / ``gridparameter.fwlwg``
     - Gas
     - Gas-oil contact and water-gas free-water level used by gas
       J-functions. These must be provided together.
     - Grid property file paths.
     - RMS property names.
   * - ``sw_functions.<region>.oil`` / ``.gas``
     - Yes
     - One or both phases per region, with parameters such as ``a``, ``b``,
       and ``swirr``. All regions must use the same phase set.
     - Same schema.
     - Same schema.
   * - ``algorithm``
     - No
     - Numerical settings such as ``method``, ``calc``, ``epsilon``, and
       ``invert_jfunc``.
     - Same schema.
     - Same schema.
   * - ``swl_height``
     - No
     - Creates the optional ``swl`` output at the requested height above free
       fluid level.
     - Same behavior.
     - Same behavior.
   * - ``swl_min`` / ``swl_max``
     - No
     - Optional clipping limits for ``swl``. Only meaningful when
       ``swl_height`` is configured.
     - Same behavior.
     - Same behavior.
   * - ``output``
     - No
     - Override result names for ``sw``, ``sw_h``, ``swl``, ``so``, and
       ``sg``.
     - Ignored.
     - RMS property names.

Configuration notes
-------------------

* ``fwl`` is required when any oil J-function is present.
* ``goc`` and ``fwlwg`` are required when any gas J-function is present. In
  gas/water-only cases, they are expected to represent the same contact.
* ``swfunction_region`` code names must match the keys under ``sw_functions``.
* All ``sw_functions`` groups must define the same phase set: all oil, all gas,
  or all oil+gas.
* ``algorithm.calc: integrated`` does not support J-functions with ``b = -1``.
* ``swl_min`` and ``swl_max`` must be within ``[0, 1]``.
* ``swl_min <= swl_max`` when both are provided.
* J-function  a  and  b  values can be given in RMS convention or petrophysical
  convention. If they are given in RMS convention, set  invert_jfunc: true ; otherwise
  leave it at the default  false .

Command line arguments
----------------------

.. argparse::
   :module: fmu.tools.swmodel.swmodel
   :func: get_parser
   :prog: swmodel
