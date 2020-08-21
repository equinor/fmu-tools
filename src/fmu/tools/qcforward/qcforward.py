"""The qcforward methods module"""
from ._wellzonation_vs_grid import WellZonationVsGrid


def wellzonation_vs_grid(data):
    """Check well zonation or perforations vs 3D grid.

    Args:
        data (dict): This is dictonary telling where data comes from

    """

    wzong = WellZonationVsGrid()
    wzong.main(data)


# def grid_statistics(self, data):
#     """Check grid statistics..."""

#     self._method = "grid_statistics"
#     QCC.print_info("Running {}".format(self._method))
#     data = self.handle_data(data)

#     _gstat.grid_statistics(self, data)
