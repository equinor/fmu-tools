#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
before running, currently using:
source /project/res/komodo/testing/enable
export PYTHONPATH=/project/res/webviz_multiuse/webviz_20180919/:$PYTHONPATH
"""
from __future__ import division, print_function, absolute_import
from fmu.tools.sensitivities import add_webviz_tornadoplots
from webviz import Webviz


html_foldername = './webviz_example'
title = 'Fossekall'

web = Webviz(title, theme='equinor')
configpath = '../tests/data/sensitivities/config/'

# add different types of plots to webportal
add_webviz_tornadoplots(web, configpath +
                         'config_example_geovolume_ensemble.yaml')
add_webviz_tornadoplots(web, configpath +
                         'config_example_geovolume.yaml')
add_webviz_tornadoplots(web, configpath +
                         'config_example_eclipse.yaml')

# Finally, write html
web.write_html(html_foldername, overwrite=True, display=True)
