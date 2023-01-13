"""
Processing of volumetrics from RMS
"""

from .import_localmodule import import_localmodule
from .volumetrics import rmsvolumetrics_txt2df

__all__ = ["rmsvolumetrics_txt2df", "import_localmodule"]
