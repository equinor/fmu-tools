rms.export_and_import_field_parameters
=======================================

The  export and import functions described below supports a workflow where
both facies and petrophysical properties are updated as field parameters in ERT.
The implemented functions in the module *fmu.tools.rms.update_petro_real* are::

    export_initial_field_parameters
    import_updated_field_parameters

Both the export and import function the same set of petrophysical variables in the
same workflow. Therefore, they both read this information from a configuration file
in YAML format that is also shared with the function *generate_petro_jobs*.

Export petrophysical parameters as field parameters to be used in ERT FIELD keyword
-------------------------------------------------------------------------------------

Example of use of the export function

.. code-block:: python

    from fmu.tools.rms import export_initial_field_parameters
    from fmu.tools.rms.generate_petro_jobs_for_field_update import read_specification_file

    DEBUG_PRINT=True
    CONFIG_FILE_NAME_VALYSAR = "../input/config/field_update/generate_petro_jobs_valysar.yml"
    CONFIG_FILE_NAME_THERYS = "../input/config/field_update/generate_petro_jobs_therys.yml"
    CONFIG_FILE_NAME_VOLON = "../input/config/field_update/generate_petro_jobs_volon.yml"
    ERTBOX_GRID = "ERTBOX"


    def export_fields():
        spec_dict = read_specification_file(CONFIG_FILE_NAME_VALYSAR)
        used_petro_dict = spec_dict["used_petro_var"]
        export_initial_field_parameters(
            project,
            used_petro_dict,
            grid_model_name=ERTBOX_GRID,
            zone_name_for_single_zone_grid="Valysar",
            debug_print= DEBUG_PRINT)

        spec_dict = read_specification_file(CONFIG_FILE_NAME_THERYS)
        used_petro_dict = spec_dict["used_petro_var"]
        export_initial_field_parameters(
            project,
            used_petro_dict,
            grid_model_name=ERTBOX_GRID,
            zone_name_for_single_zone_grid="Therys",
            debug_print= DEBUG_PRINT)

        spec_dict = read_specification_file(CONFIG_FILE_NAME_VOLON)
        used_petro_dict = spec_dict["used_petro_var"]
        export_initial_field_parameters(
            project,
            used_petro_dict,
            grid_model_name=ERTBOX_GRID,
            zone_name_for_single_zone_grid="Volon",
            debug_print= DEBUG_PRINT)

    if __name__ == "__main__":
        export_fields()


Import petrophysical parameters used as field parameters to be used in ERT FIELD keyword
------------------------------------------------------------------------------------------

Example of use of the import function

.. code-block:: python

    from fmu.tools.rms import import_updated_field_parameters
    from fmu.tools.rms.generate_petro_jobs_for_field_update import read_specification_file


    DEBUG_PRINT = False
    CONFIG_FILE_NAME_VALYSAR = "../input/config/field_update/generate_petro_jobs_valysar.yml"
    CONFIG_FILE_NAME_THERYS  = "../input/config/field_update/generate_petro_jobs_therys.yml"
    CONFIG_FILE_NAME_VOLON   = "../input/config/field_update/generate_petro_jobs_volon.yml"
    ERTBOX_GRID = "ERTBOX"

    def import_fields():
        spec_dict = read_specification_file(CONFIG_FILE_NAME_VALYSAR)
        used_petro_dict = spec_dict["used_petro_var"]
        import_updated_field_parameters(
            project,
            used_petro_dict,
            grid_model_name=ERTBOX_GRID,
            zone_name_for_single_zone_grid="Valysar",
            debug_print=DEBUG_PRINT)

        spec_dict = read_specification_file(CONFIG_FILE_NAME_THERYS)
        used_petro_dict = spec_dict["used_petro_var"]
        import_updated_field_parameters(
            project,
            used_petro_dict,
            grid_model_name=ERTBOX_GRID,
            zone_name_for_single_zone_grid="Therys",
            debug_print=DEBUG_PRINT)

        spec_dict = read_specification_file(CONFIG_FILE_NAME_VOLON)
        used_petro_dict = spec_dict["used_petro_var"]
        import_updated_field_parameters(
            project,
            used_petro_dict,
            grid_model_name=ERTBOX_GRID,
            zone_name_for_single_zone_grid="Volon",
            debug_print=DEBUG_PRINT)

    if __name__ == "__main__":
        import_fields()

