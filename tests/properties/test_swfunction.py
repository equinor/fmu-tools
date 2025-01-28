"""Testing properties Sw"""

# for tests vs RMS cf /private/jriv/work/testing/swfunc/test_swfunc.rms13.1.2
import math

import numpy as np
import pytest
import xtgeo

from fmu.tools.properties import SwFunction


@pytest.mark.parametrize(
    "avalue, bvalue, ffl, direct, cellmethod, expected_mean",
    [
        (1, -2, 13, True, "cell_center_above_ffl", 0.408742),
        (1, -2, 13, False, "cell_center_above_ffl", 0.412536),
        (0.3, -5, 12.5, True, "cell_center_above_ffl", 0.547251),
        (0.3, -5, 12.5, False, "cell_center_above_ffl", 0.549613),
        (0.3, -5, 12.5, False, "cell_corners_above_ffl", 0.549613),
    ],
)
def test_swj_simple(avalue, bvalue, ffl, direct, cellmethod, expected_mean):
    """Test a simple SwJ setup, expected mean are checked with RMS Sw job"""

    grid1 = xtgeo.create_box_grid((10, 10, 20), increment=(1, 1, 1), origin=(0, 0, 0))
    poro = 0.3
    perm = 300

    xvalue = math.sqrt(perm / poro)

    sw_obj = SwFunction(
        grid=grid1,
        a=avalue,
        b=bvalue,
        x=xvalue,
        ffl=ffl,
        invert=True,
        method=cellmethod,
    )
    sw = sw_obj.compute("direct" if direct else "integrated")
    assert sw.values.mean() == pytest.approx(expected_mean, rel=0.01)


def test_swj_simple_threshold_2grids():
    """Test a simple SwJ setup, expected mean are checked with RMS Sw job.

    In this case, the threshold height will be approx 5.42 meters. Values for assertion
    are checked in RMS.
    """

    grid1 = xtgeo.create_box_grid((10, 10, 20), increment=(1, 1, 1), origin=(0, 0, 0))
    grid2 = xtgeo.create_box_grid(
        (10, 10, 200), increment=(1, 1, 0.1), origin=(12, 0, 0)
    )
    poro = 0.3
    perm = 1.0
    avalue = 10.0
    bvalue = -5.0
    ffl = 12.5
    cellmethod = "cell_corners_above_ffl"

    xvalue = math.sqrt(perm / poro)

    sw_obj = SwFunction(
        grid=grid1,
        a=avalue,
        b=bvalue,
        x=xvalue,
        ffl=ffl,
        invert=True,
        method=cellmethod,
    )
    sw = sw_obj.compute("integrated")
    assert sw.values.mean() == pytest.approx(0.9689, rel=0.01)

    sw_obj = SwFunction(
        grid=grid2,
        a=avalue,
        b=bvalue,
        x=xvalue,
        ffl=ffl,
        invert=True,
        method=cellmethod,
    )
    sw = sw_obj.compute("integrated")

    assert sw.values.mean() == pytest.approx(0.9689, rel=0.01)
    assert float(sw.values[0, 0, 70]) == pytest.approx(1, rel=0.0001)


@pytest.mark.parametrize(
    "direct, cellmethod, expected_mean, exp_cell1",
    [
        (True, "cell_center_above_ffl", 0.7057, 0.046719),  # n/a vs RMS
        (False, "cell_center_above_ffl", 0.70736, 0.046724),  # n/a vs RMS
        (False, "cell_corners_above_ffl", 0.674485, 0.046791),  # n/a vs RMS
    ],
)
def test_swj_simple_reek(direct, cellmethod, expected_mean, exp_cell1, testdata_path):
    """Test a simple SwJ setup, expected mean are checked with RMS Sw job"""

    griddata1 = testdata_path / "3dgrids/reek/reek_sim_grid.roff"
    porodata1 = testdata_path / "3dgrids/reek/reek_sim_poro.roff"
    permdata1 = testdata_path / "3dgrids/reek/reek_sim_permx.roff"

    avalue = 1
    bvalue = -0.5
    ffl = 1700

    grid = xtgeo.grid_from_file(griddata1)
    poro = xtgeo.gridproperty_from_file(porodata1)
    perm = xtgeo.gridproperty_from_file(permdata1)

    xval = perm.copy()

    xval.values = np.ma.sqrt(perm.values / poro.values)

    sw_obj = SwFunction(
        grid=grid,
        a=avalue,
        b=bvalue,
        x=xval,
        ffl=ffl,
        invert=False,
        method=cellmethod,
    )

    sw = sw_obj.compute("direct" if direct else "integrated")

    assert sw.values.mean() == pytest.approx(expected_mean, rel=0.01)

    assert float(sw.values[32, 35, 6]) == pytest.approx(exp_cell1, abs=0.0001)


