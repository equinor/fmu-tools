======================
Examples to learn from
======================

.. Notice that YAML files included are also input to testing
   and this secures consistency!

-----------------------------------------
Adding sets of tornado plots to webportal
-----------------------------------------
This example shows how sets of tornado plots from a single sensitivitiy run can be added to a webportal using yaml configuration files and the 'add_webviz_tornadoplot'.

Fossekall on-by-one sensitivities run with design matrix is further explained on FMU wiki portal.


Yaml file for tornado from rms volumes
""""""""""""""""""""""""""""""""""""""
In this example the volume result files have been exported to csv using geogrid_volume.ipl and results from different realisation have been aggregated to one file.

.. literalinclude:: ../tests/data/sensitivities/config/config_example_geovolume.yaml
    :language: yaml

Yaml file for aggregating rms volume files to one before tornado calculations
"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
In this example the volume result files have been exported to csv using geogrid_volume.ipl, but the result files from different realisations must be aggregated to one file before tornado calculations are done.

.. literalinclude:: ../tests/data/sensitivities/config/config_example_geovolume_ensemble.yaml
    :language: yaml

Yaml file for tornado plots from eclipse volumes
""""""""""""""""""""""""""""""""""""""""""""""""
In this example the result file has already been created using CSV_EXPORT1, so there is no need to collect results from different realisations. We want to create tornado plots for FOPT (field oil production total) and FGPT (field gas production total) at end of history (Date = 2013-07-11).

.. literalinclude:: ../tests/data/sensitivities/config/config_example_eclipse.yaml
    :language: yaml


Python example using yaml input
"""""""""""""""""""""""""""""""

.. code-block:: python

    #!/usr/bin/env python
    # -*- coding: utf-8 -*-
    from fmu.tools import sensitivities as sens
    from webportal import Webportal
 
    html_foldername = './webportal_example'
    title = 'Fossekall'
 
    web = Webportal(title)
    configpath = '../input/config/'
 
    # add different types of plots to webportal
    sens.add_webviz_tornadoplots(web, configpath +
                             'config_example_geovolume.yaml') 
    sens.add_webviz_tornadoplots(web, configpath +
                             'config_example_eclipse.yaml')
 
    # Finally, write html
    web.write_html(html_foldername, overwrite=True, display=True)

----------------------------
Use parts in your own set up
----------------------------

If you want another design and setup than provided with 'add_webviz_tornadoplot'
you can use the functionallity in fmu.tools.sensitivity and make your own script.

Example: summary of design matrix
"""""""""""""""""""""""""""""""""
Use summarize_design on a design matrix on standard fmu format for one-by-one sensitivities to summarize the realisation numbers for each SENSNAME and SENSTYPE, and whether they are scalar sensitivities or monte carlo sensitivities.

.. code-block:: python

    #!/usr/bin/env python
    # -*- coding: utf-8 -*-
 
    from fmu.tools.sensitivities import summarize_design
 
    # Full or relative path to design matrix .xlsx or .csv format
    designname = '../tests/data/sensitivities/distributions/design.xlsx' 
    # Only include for excel files; name of sheet that contains design matrix
    designsheet = 'DesignSheet01' 
 
    designtable = summarize_design(designname, designsheet)
 
    # designtable is a pandas DataFrame with summary of the design in the designmatrix,
    # i.e. it will contain realisation number, senstype and senscase for each sensitivity

Example: calculating one tornadotable 
""""""""""""""""""""""""""""""""""""""
Using calc_tornadoplot with a 'designsummary' and a resultfile as input, and calculating statistics to visualize in a tornado plot for a given choice of SELECTOR (e.g. ZONE:'Ile') and RESPONSE (e.g. STOIIP_OIL). The reference is usually the mean of the realizations in the "seed sensitivity", but it can also be specified as a single realisation number, e.g. if you have a reference case in realization 0. Statistics showing the difference to the reference can be calculated as absolute values, or as percentages. You could also choose to exclude from the plot, sensitivities that are smaller than the seed sensitivity P10/P90.

.. code-block:: python

    #!/usr/bin/env python
    # -*- coding: utf-8 -*-
 
    import pandas as pd
    from fmu.tools.sensitivities import calc_tornadoplot
 
    designtable=pd.read_csv('designsummary.csv')
    results = pd.read_csv('resultfile.csv')
    response = 'STOIIP_OIL'
    selectors = ['ZONE', 'REGION'] # One or several in a list
    # One or several in a list of lists
    selection = [['Ile','Tofte'], ['SegmentA']] # Will sum Ile and Tofte volumes first
    reference = 'seed' # Alternatively a single realisation number
    scale = 'percentage' # Alterntively 'absolute'
    cutbyseed = True # If excluding sensitivities smaller than seed, default is False 
 
    (tornadotable, ref_value) = calc_tornadoinput(
        designtable,
        results, response,
        selectors, selection,
        reference, scale, cutbyseed)
 
    # tornadotable is a pandas DataFrame for visualisation of TornadoPlot in webviz
    # ref_value is the average of the reference. 
    # Can be useful to include in label/title in webviz
