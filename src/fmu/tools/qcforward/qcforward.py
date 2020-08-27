"""
The qcforward methods module

This is a function based approach, but in many cases it may be better
if the user make an explicit instance in the calling script, in particular if
the job is about to be read numerous times with the ``reuse`` option


I.e::

    from fmu.tools import qcforward

    # .. define data

    qcforward.wellzonation_vs_grid(data)

    # vs

    qcjob = qcforward.WellZonationVsGrid()
    qcjob.run(data)


"""
from ._wellzonation_vs_grid import WellZonationVsGrid


def wellzonation_vs_grid(data):
    """Check well zonation or perforations vs 3D grid.

    Args:
        data (dict): This is dictonary telling where data comes from

    """

    wzong = WellZonationVsGrid()
    wzong.run(data)
