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
        ncol=3, nrow=4, nlay=101, xinc=1.0, yinc=1.0, zinc=1.0, values=cube_values
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


def test_generate_simple_velocube(smallcube, simplesurfs):
    """Test creating a simple velocity cube."""

    print(smallcube.values)
    plot_section(smallcube, simplesurfs, title="Time domain")
    dlist, tlist = simplesurfs

    dc = DomainConversion(smallcube, dlist, tlist)

    velocube = dc.average_velocity_cube_in_time
    plot_section(velocube, simplesurfs, title="Avg Velocity cube in T")

    # now depth convert time surfaces using the velocity cube
    new_dlist = dc.depth_convert_surfaces(tlist)

    # check that the depth converted (new) surface is ~identical to the input
    assert dlist[2].values.mean() == pytest.approx(new_dlist[2].values.mean(), rel=0.01)


def test_generate_simple_velocube_cropped(smallcube, simplesurfs):
    """Test creating a simple velocity cube, crop it, and also remove MSL from surfs."""

    cropped = smallcube.copy()

    cropped.do_cropping((0, 0), (0, 0), (22, 0))

    dlist, tlist = simplesurfs

    # now skip MSL surface
    dlist = dlist[1:]
    tlist = tlist[1:]

    dc = DomainConversion(cropped, dlist, tlist)

    # now depth convert time surfaces using the velocity cube
    new_dlist = dc.depth_convert_surfaces(tlist)

    # check that the depth converted (new) surface is ~identical to the input
    assert dlist[1].values.mean() == pytest.approx(new_dlist[1].values.mean(), rel=0.01)


def test_dconvert_seismic_2coarser(smallcube, simplesurfs):
    """Test creating a simple velocity cube."""

    dlist, tlist = simplesurfs
    plot_section(smallcube, simplesurfs, title="Time domain")

    dc = DomainConversion(smallcube, dlist, tlist)

    cube_d = dc.depth_convert_cube(smallcube, zinc=2, maxdepth=100)
    plot_section(cube_d, simplesurfs, title="Depth domain, after conversion")

    assert cube_d.values[0, 0, 30] == 4.0

    # crop the result instance
    cube_d.do_cropping(icols=(0, 0), jrows=(0, 0), klays=(25, 2))


def test_generate_simple_slownesscube(smallcube, simplesurfs):
    """Test creating a simple slowness cube."""

    plot_section(smallcube, simplesurfs, title="Time domain")
    dlist, tlist = simplesurfs

    dc = DomainConversion(smallcube, dlist, tlist, time_to_depth=False)

    slowcube = dc.average_slowness_cube_in_depth
    plot_section(slowcube, simplesurfs, title="Avg Velocity cube in T")

    # now depth convert time surfaces using the velocity cube
    new_tlist = dc.time_convert_surfaces(dlist)

    # check that the time converted (new) surface is ~identical to the input
    assert tlist[2].values.mean() == pytest.approx(new_tlist[2].values.mean(), rel=0.01)


def test_depth_time_convert_seismic(smallcube, simplesurfs):
    """First depth convert, then time convert a cube."""

    dlist, tlist = simplesurfs

    plot_section(smallcube, simplesurfs, title="Time domain input")
    dc_time2depth = DomainConversion(smallcube, dlist, tlist)

    cube_d = dc_time2depth.depth_convert_cube(smallcube)

    dc_depth2time = DomainConversion(cube_d, dlist, tlist, time_to_depth=False)

    cube_t = dc_depth2time.time_convert_cube(cube_d)
    plot_section(cube_t, simplesurfs, title="Time domain output after t2d and d2t")

    print(smallcube.values.mean())
    print(cube_t.values.mean())
    assert smallcube.values.mean() == pytest.approx(cube_t.values.mean(), abs=0.01)

    indices = ((1, 1, 47), (1, 1, 70))

    for inx in indices:
        assert smallcube.values[inx] == cube_t.values[inx]

    np.testing.assert_allclose(
        smallcube.values[1, 1, :], cube_t.values[1, 1, :], atol=1, rtol=0.5
    )
    diff = smallcube.values[1, 1, :] - cube_t.values[1, 1, :]
    assert abs(diff.mean()) < 0.01


def test_depth_time_convert_seismic_cropped_template(
    smallcube: xtgeo.Cube, simplesurfs
):
    """Using a truncated template cube (not starting from Z 0.0)"""

    dlist, tlist = simplesurfs

    cropped = smallcube.copy()
    cropped.do_cropping((0, 0), (0, 0), (20, 0))
    dc_time2depth_cropped = DomainConversion(cropped, dlist, tlist)
    new_tmpl = dc_time2depth_cropped.cube_template_applied
    new_tmpl.resample(cropped)  # for visual QC in plot_section below

    plot_section(
        new_tmpl,
        simplesurfs,
        title="Time domain input",
        limits_from=smallcube,
    )

    assert new_tmpl.dimensions == smallcube.dimensions
    print(new_tmpl)
    print(smallcube)
    print(cropped)

    cube_d = dc_time2depth_cropped.depth_convert_cube(cropped)
    print(cube_d)

    dc_depth2time_cropped = DomainConversion(cube_d, dlist, tlist, time_to_depth=False)

    cube_t = dc_depth2time_cropped.time_convert_cube(cube_d)
    plot_section(cube_t, simplesurfs, title="Time domain output after t2d and d2t")

    print(smallcube.values.mean())
    print(cube_t.values.mean())
    assert smallcube.values.mean() == pytest.approx(cube_t.values.mean(), abs=0.01)

    indices = ((1, 1, 47), (1, 1, 70))

    for inx in indices:
        assert smallcube.values[inx] == cube_t.values[inx]

    np.testing.assert_allclose(
        smallcube.values[1, 1, :], cube_t.values[1, 1, :], atol=1, rtol=0.5
    )
    diff = smallcube.values[1, 1, :] - cube_t.values[1, 1, :]
    assert abs(diff.mean()) < 0.01
