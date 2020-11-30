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
from ._grid_statistics import GridStatistics
from ._grid_quality import GridQuality


def wellzonation_vs_grid(data, project=None):
    """Check well zonation or perforations vs 3D grid.

    Args:
        data (dict): This is dictonary telling where data comes from

    """

    wzong = WellZonationVsGrid()
    wzong.run(data, project=project)


def grid_statistics(data, project=None):
    """Check statistics in 3D grid against user input.

    Args:
        data (dict or str): The input data either as a Python dictionary or
            a path to a YAML file
    """

    gps = GridStatistics()
    gps.run(data, project=project)


def grid_quality(data, project=None):
    """Check grid quality in 3D grid against user input.

    Args:
        data (dict): The input data either as a Python dictionary or
            a path to a YAML file
    """

    gqual = GridQuality()
    gqual.run(data, project=project)
