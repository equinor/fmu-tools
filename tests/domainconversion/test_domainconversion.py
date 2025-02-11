import logging
import os

import numpy as np
import pytest
import xtgeo

from fmu.tools.domainconversion import DomainConversion

logger = logging.getLogger(__name__)


def plot_section(cube, simplesurfs, title="", limits_from=None):
    """Simple plotting, while testing interactive"""
    if "PLOT" not in os.environ:
        return

    import matplotlib.lines as lines
    import matplotlib.pyplot as plt

    xline = 3

    data3d = cube.values

    dsurfs, tsurfs = simplesurfs

    fig, ax = plt.subplots()

    data = data3d[:, xline, :]

    _cube = limits_from if limits_from else cube

    # Set the x-axis (trace) limits
    ax.set_xlim([_cube.xori, _cube.xori + (_cube.ncol - 1) * _cube.xinc])

    # Set the y-axis (depth) limits
    ax.set_ylim([_cube.zori, _cube.zori + (_cube.nlay - 1) * _cube.zinc])

    use_extent = [-0.5, 2.5, 100.5, -0.5]
    im = ax.imshow(
        data.T, cmap="seismic", extent=use_extent, aspect="auto", interpolation=None
    )
    logger.info("Current extent is %s", im.get_extent())

    for ds in dsurfs:
        x, _, z = ds.get_xyz_values()
        line = lines.Line2D(x[:, xline], z[:, xline], color="yellow")
        ax.add_line(line)

    for ts in tsurfs:
        x, _, z = ts.get_xyz_values()
        line = lines.Line2D(x[:, xline], z[:, xline], color="green")
        ax.add_line(line)

    # Set the axis labels
    ax.set_xlabel("Trace")
    ax.set_ylabel("Z/TWT")

    # Set the title of the plot
    ax.set_title(title)
    ax = plt.gca()
    ax.invert_yaxis()
    # Show the plot
    plt.show()


@pytest.fixture(name="smallcube")
def fixture_smallcube():
    """Fixture for making a small synthetic test cube"""
    cube_values = np.zeros((3, 4, 101))
    cube_values[:, :, 44:50] = 2.0
    cube_values[:, :, 50:55] = 4.0
    cube_values[:, :, 55:60] = 5.0
    cube_values[:, :, 60:63] = 2.0
    cube_values[:, :, 63:66] = -2.0
    cube_values[:, :, 66:68] = -4.0
    cube_values[:, :, 68:70] = -1.0

    return xtgeo.Cube(
        ncol=3,
        nrow=4,
        nlay=101,
        xinc=1.0,
        yinc=1.0,
        zinc=1.0,
        values=cube_values,
        ilines=[3, 6, 9],
        xlines=[42, 40, 38, 36],
    )


@pytest.fixture(name="simplesurfs")
def fixture_simple_surfaces(smallcube):
    """Generate a few simple flat surfaces (time/depth pairs)."""

    surface_template = xtgeo.surface_from_cube(smallcube, value=0)

    d0 = surface_template.copy()
    d0.values = 0.0
    d1 = surface_template.copy()
    d1.values = 50.0
    d2 = surface_template.copy()
    d2.values = 75.0
    t0 = surface_template.copy()
    t0.values = 0.0
    t1 = surface_template.copy()
    t1.values = 43.0
    t2 = surface_template.copy()
    t2.values = 70.0

    return [d0, d1, d2], [t0, t1, t2]


def test_domainconversion_deprecated_arg_order(smallcube, simplesurfs):
    """Test deprecated argument order."""

    dlist, tlist = simplesurfs
    with pytest.raises(ValueError, match="the first argument was a Cube"):
        DomainConversion(smallcube, dlist, tlist)


def test_generate_simple_dconvert_model(simplesurfs):
    """Test creating a simple domain_conversion model."""

    dlist, tlist = simplesurfs
    dc = DomainConversion(dlist, tlist)
    assert dc is not None
    for velo in dc.velocity_surfaces():
        assert isinstance(velo, xtgeo.RegularSurface)
        logger.debug("Velo surface mean value: %s", velo.values.mean())

    # now depth convert time surfaces using the velocity cube
    new_dlist = dc.depth_convert_surfaces(tlist)

    # check that the depth converted (new) surface is ~identical to the input
    assert dlist[2].values.mean() == pytest.approx(new_dlist[2].values.mean(), rel=0.01)

    # time convert back
    new_tlist = dc.time_convert_surfaces(dlist)
    assert tlist[2].values.mean() == pytest.approx(new_tlist[2].values.mean(), rel=0.01)


def test_domainconvert_surfaces_outside(simplesurfs):
    """Convert the cube back and forth in time and depth."""

    dc = DomainConversion(*simplesurfs)

    another_surf = simplesurfs[1][0].copy()
    another_surf.values = 1000
    another_surf.xori = 1000  # move it outside the surface range

    with pytest.raises(ValueError, match="not fully inside the model area"):
        dc.depth_convert_surfaces([another_surf])


