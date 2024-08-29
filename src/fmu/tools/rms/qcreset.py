import warnings
from typing import Any, Dict, List, Union

try:
    import _roxar  # type: ignore
except ModuleNotFoundError:
    try:
        import _rmsapi as _roxar  # type: ignore
    except ModuleNotFoundError:
        warnings.warn("This script only supports interactive RMS usage", UserWarning)


def _set_safe_value(
    project: Any, surf_type: str, name: str, data_type: str, value: float
):
    """Set the horizon or zone surface to the defined value.

    Args:
        project: the roxar project.
        surf_type: the type of surface.
            It should be the string "horizons" or "zones".
        name: the name the of surface.
        value: the value (int or float) to be assigned to the surface
    """

    try:
        if surf_type == "horizons":
            surf = project.horizons[name][data_type]
        else:
            surf = project.zones[name][data_type]
        grid2d = surf.get_grid()
        grid2d.set_values(grid2d.get_values() * 0.0 + value)
        surf.set_grid(grid2d)
        print(" >> >> " + name)
    except Exception as e:
        print(" >> >> " + name + " cannot be modified")
        print(e)


def _set_safe_empty(project: Any, surf_type: str, name: str, data_type: str):
    """Set empty the horizon or zone surface.

    Args:
        project: the roxar project.
        surf_type: the type of surface.
            It should be the string "horizons" or "zones".
        name: the name the of surface.
    """
    try:
        if surf_type == "horizons":
            surf = project.horizons[name][data_type]
        else:
            surf = project.zones[name][data_type]
        surf.set_empty()
        print(" >> >> " + name)
    except Exception as e:
        print(" >> >> " + name + " cannot be modified")
        print(e)


def _set_surfaces_value(
    project: Any,
    surf_type: str,
    dict_val: Union[List, Dict],
    value: float,
):
    """Set a group of surfaces to a given value.

    Args:
        project: roxar project.
        surf_type: the type of surface.
            It should be the string "horizon" or "zone".
        dict_val: a list of surfaces or a dictionary of surfaces categories
            (keys) with a list of surfaces names (value).
        value: the value to assign to the surfaces.
    """
    if surf_type == "horizons":
        surfaces = project.horizons
    elif surf_type == "zones":
        surfaces = project.zones
    else:
        raise ValueError("surf_type must be 'horizons' or 'zones'")

    if isinstance(dict_val, list):
        # work directly at horizon/zone category level
        for data_type in dict_val:
            print(" >> " + data_type)
            for surface in surfaces:
                _set_safe_value(project, surf_type, surface.name, data_type, value)
    elif isinstance(dict_val, dict):
        # check setup for each horizon/zone category (list vs. all)
        surf_cat = dict_val.keys()
        for data_type in surf_cat:
            print(" >> " + data_type)
            surf_names = dict_val[data_type]
            if isinstance(surf_names, str):
                if surf_names == "all":
                    for surface in surfaces:
                        _set_safe_value(
                            project, surf_type, surface.name, data_type, value
                        )
                else:
                    raise ValueError(
                        "keyword '" + surf_names + "' not recognized, 'all' expected!"
                    )
            elif isinstance(surf_names, list):
                for surf_name in surf_names:
                    _set_safe_value(project, surf_type, surf_name, data_type, value)
    else:
        raise TypeError(
            "Value associated with key '"
            + surf_type
            + "' must be of type list or dict!"
        )


def _set_surfaces_empty(project: Any, surf_type: str, dict_val: Union[List, Dict]):
    """Set empty a group of surfaces.

    Args:
        project: roxar project.
        surf_type: the type of surface.
            It should be the string "horizon" or "zone".
        dict_val: a list of surfaces or a dictionary of surfaces categories
            (keys) with a list of surfaces names (value).
    """
    if surf_type == "horizons":
        surfaces = project.horizons
    elif surf_type == "zones":
        surfaces = project.zones
    else:
        raise ValueError("surf_type must be 'horizons' or 'zones'")

    if isinstance(dict_val, list):
        # work directly at horizon/zone category level
        for data_type in dict_val:
            print(" >> " + data_type)
            for surface in surfaces:
                _set_safe_empty(project, surf_type, surface.name, data_type)
    elif isinstance(dict_val, dict):
        # check setup for each horizon/zone category (list vs. all)
        surf_cat = dict_val.keys()
        for data_type in surf_cat:
            print(" >> " + data_type)
            surf_names = dict_val[data_type]
            if isinstance(surf_names, str):
                if surf_names == "all":
                    for surface in surfaces:
                        _set_safe_empty(project, surf_type, surface.name, data_type)
                else:
                    raise ValueError(
                        "keyword '" + surf_names + "' not recognized, 'all' expected!"
                    )
            elif isinstance(surf_names, list):
                for surf_name in surf_names:
                    _set_safe_empty(project, surf_type, surf_name, data_type)
    else:
        raise TypeError(
            "Value associated with key '"
            + surf_type
            + "' must be of type list or dict!"
        )


