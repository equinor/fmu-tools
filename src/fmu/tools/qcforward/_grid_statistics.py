"""
This private module in qcforward is used for grid statistics
"""

from . import _parse_data


def grid_statistics(self, data):

    _parse_data.parse(self, data)
