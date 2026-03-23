rms.create_fluid_contacts_from_grid
===================================

Function to create fluid contacts surfaces and outlines from grid contact
parameters. Output will be stored under the General 2D data folder, in folders
``fluid_contact_surfaces`` and ``fluid_contact_outlines``.

By default, the function creates a contact surface and outline for each zone
defined in the grid. To instead create contacts for groups of zones that share
a contact, a custom zone property can be provided.

The contact surface will be created by finding the closest contact cell in each
grid pillar, and gridding them with nearest-node. The contact outline will be
extracted as the boundary polygon of cells whose centers lie above the contact.

The function will check for supported contact types in the project and create output
for the ones available. The supported contact types are:

- ``FWL`` (Free water level)
- ``GOC`` (Gas-oil contact)
- ``GWC`` (Gas-water contact)


A value filter can be applied to remove values below a certain threshold via the
``min_value_filter`` argument. This is useful for removing contact values in
surrounding areas where the value is often set to a low number.

By default, output surfaces have the same resolution as the input grid. To increase
resolution, the grid can be refined before processing using the ``grid_refinement``
argument. It is also possible to match a specific geometry by providing a template
surface via ``template_surf``; the contact surface will be resampled
to this template as a final step. For outlines, the ``rescale_distance`` argument
can be used to resample polygon vertices to a target spacing. This can help reduce
jagged grid artifacts and produce smoother boundaries.


Usage and examples
^^^^^^^^^^^^^^^^^^

**Available arguments**

- ``project``:  The magic ``project`` variable from RMS.
- ``grid_name (str)``:  The name of the grid.
- ``fwl_name (str)``:  The name of the free water level property. Default is ``FWL``.
- ``goc_name (str)``:  The name of the gas-oil contact property. Default is ``GOC``.
- ``gwc_name (str)``:  The name of the gas-water contact property. Default is ``GWC``.
- ``zone_name (str)``:  Optional name of the zone property to use for creating contacts
  for coarse zones.
- ``min_value_filter (float)``:  Minimum value filter, surface values below this will be
  set to undefined. Default is ``0``.
- ``template_surf (xtgeo.RegularSurface)``:  Optional template surface to resample the
  contact surface to as a final step. If not provided, the contact surface will have the
  same dimension as the grid.
- ``grid_refinement (int)`` :  Optional refinement factor to refine the grid before
  processing to increase resolution of the output. Be aware that a high refinement factor
  will reduce performance. Note, this does not affect the grid in RMS.
- ``rescale_distance (float)``: Optional target spacing used to resample contact outlines.

**Examples**

Use a Python job in RMS to call the function with appropriate arguments. 
By default, the function will look for contact properties named ``FWL``, ``GOC`` and ``GWC``.
If your project uses different names, you can specify them as arguments to the function. 
If you have a custom zone property that you want to use for creating contacts for coarse zones,
you can specify its name as well.

Example below shows a minimum configuration 👇

.. code-block:: python

    from fmu.tools.rms import create_fluid_contacts_from_grid

    create_fluid_contacts_from_grid(project=project, gridname="MyGrid")


Example below shows how to use contact properties that do not follow the default naming convention 👇

.. code-block:: python

    from fmu.tools.rms import create_fluid_contacts_from_grid

    create_fluid_contacts_from_grid(
        project=project,
        grid_name="MyGrid",
        fwl_name="FWL_prop",
        goc_name="GOC_prop",
    )


Example using a coarse zone property and a filter to remove areas with contact values less than 1000 👇

.. code-block:: python

    from fmu.tools.rms import create_fluid_contacts_from_grid

    create_fluid_contacts_from_grid(
        project=project,
        grid_name="MyGrid",
        zone_name="Contact_zones",
        min_value_filter=1000,
    )


Example with the use of a template surface and grid refinement by 2 to enhance resolution 👇

.. code-block:: python

    import xtgeo
    from fmu.tools.rms import create_fluid_contacts_from_grid

    template_surf = xtgeo.surface_from_roxar(project, "template_surface", "templates", stype="clipboard")

    create_fluid_contacts_from_grid(
        project=project,
        grid_name="MyGrid",
        grid_refinement=2,
        template_surf=template_surf,
    )