def set_data_constant(config: Dict):
    """Set data from RMS constant.

    This method is a utility in order to set surface and 3D grid property data
    to a given value. The value must be of the correct type (if discrete 3D
    property for example). The purpose of it is to make sure that those data
    are properly generated by the modelling workflow and not inherited from a
    previous run with the corresponding jobs deactivated. The data are set to a
    value triggering attention and not deleted in order not to reset some jobs
    in RMS.

    The input of this method is a Python dictionary with defined keys. The keys
    "project" and "value" are required while "horizons", "zones" and
    "grid_models" are optional (at least one of them should be provided for the
    method to have any effect).

    Args:
        project: The roxar magic keyword ``project`` refering to the current
            RMS project.

        value: The constant value to assign to the data. It could be 0 or -999
            for example. If discrete properties from grid models are modified,
            the value should be applicable (integer).

        horizons: A Python dictionary where each key corresponds to the name of
            the horizons category where horizon data need to be modified. The
            value associated to this key should be a list of horizon names to
            modify. If a string ``all`` is assigned instead of a list, all
            available horizon names for this category will be used.
            Alternatively, if a list of horizons categories is given instead of
            a dictionary, the method will apply to all horizons within these
            horizons categories.

        zones: A Python dictionary where each key corresponds to the name of
            the zones category where zone data need to be modified. The value
            associated to this key should be a list of zone names to modify. If
            a string ``all`` is assigned instead of a list, all available zone
            names for this category will be used.
            Alternatively, if a list of zones categories is given instead of a
            dictionary, the method will apply to all zones within these zones
            categories.

        grid_models: A Python dictionary where each key corresponds to the name
            of the grid models where properties need to be modified. The
            value associated to this key should be a list of property names to
            modify. If a string ``all`` is assigned instead of a list, all
            available properties for this grid model name will be used.
            Alternatively, if a list of grid models names is given instead of a
            dictionary, the method will apply to all properties within these
            grid models.
    """
    if not isinstance(config, dict):
        raise TypeError("Argument must be a Python dictionary!")
    assert "project" in config, "Input dict must contain key 'project'!"
    project = config["project"]
    if not isinstance(project, _roxar.Project):
        raise RuntimeError("This run must be ran in an RoxAPI environment!")

    assert "value" in config, "Input dict must contain key 'value'!"
    value = config["value"]

    # HORIZON DATA
    if "horizons" in config:
        print("Set horizons values to " + str(value) + "...")
        _set_surfaces_value(project, "horizons", config["horizons"], value)

    # ZONE DATA
    if "zones" in config:
        print("Set zones values to " + str(value) + "...")
        _set_surfaces_value(project, "zones", config["zones"], value)

    # GRID MODEL DATA
    if "grid_models" in config:
        print("Set 3D grid properties values to " + str(value) + "...")
        if isinstance(config["grid_models"], list):
            # work directly at grid models level
            for gridname in config["grid_models"]:
                print(" >> " + gridname)
                grid = project.grid_models[gridname]
                for prop in grid.properties:
                    try:
                        prop.set_values(prop.get_values() * 0 + value)
                        print(" >> >> " + prop.name)
                    except Exception as e:
                        print(" >> >> " + prop.name + " is already empty")
                        print(e)
        elif isinstance(config["grid_models"], dict):
            # check setup for each grid models (list vs. all)
            gridnames = config["grid_models"].keys()
            for gridname in gridnames:
                print(" >> " + gridname)
                grid = project.grid_models[gridname]
                propnames = config["grid_models"][gridname]
                if isinstance(propnames, str):
                    if propnames == "all":
                        for prop in grid.properties:
                            try:
                                prop.set_values(prop.get_values() * 0 + value)
                                print(" >> >> " + prop.name)
                            except Exception as e:
                                print(" >> >> " + prop.name + " is already empty")
                                print(e)
                    else:
                        raise Exception(
                            "keyword " + propnames + "not recognized, 'all' expected!"
                        )
                elif isinstance(propnames, list):
                    for propname in propnames:
                        try:
                            prop = grid.properties[propname]
                            prop.set_values(prop.get_values() * 0 + value)
                            print(" >> >> " + prop.name)
                        except Exception as e:
                            print(" >> >> " + prop.name + " is already empty")
                            print(e)
        else:
            raise TypeError(
                "Value associated with key 'zones' must be of type list or dict!"
            )

    print("End of function set_data_constant().")


