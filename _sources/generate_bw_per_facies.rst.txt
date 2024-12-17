rms.create_bw_per_facies
============================

The RMS python job to generate new blocked wells with petrophysical
values for one facies per blocked well log is used as part of a workflow
to create petrophysical 3D grid realizations conditioned to only one facies.
This is used in FMU workflows where both facies and petrophysical variables
are used as field parameters in assisted history matching (AHM) with ERT.

Input

* Grid name
* Existing blocked well set (containing the original blocked well logs)
* List of original petrophysical blocked well log names to be used to generate new logs
* Facies log name
* Python dictionary with code and facies names per code for relevant facies

Output

For each of the specified original petrophysical logs, one new log per facies
for the specified facies is made. The values are copies of the original blocked
well logs except that all values belonging to other facies than the one for the
created log is set to undefined. The new logs will have name of
the form "faciesname_petroname".

Example of use as RMS python job
---------------------------------

.. code-block:: python

     from fmu.tools.rms import create_bw_per_facies
     from fmu.config import utilities as ut
     DEBUG_PRINT = False

     CFG = ut.yaml_load("../../fmuconfig/output/global_variables.yml")["global"]
     FACIES_ZONE = CFG["FACIES_ZONE"]

     GRID_NAMES = {
          "Valysar": "Geogrid_Valysar",
          "Therys":  "Geogrid_Therys",
          "Volon":   "Geogrid_Volon",
     }

     # Blocked well set
     BW_NAME = "BW"

     # Original logs to make copy of per facies
     ORIGINAL_BW_LOG_NAMES = ["PHIT", "KLOGH"]

     # Facies log in original blocked well set
     FACIES_LOG_NAME = "Facies"

     def main(project):
          for zone_name, facies_code_names_for_zone  in FACIES_ZONE.items():
               # For each of the single zone grids, calculate updated BW set
               create_bw_per_facies(
                    project,
                    GRID_NAMES[zone_name],
                    BW_NAME,
                    ORIGINAL_BW_LOG_NAMES,
                    FACIES_LOG_NAME,
                    FACIES_ZONE[zone_name],
                    debug_print=DEBUG_PRINT)

     if __name__ == "__main__":
          main(project)

The example above will create the following new blocked well logs for
each well based on the original logs "PHIT" and "KLOGH":

* Floodplain_PHIT
* Floodplain_KLOGH
* Channel_PHIT
* Channel_KLOGH
* Crevasse_PHIT
* Crevasse_KLOGH
* Coal_PHIT
* Coal_KLOGH

