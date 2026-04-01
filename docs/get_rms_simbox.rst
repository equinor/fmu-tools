rms.get_rms_simbox
============================

The function extract the information from a geomodel grid necessary to
create a box grid representing the RMS simulation box. The purpose is to save the necessary
information to either create a box grid with same resolution, size, location and orientation
as the a xy-regular geogrid. This information can be used in ERT to calculate cell center points
for field parameters where (x,y) coordinates is relevant for the field parameter like in
distance-based localization.

Example of use
----------------

The function is called from a python job in RMS and use the rmsapi to get the information.

Example from Drogon where a small yaml file is written for each of the three zones.
Here zone_index is counted from 0 from top of a (multizone-) geogrid.
Drogon has only single zone grids, therefore zone_index = 0 for all three grids.

.. code-block:: python

    from fmu.tools.rms.get_rms_simbox_params import get_simbox_param, write_simbox

    if __name__ == "__main__":
        grid_model_names = ["Geogrid_Valysar", "Geogrid_Therys", "Geogrid_Volon"]
        for grid_model_name in grid_model_names:
            filename = "simbox_" + grid_model_name + ".yml"
            zone_index = 0
            simbox = get_simbox_param(project, grid_model_name, zone_index)
            write_simbox(filename, simbox)