def set_data_empty(config: Dict):
    """Set data from RMS empty.

    This method is a utility in order to set empty surface and 3D grid property
    data. The value must be of the correct type (if discrete 3D property for
    example). The purpose of it is to make sure that those data are properly
    generated by the modelling workflow and not inherited from a previous run
    with the corresponding jobs deactivated.

    The input of this method is a Python dictionary with defined keys. The keys
    "project" and "value" are required while "horizons", "zones" and
    "grid_models" are optional (at least one of them should be provided for the
    method to have any effect).

    Input configrations:

    project: The roxar magic keyword ``project`` refering to the current
        RMS project.

    horizons: A Python dictionary where each key corresponds to the name of
        the horizons category where horizon data need to be made empty. The
        value associated to this key should be a list of horizon names to
        modify. If a string ``all`` is assigned instead of a list, all
        available horizon names for this category will be used.
        Alternatively, if a list of horizons categories is given instead of
        a dictionary, the method will apply to all horizons within these
        horizons categories.

    zones: A Python dictionary where each key corresponds to the name of
        the zones category where zone data need to be made empty. The value
        associated to this key should be a list of zone names to modify. If
        a string ``all`` is assigned instead of a list, all available zone
        names for this category will be used.
        Alternatively, if a list of zones categories is given instead of a
        dictionary, the method will apply to all zones within these zones
        categories.

    grid_models: A Python dictionary where each key corresponds to the name
        of the grid models where properties need to be made empty. The
        value associated to this key should be a list of property names to
        modify. If a string ``all`` is assigned instead of a list, all
        available properties for this grid model name will be used.
        Alternatively, if a list of grid models names is given instead of a
        dictionary, the method will apply to all properties within these
        grid models.



    Args:

        config: Configration as a dictionary. See examples in documentation

    """

    if not isinstance(config, dict):
        raise TypeError("Argument must be a Python dictionary!")
    assert "project" in config, "Input dict must contain key 'project'!"
    project = config["project"]
    if not isinstance(project, _roxar.Project):
        raise RuntimeError("This run must be ran in an RoxAPI environment!")

    # HORIZON DATA
    if "horizons" in config:
        print("Set empty horizons...")
        _set_surfaces_empty(project, "horizons", config["horizons"])

    # ZONE DATA
    if "zones" in config:
        print("Set empty zones...")
        _set_surfaces_empty(project, "zones", config["zones"])

    # GRID MODEL DATA
    if "grid_models" in config:
        print("Set empty 3D grid properties...")
        if isinstance(config["grid_models"], list):
            # work directly at grid models level
            for gridname in config["grid_models"]:
                print(" >> " + gridname)
                grid = project.grid_models[gridname]
                for prop in grid.properties:
                    prop.set_empty()
                    print(" >> >> " + prop.name)
        elif isinstance(config["grid_models"], dict):
            # check setup for each grid models (list vs. all)
            gridnames = config["grid_models"].keys()
            for gridname in gridnames:
                print(" >> " + gridname)
                grid = project.grid_models[gridname]
                propnames = config["grid_models"][gridname]
                if isinstance(propnames, str):
                    if propnames == "all":
                        for prop in grid.properties:
                            prop.set_empty()
                            print(" >> >> " + prop.name)
                    else:
                        raise Exception(
                            "keyword " + propnames + "not recognized, 'all' expected!"
                        )
                elif isinstance(propnames, list):
                    for propname in propnames:
                        prop = grid.properties[propname]
                        prop.set_empty()
                        print(" >> >> " + prop.name)
        else:
            raise TypeError(
                "Value associated with key 'zones' must be of type list or dict!"
            )

    print("End of function set_data_empty().")
