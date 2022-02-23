Ensembles
=========

The ``ensembles`` provides functionality (methods, scripts) to compute various results from
a full ensemble.

The ``ensemble_well_props`` script
----------------------------------

The usecase for this script it to 'drill a well', typically a planned well, in the full ensemble
and get the following products:

* A RMS well file (ascii) that has average log(s) sampled from all realizations
* Get statistics on 'good' intervals, e.g. get the cumulative length vs total length when facies
  number is 1 and porosity is above 0.24.

The script will generate an ``example.yml`` file that can be used as a template for you case::

    ensemble_well_props --example

Then rename this file to e.g. ``wellplan_code_x.yml`` and modify settings, and run::

    ensemble_well_props --config wellplan_code_x.yml
