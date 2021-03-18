# -*- coding: utf-8 -*-

"""Top-level package for fmu-tools"""

from fmu.tools.qcforward.qcforward import wellzonation_vs_grid  # noqa
from fmu.tools.qcproperties.qcproperties import QCProperties  # noqa
from fmu.tools.extract_grid_zone_tops import extract_grid_zone_tops  # noqa

try:
    import roxar  # noqa

    ROXAR = True
except ImportError:
    ROXAR = False

if not ROXAR:

    from .rms import volumetrics  # noqa

    from .sensitivities import DesignMatrix  # noqa
    from .sensitivities import summarize_design  # noqa
    from .sensitivities import calc_tornadoinput  # noqa
    from .sensitivities import excel2dict_design  # noqa

try:
    from .version import version

    __version__ = version
except ImportError:
    __version__ = "0.0.0"
