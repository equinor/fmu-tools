rms.generate_petro_jobs
===========================

When running FMU project where field parameters for both facies and
petrophysical properties is updated in ERT simultaneously,
some adjustments are needed in the RMS project to support this type
of workflow. It is necessary to have one petrosim job per facies.
To simplify the work with the RMS project, the function
*generate_petro_jobs* from *fmu.tools*
can be used in a python job in RMS.
It requires a small configuration file and will then
read an existing petrosim job from the RMS project and generate one new
petrosim job per facies. The new jobs are ready to be used
(put into the RMS workflow) and they will use the same model parameters
for the petrophysical properties as the original (existing) job,
but only for one facies.

The function *generate_petro_jobs* will modify
your RMS project when run from your RMS project
by adding new petrosim jobs, one per facies as specified in the
configuration file for the script. The configuration file is a yaml format
file defining which grid model and which facies 3D parameter to use and the
name of the original petrosim job. For each zone and each facies per zone
a list is specified of which petrophysical parameters to use in the new
petrosim jobs that are generated.


Usage
^^^^^
* Import the function  *generate_petro_jobs* into a python job in RMS.
  Specify a configuration file and specify the name of this configuration
  file in the python job.

* Run the python job in RMS to generate the new petrosim jobs.

* Finally, update the workflowin RMS by using the generated jobs.

Example of python script in RMS

.. code-block:: python

    from fmu.tools.rms import generate_petro_jobs

    CONFIG_FILE = "generate_petro_jobs.yml"
    if  __name__  ==  "__main__":
        generate_petro_jobs(CONFIG_FILE)

Example of configuration file for multi zone grid in RMS

.. code-block:: yaml

    # Name of grid model for the petrophysics jobs
    grid_name: MultiZoneBox

    # Name of original petro job using facies realization as input
    original_job_name: original_multi_zone

    # Use empty string as zone name for single zone grids and zone name
    # for multizone grids.
    # For each zone, specify facies and for each facies specify
    # petro variables to be used as field parameters in ERT update

    # Example for a multizone grid with three zones:
    used_petro_var:
        Zone1:
            F1:  [P1, P2]
            F2:  [P1, P2]
            F3:  [P1, P2]
        Zone2:
            F1:  [P1, P2]
            F2:  [P1, P2]
            F3:  [P1, P2]

Example of configuration file for single zone grid in RMS

.. code-block:: yaml

    # Name of grid model for the petrophysics jobs
    grid_name: SingleZoneBox

    # Name of original petro job using facies realization as input
    original_job_name: original_single_zone

    # Use empty string as zone name for single zone grids and zone name
    # for multizone grids.
    # For each zone, specify facies and for each facies specify
    # petro variables to be used as field parameters in ERT update
    used_petro_var:
        default:
            F1:  [P1, P2]
            F2:  [P1, P2]
            F3:  [P1, P2]