def test_sw_bvw():
    """Test a simple BVW setup, expected values are checked from spreadsheet.

    In BVW, the Sw = A * P^B * poro^C

    Here A, B, C can be derived from regressions

    A = a1*poro + a2
    B = b1*poro + b2
    C = c1*poro + c2  ...or...  c1*poro + c2 - 1

    The P kan be normalized capillary pressure, and for gas above an oil zone with
    thickness H_oil, this will be

    P = Pcn = H_oil * (gradw - grado)/ado  +  h * (gradw - gradg)/adg

    """
    poro = 0.3
    a1 = -0.5561
    a2 = 0.3385
    b1 = 0.01985
    b2 = -0.3953
    c1 = 5.648
    c2 = 0.4987

    rw = 0.1002
    rg = 0.0113
    ro = 0.0785

    adg = 42.7
    ado = 26.0
    h_oil = 3

    ffl = 30.5  # FOL in this example

    grid = xtgeo.create_box_grid((1, 1, 200))

    a_term = a1 * poro + a2
    b_term = b1 * poro + b2
    c_term = c1 * poro + c2 - 1.0

    assert a_term == pytest.approx(0.171670)
    assert b_term == pytest.approx(-0.389345)
    assert c_term == pytest.approx(2.193100 - 1.0)
    # was done in input

    avalue = a_term * poro**c_term
    bvalue = b_term
    mvalue = h_oil * (rw - ro) / ado
    xvalue = (rw - rg) / adg

    # PCN at 10m above FFL:

    # in practice, this will always be the first term(?)
    m10 = min([h_oil * (rw - ro) / ado, max([0, 10 + h_oil * (rw - ro) / ado])])

    # in practice, this will always be the second term(?)
    x10 = max([0, 10 * (rw - rg) / adg])
    assert m10 + x10 == pytest.approx(0.0233235)

    manual10 = a_term * ((m10 + x10) ** b_term) * (poro**c_term)
    assert manual10 == pytest.approx(0.176335192)

    sw_obj = SwFunction(
        grid=grid,
        a=avalue,
        b=bvalue,
        m=mvalue,
        x=xvalue,
        ffl=ffl,
        method="cell_center_above_ffl",
        debug=False,
    )
    sw = sw_obj.compute("direct")

    sw10 = float(sw.values[:, :, 20])  # 10 meter above contact
    assert sw10 == pytest.approx(manual10)

    sw20 = float(sw.values[:, :, 10])  # 20 meter above contact
    assert sw20 == pytest.approx(0.13755086)

    sw = sw_obj.compute("integrated")
    sw10_i = float(sw.values[:, :, 20])
    assert sw10_i == pytest.approx(sw10, abs=0.0001)


def test_sw_brooks_corey():
    """Test a simple Brooks-Corey setup, expected values are checked from spreadsheet.

    In BVW, the Sw = (PCNe / Pcn)^(1/N)

    Sw,final = Swi + (1-Swi) * Sw

    Perhaps some regressions are made:
    Swi = a1*poro + a2
    Pcne = b1*poro^b2
    N = c1*poro + c2


    The Pcn is be normalized capillary pressure, and for gas above an oil zone with
    thickness H_oil, this will be

    Pcn = H_oil * (gradw - grado)/ado  +  h * (gradw - gradg)/adg

    a = Pcne^(1/N)
    b = (1/N)
    x = Pcn


    """
    poro = 0.3
    a1 = 0.0
    a2 = 0.3
    b1 = 4.4e-06
    b2 = -5.7
    c1 = -28.45
    c2 = 10.42

    rw = 0.1002
    rg = 0.0113
    ro = 0.0785

    adg = 42.7
    ado = 26.0
    h_oil = 3

    ffl = 30.5  # FOL in this example

    grid = xtgeo.create_box_grid((1, 1, 200))

    swi = a1 * poro + a2
    pcne = b1 * poro**b2
    n = c1 * poro + c2

    assert swi == pytest.approx(0.3)
    assert n == pytest.approx(1.885)
    assert pcne == pytest.approx(0.004205925)

    avalue = pcne ** (1.0 / n)
    bvalue = -1.0 / n
    mvalue = h_oil * (rw - ro) / ado
    xvalue = (rw - rg) / adg

    sw_obj = SwFunction(
        grid=grid,
        a=avalue,
        b=bvalue,
        m=mvalue,
        x=xvalue,
        ffl=ffl,
        method="cell_center_above_ffl",
        debug=False,
    )
    sw = sw_obj.compute("direct")

    sw10 = float(sw.values[:, :, 20])  # 10 meter above contact
    assert sw10 == pytest.approx(0.40303321)
    sw10final = swi + (1 - swi) * sw10
    assert sw10final == pytest.approx(0.582123)

    sw20 = float(sw.values[:, :, 10])  # 20 meter above contact
    assert sw20 == pytest.approx(0.28731234)

    sw = sw_obj.compute("integrated")
    sw10_i = float(sw.values[:, :, 20])
    assert sw10_i == pytest.approx(sw10, abs=0.001)
