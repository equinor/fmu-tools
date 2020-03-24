"""Testing qcforward methods"""

from __future__ import absolute_import, division, print_function  # PY2


from fmu.tools import qcforward as qcf


def test_zonelog_vs_grid_asfiles():
    """Testing the zonelog vs grid functionality using files"""

    myqc = qcf.QCForward()

    assert isinstance(myqc, qcf.QCForward)

    myqc.wellzonation_vs_grid()


def test_zonelog_vs_grid_asrms():
    """Testing the zonelog vs grid functionality inside RMS"""

    myqc = qcf.QCForward()

    assert isinstance(myqc, qcf.QCForward)

    myqc.wellzonation_vs_grid()
