The qcreset module
==================

The ``qcreset`` module provides methods (functions) to reset the selected data
before starting a forward modelling workflow.


Design philosophy
-----------------

* The client (user) scripts shall be small and simple and easy to use also
  for modellers with little Python experience.
* Input will be a python dictionary
* The ``qcreset`` methods are meant to run inside RMS at the begining of
  a modelling process

Method set_data_empty
---------------------


This method set all data described as input as empty. The data are not deleted
so that the geometry of the data (surfaces or 3D grid properties) should be
preserved and no workflow component (job or other) should be reset.


Signature
~~~~~~~~~

The input of this method is a Python dictionary with defined keys. The key
"project" is required while "horizons", "zones" and "grid_models" are optional
(at least one of them should be provided for the method to have any effect).

project
  The roxar magic keyword ``project`` refering to the current RMS project.

horizons
  A Python dictionary where each key corresponds to the name of the horizons
  category where horizon data need to be made empty. The value associated to
  this key should be a list of horizon names to modify. If a string ``all`` is
  assigned instead of a list, all available horizon names for this category
  will be used.
  Alternatively, if a list of horizons categories is given instead of a
  dictionary, the method will apply to all horizons within these horizons
  categories.

zones
  A Python dictionary where each key corresponds to the name of the zones
  category where zone data need to be made empty. The value associated to
  this key should be a list of zone names to modify. If a string ``all`` is
  assigned instead of a list, all available zone names for this category will
  be used.
  Alternatively, if a list of zones categories is given instead of a dictionary,
  the method will apply to all zones within these zones categories.

grid_models
  A Python dictionary where each key corresponds to the name of the grid models
  where properties need to be made empty. The value associated to this key
  should be a list of property names to modify. If a string ``all`` is
  assigned instead of a list, all available properties for this grid model name
  will be used.
  Alternatively, if a list of grid models names is given instead of a
  dictionary, the method will apply to all properties within these grid models.



Known issues
~~~~~~~~~~~~

* None for now


Examples to run from RMS
~~~~~~~~~~~~~~~~~~~~~~~~

Example 1
^^^^^^^^^

.. code-block:: python

    from fmu.tools.rms import qcreset
    import roxar

    SETUP = {
        "project": project,
        "horizons": {
            "horizon_category_1": ["horizon_name_1", "horizon_name_2"],
            "horizon_category_2": [
                "horizon_name_1",
                "horizon_name_2",
                "horizon_name_3",
                "horizon_name_4"
            ],
            "horizon_category_3": "all"
        },
        "zones": ["zone_category_1"],
        "grid_models": {
            "Geogrid": ["property_1", "property_2"],
            "Simgrid": "all"
        }
    }

    if __name__ == "__main__":
        qcreset.set_data_empty(SETUP)


Method set_data_constant
------------------------


This method set all values of the data described as input to a constant.
The data are therefore not made empty or deleted. This ensure that the geometry
of the data (surfaces or 3D grid properties) is preserved and no workflow
component (job or other) is reset.
This method is more conservative than the ``set_data_empty`` method.


Signature
~~~~~~~~~

The input of this method is a Python dictionary with defined keys. The keys
"project" and "value" are required while "horizons", "zones" and "grid_models"
are optional (at least one of them should be provided for the method to have
any effect).

project
  The roxar magic keyword ``project`` refering to the current RMS project.

value
  The constant value to assign to the data. It could be 0 or -999 for example.
  If discrete properties from grid models are modified, the value should be
  applicable (integer).

horizons
  A Python dictionary where each key corresponds to the name of the horizons
  category where horizon data need to be made empty. The value associated to
  this key should be a list of horizon names to modify. If a string ``all`` is
  assigned instead of a list, all available horizon names for this category
  will be used.
  Alternatively, if a list of horizons categories is given instead of a
  dictionary, the method will apply to all horizons within these horizons
  categories.

zones
  A Python dictionary where each key corresponds to the name of the zones
  category where zone data need to be made empty. The value associated to
  this key should be a list of zone names to modify. If a string ``all`` is
  assigned instead of a list, all available zone names for this category will
  be used.
  Alternatively, if a list of zones categories is given instead of a dictionary,
  the method will apply to all zones within these zones categories.

grid_models
  A Python dictionary where each key corresponds to the name of the grid models
  where properties need to be made empty. The value associated to this key
  should be a list of property names to modify. If a string ``all`` is
  assigned instead of a list, all available properties for this grid model name
  will be used.
  Alternatively, if a list of grid models names is given instead of a
  dictionary, the method will apply to all properties within these grid models.



Known issues
~~~~~~~~~~~~

* None for now


Examples to run from RMS
~~~~~~~~~~~~~~~~~~~~~~~~

Example 1
^^^^^^^^^

.. code-block:: python

    from fmu.tools.rms import qcreset
    import roxar

    SETUP = {
        "project": project,
        "horizons": {
            "horizon_category_1": ["horizon_name_1", "horizon_name_2"],
            "horizon_category_2": [
                "horizon_name_1",
                "horizon_name_2",
                "horizon_name_3",
                "horizon_name_4"
            ],
            "horizon_category_3": "all"
        },
        "zones": ["zone_category_1"],
        "grid_models": {
            "Geogrid": ["property_1", "property_2"],
            "Simgrid": "all"
        },
        "value": 0.0
    }

    if __name__ == "__main__":
        qcreset.set_data_constant(SETUP)


Example 2
^^^^^^^^^

.. code-block:: python

    from fmu.tools.rms import qcreset
    import roxar

    # We split the work into 2 different setups here in order to use different
    # values for different properties (continuous versus discrete)

    SETUP1 = {
        "project": project,
        "grid_models": {
            "Geogrid": ["continuous_property_1", "continuous_property_2"]
        },
        "value": -5.0
    }

    SETUP2 = {
        "project": project,
        "grid_models": {
            "Geogrid": ["discrete_property_1", "discrete_property_2"]
        },
        "value": 999
    }

    if __name__ == "__main__":
        qcreset.set_data_constant(SETUP1)
        qcreset.set_data_constant(SETUP2)
