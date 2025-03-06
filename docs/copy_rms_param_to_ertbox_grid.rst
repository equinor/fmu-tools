rms.copy_rms_param
====================

The RMS python job to copy petrophysical field parameters between
geomodel grid and ERTBOX grid is used as a part of a workflow
to update petrophysical field parameters (RMS 3D parameters) in ERT
as a part of an assisted history matching.

About the ERTBOX grid and its purpose
--------------------------------------

The ERTBOX grid is a grid with same lateral extent, orientation, location and grid resolution as
the geogrid assuming the geogrid has close to regular grid layout laterally. The ERTBOX grid is
a regular grid without any structure (just a box) and the geometry is not of importance. It is
used as input to the GRID keyword in ERT config files when using FIELD keyword in ERT. The purpose
of the grid is to ensure fixed size of the field parameters and hence also the state vectors
(realizations in ERT). It enable the workflow to handle field parameters from multizone
geogrids and structural uncertainty ( varying number of layers per zone due to
top conform or base conform grid layout of zones in the geogrid or stair stepped faults) in ERT.
The number of layers must be at least as large as the geomodel zone with
most layers  (of the zones having field parameters to be updated in ERT). Since the number of
layers may vary from realization to realization in the geomodel grid, the ERTBOX grid must
have a number of layers that is as large as the largest zone in the geomodel for all realizations
of the geomodel grid, but not larger than necessary to avoid unnecessary large state vectors,
cpu time, memory usage and disk space usage by ERT. The ERTBOX grid is used with its fixed size
for all field parameters for all zones and all realizations.

Purpose of the function
------------------------

The copy from geogrid to ertbox grid will usually leave grid cells in ertbox undefined
for grid cell values in ertbox that does not corresponds to any active grid cell in the geogrid.
To avoid missing code or any other unphysical values in the ertbox, the values are extrapolated.
The purpose is to deliver field parameters with size equal to the ertbox size (nx, ny, nz_ertbox) where all field
parameters for all grid cells have sensible physical values also for those that may not be used.
ERT will per today require that all realizations (all state vectors) are of same size and be consistent.
For a field parameter F(i,j,k), all realizations of F must have exactly the same set of active and inactive grid cells,
and this may not automatically be the case when the geogrid zones have varying number of layers or the
geogrid has stair step faults. To handle this, a pragmatic solution is use a fixed sized help grid, the ERTBOX grid.
The workflow is to first copy the values for a field parameter for a zone into the ERTBOX grid
and fill the ERTBOX grid cell values (for those grid cells that is still not filled with values)
with extrapolated values that have at least sensible
value and not just 0 or Nan or similar 'missing' code. The field parameters are then exported to file to be read
by ERT. This ensure that all field parameters have same size for all realizations and that ERT in
the analysis step does not make linear combinations of field parameters where some realization have physical values
and others have unphysical values or Nan.

Input is a python dictionary with all relevant specifications:

* Name of geomodel grid and ertbox grid
* Name of petrophysical variable in the geomodel grid to used as field parameters in ERT.
* Name of the petrophysical variable in the ERTBOX grid.
* Typically the field name in the ERTBOX grid will be zone_name combined with variable name.
* Grid conformity per zone.
* Optional if a active/inactive parameter is to be created in ERTBOX grid.
* Extrapolation method when copying from geomodel grid to ERTBOX grid.

Consistency check with the grid model
--------------------------------------

The keyword *Conformity* should specify the correct grid conformity for each of the zones in the grid model.
If the grid model is built using RMS grid building job, it is possible to check that the specified conformities
are correct. There are however a few requirements for the consistency check:

* The grid model must be built by an RMS grid building job for the geogrid.
* There can only be one RMS grid building job for the grid model that is used.
* The option in the grid building job to *Honor* zone boundaries must be used.
* The zone grid layout must be defined by *Horizon* as reference and not *Surface*.

