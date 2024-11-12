
The fmu-tools utilities package
###############################

Sample attributes for sim2seis
==============================

This function takes an attribute surface (typically seismic attributes from 4D)
and generates points with error values as input to ERT and Webviz, on approximate
simgrid resolution.

A grid model (typically the simgrid) is required, with (optionally) region and zones.

Examples
--------

Example 1
^^^^^^^^^

Sample an attribute surface and generate points with error values.

.. code-block:: python

    import xtgeo
    
    from fmu.tools import sample_attributes_for_sim2seis
    
    grd = xtgeo.grid_from_file("somefile.roff")
    region = xtgeo.gridproperty_from_file("somefile.roff", name="Region")
    zones = xtgeo.gridproperty_from_file("somefile.roff", name="Zone")
    attr = xtgeo.surface_from_file("some_attr.gri")

    df = sample_attributes_for_sim2seis(
        grd,
        region=region,
        zones=zones,
        attribute=attr,
        attribute_error=0.2,  # relative error if number
        attribute_minimum_error=0.005,
        position=("Valysar", "top"),
    )

    ert_out = "../ert/observations/seismic/some_attr_1.txt"
    webviz_out = "../webviz/observations/seismic/meta--some_attr_1.txt"
    df[["OBS", "OBS_ERROR"]].to_csv(
        header=False,
        index=False,
        sep=" ",
        float_format="%.6f",
        path_or_buf=ert_out,
    )
    df.to_csv(
        index=False,
        float_format="%.6f",
        path_or_buf=webviz_out,
    )
