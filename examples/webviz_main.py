#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Loading nested configs for FMU"""
from __future__ import division, print_function, absolute_import
from fmu.tools import sensitivities as sens
from webportal import Webportal


html_foldername = './webportal_example'
title = 'Snorreberg'

web = Webportal(title)
configpath = '../tests/data/sensitivities/config/'

# add different types of plots to webportal
sens.add_webviz_tornadoplots(web, configpath +
                             'config_example_geovolume_ensemble.yaml')
sens.add_webviz_tornadoplots(web, configpath +
                             'config_example_geovolume.yaml')
sens.add_webviz_tornadoplots(web, configpath +
                             'config_example_eclipse.yaml')

# Finally, write html
web.write_html(html_foldername, overwrite=True, display=True)