If all these requirements are satisfied, the keyword *Conformity* is not necessary and will
be ignored and the grid conformity information from the grid building job will be used instead.
In the case some of the requirements are not satisfied, the *Conformity* keyword must be specified.
But note that in this case the grid conformity may be of a type that is not supported and this will
have effect on the field update done by ERT.
*It is recommended to stick to the grid conformity that is implemented.*
If the grid is built outside of RMS or by a script, there are no check and the user will have to
ensure this is correctly specified in the keyword *Conformity*. Some warnings will
appear in log output when it is not possible to check conformity or the conformity is not supported.

Example of RMS python job using this function to copy from geogrid to ERTBOX grid
----------------------------------------------------------------------------------

In this example the geomodel grid has zone *ZoneA* and *ZoneB* and the
petrophysical parameters *P1* and *P2*. They will be copied to the ERTBOX grid
and will get the names *ZoneA_P1*, *ZoneA_P2* and similarly for *ZoneB*. The zone
number is specified as the key and corresponding parameters must come in the same
order in the list for both the keyword *GeoGridParameters* and *ErtboxParameters*.
The available keywords are:

* project (The internal project variable for RMS python jobs)
* debug_print to control printed output to screen (value 0 is no output, value 1 or 2 for more output)
* Mode with the two options *from_geo_to_ertbox* or *from_ertbox_to_geo*
* GeoGridParameters with list of which parameters to use per zone.
* ErtboxParameters with corresponding parameter names in ERTBOX for each zone and parameter combination.
* Conformity with legal values *Proportional, TopConform, BaseConform*.
* GridModelName  specify grid model name in RMS for the geomodel.
* ERTBoxGridName specify the name of the gridmodel used as ERTBOX grid.
* ZoneParam specify the name of the zone parameter in the grid model for the geomodel.
* ExtrapolationMethod specify which method to use. Implemented alternatives are *extend, repeat, mean, zero*.
* SaveActiveParam turns on/off if a 0/1 parameter is to be created for the ERTBOX grid.
* AddNoiseToInactive is optional and will add some small random noise to extrapolated values for grid cell values.

.. code-block:: python

    from fmu.tools.rms import copy_rms_param

    params = {
        "project": project,
        "debug_level": 1,
        "Mode": "from_geo_to_ertbox",
        "GeoGridParameters": {
            1: ["P1", "P2"],
            2: ["P1", "P2"],
        },
        "ErtboxParameters": {
            1: ["ZoneA_P1", "ZoneA_P2"],
            2: ["ZoneB_P1", "ZoneA_P2"],
        },
        "Conformity": {
            1: "BaseConform",
            2: "TopConform",
        },

        "GridModelName": "Geogrid",
        "ZoneParam": "Zone",
        "ERTBoxGridName": "ERTBOX",
        "ExtrapolationMethod": "repeat",
        "SaveActiveParam": True,
        "AddNoiseToInactive": True,
    }
    copy_rms_param(params)

The next example will copy from the ERTBOX grid to the geomodel grid.
This corresponds to using the *from_ertbox_to_geo* mode instead.
In this case the keywords *SaveActiveParam. AddNoiseToInactive,ExtrapolationMethod* are not used.

.. code-block:: python

    from fmu.tools.rms import copy_rms_param

    params ={
        "project": project,
        "debug_level": 1,
        "Mode": "from_ertbox_to_geo",
        "GeoGridParameters": {
            1: ["P1", "P2"],
            2: ["P1", "P2"],
        },
        "ErtboxParameters": {
            1: ["ZoneA_P1", "ZoneA_P2"],
            2: ["ZoneB_P1", "ZoneB_P2"],
        },
        "Conformity": {
            1: "BaseConform",
            2: "TopConform",
        },

        "GridModelName": "Geogrid",
        "ZoneParam": "Zone",
        "ERTBoxGridName": "ERTBOX",
    }
    copy_rms_param(params)
