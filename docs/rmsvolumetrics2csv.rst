rmsvolumetrics2csv
==================

This script parses volumetrics text output from RMS and writes CSV files.
Column names will be according to the FMU standard,
https://wiki.equinor.com/wiki/index.php/FMU_standards

It is installed and available both in Komodo and in the RMS Python environment,
and the associated API can also be used in Python scripts (this gives more
options than the command line interface).

Usage
^^^^^

.. argparse::
  :module: fmu.tools.rms.volumetrics
  :func: get_parser
  :prog: rmsvolumetrics2csv


Usage from RMS
^^^^^^^^^^^^^^

Use a "System command" RMS job to run the command with appropriate arguments. Ensure
that any output directory exists upfront. Since fmu-tools is inside both in Komodo and in
the RMS Python environment, using ``run_external`` is not necessary, but will also work.
