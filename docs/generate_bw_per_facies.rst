rms.generate_bw_per_facies
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

   from fmu.tools.rms.generate_bw_per_facies import create_bw_per_facies

   DEBUG_PRINT = True
   GRID_NAME = "Geogrid_Valysar"
   BW_NAME = "BW_copy"
   ORIGINAL_BW_LOG_NAMES = ["PHIT", "KLOGH"]
   FACIES_LOG_NAME = "Facies"
   FACIES_CODE_NAMES = {
        0: "Floodplain",
        1: "Channel",
        2: "Crevasse",
        5: "Coal",
   }

   def main(project):
        create_bw_per_facies(
          project,
          GRID_NAME,
          BW_NAME,
          ORIGINAL_BW_LOG_NAMES,
          FACIES_LOG_NAME,
          FACIES_CODE_NAMES,
          DEBUG_PRINT)

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