def test_generate_simple_velocube(smallcube, simplesurfs):
    """Test creating a simple velocity cube."""

    plot_section(smallcube, simplesurfs, title="Time domain")
    dlist, tlist = simplesurfs

    dc = DomainConversion(dlist, tlist)

    # None! creating the velocity is lazy, after depth conversion of a cube is asked for
    assert dc.average_velocity_cube_in_time is None

    # so now depth convert a cube...
    _ = dc.depth_convert_cube(smallcube)
    velocube = dc.average_velocity_cube_in_time
    assert velocube is not None

    assert velocube.ilines == smallcube.ilines
    assert velocube.xlines == smallcube.xlines

    plot_section(velocube, simplesurfs, title="Avg Velocity cube in T")


@pytest.mark.parametrize(
    "input, expected",
    [
        # [(None, None, None), (1.1, 0, 82.5)],  # TODO: Take a look at this
        [(1.1, 0.0, 100), (1.1, 0.0, 99.0)],
        [(1.5, 0.0, 100), (1.5, 0.0, 99.0)],
        [(1.5, 20.0, 100), (1.5, 19.5, 99.0)],
        [(3.3, 20.0, 100), (3.3, 19.8, 99.0)],
        [(0.1, 20.0, 100), (0.1, 20, 100.0)],
    ],
)
def test_proposing_zinc_etc_depthconvert(smallcube, simplesurfs, input, expected):
    """Test various proposal of zinc, zmax, zmin."""

    dc = DomainConversion(*simplesurfs)

    assert smallcube.zinc == 1.0

    zinc, zmin, zmax = input
    expected_zinc, expected_zmin, expected_zmax = expected

    depthcube = dc.depth_convert_cube(smallcube, zinc=zinc, zmin=zmin, zmax=zmax)
    assert depthcube.zinc == pytest.approx(expected_zinc)
    assert depthcube.zori == pytest.approx(expected_zmin)
    max = depthcube.zori + (depthcube.nlay - 1) * depthcube.zinc
    assert max == pytest.approx(expected_zmax)

    assert depthcube.ilines == [3, 6, 9]
    assert depthcube.xlines == [42, 40, 38, 36]


@pytest.mark.parametrize(
    "input, expected",
    [
        [(None, None, None), (0.9, 0, 76.5)],
        [(1.1, 0.0, 100), (1.1, 0.0, 99.0)],
        [(1.5, 0.0, 100), (1.5, 0.0, 99.0)],
        [(1.5, 20.0, 100), (1.5, 19.5, 99.0)],
        [(3.3, 20.0, 100), (3.3, 19.8, 99.0)],
        [(0.1, 20.0, 100), (0.1, 20, 100.0)],
    ],
)
def test_proposing_zinc_etc_timeconvert(smallcube, simplesurfs, input, expected):
    """Test various proposal of tinc, tmax, tmin."""

    dc = DomainConversion(*simplesurfs)

    assert smallcube.zinc == 1.0

    tinc, tmin, tmax = input
    expected_tinc, expected_tmin, expected_tmax = expected

    timecube = dc.time_convert_cube(smallcube, tinc=tinc, tmin=tmin, tmax=tmax)
    assert timecube.zinc == pytest.approx(expected_tinc)
    assert timecube.zori == pytest.approx(expected_tmin)
    max = timecube.zori + (timecube.nlay - 1) * timecube.zinc
    assert max == pytest.approx(expected_tmax)


def test_domainconvert_back_and_forth(smallcube, simplesurfs):
    """Convert the cube back and forth in time and depth."""

    dlist, tlist = simplesurfs

    dc = DomainConversion(dlist, tlist)

    new_depth_cube = dc.depth_convert_cube(smallcube, zinc=1, zmax=100, zmin=0)
    plot_section(smallcube, simplesurfs, title="Input cube in time domain")

    plot_section(new_depth_cube, simplesurfs, title="Depth converted cube")

    # now timeconvert the newcube
    new_time_cube = dc.time_convert_cube(new_depth_cube, tinc=1, tmax=100, tmin=0)
    plot_section(new_time_cube, simplesurfs, title="Time domain output after d2t")

    assert abs((smallcube.values - new_time_cube.values).mean()) < 0.01


def test_domainconvert_cube_outside(smallcube, simplesurfs):
    """Convert the cube back and forth in time and depth."""

    dc = DomainConversion(*simplesurfs)

    newcube = smallcube.copy()
    newcube.xori = 1000  # move it outside the surface range

    with pytest.raises(ValueError, match="not fully inside the model area."):
        dc.depth_convert_cube(newcube)
