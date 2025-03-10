"""Top-level package for fmu-tools"""

from __future__ import annotations

import logging
import warnings

_logger = logging.getLogger(__name__)

ROXAR = True
try:
    import rmsapi  # type: ignore # noqa
except ImportError:
    try:
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore", category=DeprecationWarning, module="roxar"
            )
            import roxar as rmsapi  # type: ignore # noqa
    except ImportError:
        ROXAR = False

_logger.debug("Being inside RMS/RMSAPI: %s", ROXAR)

from fmu.tools.extract_grid_zone_tops_etc import extract_grid_zone_tops  # noqa
from fmu.tools.qcforward.qcforward import wellzonation_vs_grid  # noqa
from fmu.tools.qcproperties.qcproperties import QCProperties  # noqa
from fmu.tools.domainconversion.dconvert import DomainConversion  # noqa
from fmu.tools.utilities.sample_attributes import sample_attributes_for_sim2seis  # noqa

__all__ = [
    "extract_grid_zone_tops",
    "wellzonation_vs_grid",
    "QCProperties",
    "DomainConversion",
    "sample_attributes_for_sim2seis",
]

if not ROXAR:
    from fmu.tools.rms import volumetrics  # noqa

    __all__.extend(
        [
            "volumetrics",
        ]
    )

try:
    from fmu.tools.version import version

    __version__ = version
except ImportError:
    __version__ = "0.0.0"
