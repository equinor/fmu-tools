create_rft_ertobs
=================

This scripts creates ``.txt``, ``.obs`` and a "welldatefile" to be used for
``GEN_DATA`` usage in assisted history match for matching of RFT pressure values
in wells.

The script must be run from within RMS to be able to interpolate from MD to
(x,y,z) (or the other way) along wellpaths.

Usage
^^^^^

Typical input is a CSV file:

.. csv-table:: Example CSV input
   :file: ../tests/rms/rft_ertobs_data/input_table_drogon.csv
   :header-rows: 1

For each row, corresponding to a specific RFT observation value, either (x,y,z)
(in the columns EAST, NORTH and TVD), or the measured depth MD must be specified,
(and the missing value(s) will be interpolated from the well trajectory).

The RKB of measured depth (MD) must be the same as for the well in the RMS
project.

If ZONE is specified, the provided zone value is compared with the zone name
valid for the relevant cell in the RMS model. If they do not match, a warning is
emitted.

If a well has observations as multiple dates, the REPORT_STEP column in the
welldatefile will be enumerated from 1 and upwards. The obs-files produced
will always include the REPORT_STEP in the filename.

Observation files will always cover the measurement points for all dates for a
well, but padded with -1 at dates (report steps) where there is no data.

Additional options are specified through a RMS dictionary, and
``create_rft_ertobs`` can be called from a RMS Python job with a script like

.. code-block:: python

  from fmu.tools.rms import create_rft_ertobs

  # Paths are relative to rms/model
  CONFIG = {
      "input_file": "../input/well_modelling/rft_observations.csv",
      "alias_file": "../../config/rms_eclipse_alias.csv",
      "exportdir": "../../ert/input/observations/rft",  # Must exist
      "project": project,  # The Python object representing your RMS project
      "gridname": "Simgrid",
      "zonename": "Zone",
      "verbose": True,
      "clipboard_folder": "RFT_ERT_observations", # Optional folder for storage in RMS
  }

  create_rft_ertobs.main(CONFIG)


The example provides a typical minimum. Available options to set are

input_file
  CSV file with input data, one row for each RFT observations. The DATE column
  must be in ISO-8601 format (YYYY-MM-DD). Required columns are "DATE", "MD",
  "WELL_NAME" and "PRESSURE".

alias_file
  A CSV file with RMS well names in one column and Eclipse names in a different
  column. The column names for RMS and Eclipse has defaults, that can be changed
  through options. First line in this file is used as a header with column
  names.

rft_prefix
  If specified, this is added as a prefix to all well names in the input file. 
  If aliases are in use, the RMS names of wells in the alias file must include
  the prefix.

exportdir
  A directory for where to dump the resulting txt, obs and well_date file. The
  directory must exist upfront.

welldatefile
  A filename that will be written to (do not include the path, it is written
  to the directory specified in ``exportdir``) that will contain data to
  be provided to GENDATA_RFT.

interpolation
  Interpolation setting, choose between ``linear`` and ``cubic``. Default is
  ``cubic``. This affects how points along the wellpath are interpolated.

absolute_error
  Floating point value for absolute error to use on those observations where
  "ERROR" is not specified in the CSV file.

relative_error
  Relative error to be used for those observations where "ERROR" is not
  specified in the CSV file. The error is calculated as this relative
  error times the VALUE column in the CSV.

input_dframe
  Alternative to using ``input_file``, you may provide a Pandas dataframe with
  the same columns, directly without going via CSV on disk.

rms_name
  The column name in the CSV alias_file with RMS names. Defaults to
  ``RMS_WELL_NAME``.

ecl_name
  The column name in the CSV alias_file with Eclipse names. Defaults to
  ``ECLIPSE_WELL_NAME``.

zonename
  Name of zone parameter in RMS grid (necessary for verifying if RFT
  observations are in the correct zone in the grid)

gridname
  Name of the RMS gridmodel to be requested for mapping (x,y,z) to gridcells
  and into zone queries.

trajectory_name
  The trajectory name for the wellpaths in the RMS project. Defaults
  to "Drilled trajectory".

clipboard_folder
  Optional name of clipboard folder for storing RFT points inside the RMS project.
  The folder will be created if not present.

  
See also
^^^^^^^^

* `GENDATA_RFT forward model in ERT <https://fmu-docs.equinor.com/docs/ert/reference/configuration/forward_model.html#GENDATA_RFT>`__
* `GENDATA keyword in ERT <https://ert.readthedocs.io/en/latest/reference/configuration/keywords.html#gen-data>`__
* `merge_rft_ertobs in subscript <https://equinor.github.io/subscript/scripts/merge_rft_ertobs.html>`__
