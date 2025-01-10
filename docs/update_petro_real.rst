rms.update_petro_parameters
============================

When running FMU project where field parameters for both facies and
petrophysical properties are updated in ERT simultaneously,
some adjustments are needed in the RMS project to support this type
of workflow. It is necessary to have one petrosim job per facies.

The module *update_petro_parameters* will combine values from realization
of a petrophysical property for individual facies into one common
petrophysical realization by using the facies realization as filter.


Example describing the workflow
--------------------------------

The zone Valysar has four different facies::

    Floodplain
    Channel
    Crevasse
    Coal

A petrophysical realization is made for PHIT and KLOGH for each of the three
first facies with property names::

    Floodplain_PHIT
    Floodplain_KLOGH
    Channel_PHIT
    Channel_KLOGH
    Crevasse_PHIT
    Crevasse_KLOGH

Neither PHIT nor KLOGH are updated as field parameters for facies
Coal since they have constant (not spatially varying) values and
may even have no uncertainty specified.
The variables VSH and VPHYL are chosen not to be used as field parameters
in ERT in assisted history matching in this example
and therefore not included here,
but still used in the RMS workflow with the prior values.

The original realizations created for PHIT and KLOGH are conditioned
to facies. In a workflow where we want to use both facies by applying
the Adaptive PluriGaussian Simulation method (APS) and PHIT and KLOG
for some selected facies as field parameters to be updated by ERT,
we will need the separate PHIT and KLOGH realizations for the selected
facies.

The steps will be:

    * Use original petrophysical job to create initial version of a realization of
      PHIT, KLOGH, VSH and VPHYL.
    * Use separate petrophysical jobs to create separate version of realizations of
      Floodplain_PHIT, Floodplain_KLOGH and so on.
    * Use the script *update_petro_parameters* to copy the values for PHIT and KLOGH from
      the individual realizations per facies into the initial version of PHIT and KLOG
      by overwriting the values in the original version. In this process,
      the facies realization is used as a filter to select which grid cell values
      to get from the individual PHIT and KLOGH parameters that belongs to the
      various facies.

When running ERT iteration 0 which creates the initial ensemble, this looks a bit unnecessary,
since the initial PHIT and KLOGH already has taken facies into account. But, when running
ERT iteration larger than 0 (after ERT has updated the fields Floodplain_PHIT,
Floodplain_KLOGH and so on), then updated versions of the field parameters are imported
and updated version of facies realization is used to update the PHIT and KLOGH parameters
from the imported field parameters (Floodplain_PHIT, Floodplain_KLOGH ...).

Also for iteration 0, to ensure consistency the same procedure
(copy from the field parameters Floodplain_PHIT, Floodplain_KLOG,..) is
applied since this ensure consistent handling of the realizations.

Example of RMS python job running this module to combine the field parameters
-------------------------------------------------------------------------------

The python job below will call the *update_petro_parameters* function that does the
combination of the field parameters into one petrophysical realization.
This job depends on a small config file ( the same config file that is used by the
function *generate_petro_jobs*  from fmu.tools.rms module). Here the python job gets
the grid name and which of the petrophysical properties for which facies
to be updated as field parameters in ERT. The script also depends on the facies table
(which facies code and name belongs together).
This can be fetched from the *global_variables.yml* file as shown in the example below.

An alternative is to add a key *USED_PETRO_FIELDS*  in global_master_config.yml
and get the petro parameters per facies per zone from this keyword instead.

.. code-block:: python

    from fmu.tools.rms import update_petro_parameters
    from fmu.config import utilities as ut

    DEBUG_PRINT = False

    # Choose either to use config file or input from global variable file
    USE_CONFIG_FILES = True

    CFG = ut.yaml_load("../../fmuconfig/output/global_variables.yml")["global"]
    FACIES_ZONE = CFG["FACIES_ZONE"]

    # Used if alternative 1 with config file is used
    CONFIG_FILES = {
        "Valysar": "../input/config/field_update/generate_petro_jobs_valysar.yml",
        "Therys":  "../input/config/field_update/generate_petro_jobs_therys.yml",
        "Volon":   "../input/config/field_update/generate_petro_jobs_volon.yml",
    }

    # Used if alternative 2 without config file is used
    # In this case the global master config must be updated
    # to define the dictionary with used petro fields per zone per facies
    USED_PETRO_FIELDS = CFG["USED_PETRO_FIELDS"]
    GRID_NAMES = {
        "Valysar": "Geogrid_Valysar",
        "Therys":  "Geogrid_Therys",
        "Volon":   "Geogrid_Volon",
    }
    FACIES_REAL_NAMES = {
        "Valysar": "FACIES",
        "Therys":  "FACIES",
        "Volon":   "FACIES",
    }

    # For multi zone grids also zone_param_name and zone_code_names must be specified
    # Example:
    #   ZONE_PARAM_NAME = "Zone"
    #   ZONE_CODE_NAMES = {
    #      1: "Valysar,
    #      2: "Therys",
    #      3: "Volon",
    #   }


    if __name__ == "__main__":
        # Drogon uses 3 different grids and single zone grids
        if USE_CONFIG_FILES:
            # Alternative 1 using config file common with generate_petro_jobs
            for zone_name in ["Valysar", "Therys", "Volon"]:
                facies_code_names =  FACIES_ZONE[zone_name]
                config_file = CONFIG_FILES[zone_name]
                update_petro_parameters(
                    project,
                    facies_code_names,
                    zone_name_for_single_zone_grid=zone_name,
                    config_file=config_file,
                    debug_print=DEBUG_PRINT)
        else:
            # Alternative 2 specify input using global_variables file
            for zone_name in ["Valysar", "Therys", "Volon"]:
                facies_code_names =  FACIES_ZONE[zone_name]
                grid_name = GRID_NAMES[zone_name]
                facies_real_name = FACIES_REAL_NAMES[zone_name]
                used_petro_per_facies=USED_PETRO_FIELDS
                update_petro_parameters(
                    project,
                    facies_code_names,
                    grid_name=grid_name,
                    facies_real_name=facies_real_name,
                    used_petro_dict=used_petro_per_facies,
                    zone_name_for_single_zone_grid=zone_name,
                    debug_print=DEBUG_PRINT)


The *global_master_config.yml* file can include a keyword for *USED_PETRO_FIELDS*

.. code-block:: yaml

    USED_PETRO_FIELDS:
        Valysar:
            Floodplain: [ PHIT, KLOGH ]
            Channel:    [ PHIT, KLOGH ]
            Crevasse:   [ PHIT, KLOGH ]
        Therys:
            Offshore:       [ PHIT, KLOGH ]
            Lowershoreface: [ PHIT, KLOGH ]
            Uppershoreface: [ PHIT, KLOGH ]
        Volon:
            Floodplain: [ PHIT, KLOGH ]
            Channel:    [ PHIT, KLOGH ]

and optionally also for multizone grid:

.. code-block:: yaml

    ZONE_CODE_NAMES:
        1: Valysar
        2: Therys
        3: Volon
