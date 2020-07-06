"""
This private module in qcforward is used to check wellzonation vs grid
"""

import xtgeo
from . import _parse_data


def wellzonation_vs_grid(self, data):

    _parse_data.parse(self, data)
