Ensembles
=========

The ``ensembles`` provides functionality (methods, scripts) to compute various results from
a full ensemble.

The ensemble_well_props script
----------------------------------

Introduction to ``ensemble_well_props``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The use case for this script it to 'drill a well', typically a planned well, in the full ensemble
and get the following products:

* A RMS well file (ascii) that has average log(s) sampled from all realizations
* Get statistics on 'good' intervals, e.g. get the cumulative length vs total length when facies
  number is 1 and porosity is above 0.24.

The script will generate an ``example.yml`` file that can be used as a template for you case::

    ensemble_well_props --example

Then rename this file to e.g. ``wellplan_code_x.yml`` and modify settings, and run::

    ensemble_well_props --config wellplan_code_x.yml


Example input YAML file
~~~~~~~~~~~~~~~~~~~~~~~

In addition to the option of generating an example in the script itself, a simple example is
provided here for reference.

.. code-block:: yaml

    ensemble:
      iteration: iter-3
      realizations:
        range: 0-30
      root: /scratch/some/case/

    gridproperties:
      grid:
        filestub: share/results/grids/geogrid.roff
      properties:
      - discrete: true
        filestub: share/results/grids/geogrid--facies.roff
        name: Facies
      - filestub: share/results/grids/geogrid--phit.roff
        name: PHIT

    well:
      delta: 3
      file: somefolder/OP5_Y1.rmswell
      lognames: [MD]
      mdlog: MD
      mdranges: [[1653, 1670], [1680, 1698]]

    report:
      average_logs:
        fileroot: avgfile
      cumulative_lengths:
        # look at criteria where facies is 1 and porosity is above 0.24
        criteria:
          Facies:
            codes: [1]
          PHIT:
            interval: [0.24, 0.40]
        fileroot: cumfile
      keep_intermediate_logs: true

Result files
~~~~~~~~~~~~

The script will generate on or more result on CSV and/or RMS well format. The RMS well file
can be imported in RMS for visual inspection, while the CSV files can be imported to spreadsheet
or similar for further usage.
