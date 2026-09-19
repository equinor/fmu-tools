"""Generate ``sw_calc_geometry_grid.png`` for ``docs/sw_theory.rst``.

Illustrates, for a single grid cell whose top face straddles the free
fluid level (FFL), how each of xtgeo's three ``get_heights_above_ffl``
``method`` options (rows) differs, and how the resulting heights are
consumed either directly (``hmid``) or via integration (``hbot`` ->
``htop``) by :class:`fmu.tools.properties.SwFunction` (columns).

The per-method height computation mirrors xtgeo's C++ implementation in
``get_height_above_ffl`` (xtgeo/src/lib/src/grid3d/grid.cpp):

- ``cell_center_above_ffl``: average the 4 corners on each face first,
  then take ``ffl - avg`` and clip to >= 0.
- ``cell_corners_above_ffl``: use only the shallowest top corner and the
  deepest bottom corner (min/max of raw z), then clip to >= 0.
- ``truncated_cell_corners_above_ffl``: clip each of the 4 corners on a
  face to >= 0 individually, then average.

Run with ``python generate_sw_calc_geometry_grid.py`` (requires
matplotlib) to regenerate the PNG in place.
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np

# Corners of one wide, gently tilted cell whose top face straddles FFL
# (TL below FFL, TR above FFL) and whose bottom face is fully submerged.
TL = (0.0, -0.35)
TR = (4.2, 0.85)
BL = (0.3, -1.65)
BR = (4.5, -0.55)
FFL_Y = 0.0

TOP_CORNERS = [TL, TR]
BOT_CORNERS = [BL, BR]


def _raw_heights(corners):
    """height above FFL, uncapped, for each corner (bigger = shallower).

    ``y`` here is a plot elevation (increasing upward), so a corner above
    the FFL line has ``y > FFL_Y`` and a positive raw height.
    """
    return [y - FFL_Y for _, y in corners]


def cell_center_above_ffl():
    htop = max(np.mean([y for _, y in TOP_CORNERS]) - FFL_Y, 0.0)
    hbot = max(np.mean([y for _, y in BOT_CORNERS]) - FFL_Y, 0.0)
    return htop, hbot


def cell_corners_above_ffl():
    htop = max(max(_raw_heights(TOP_CORNERS)), 0.0)
    hbot = max(min(_raw_heights(BOT_CORNERS)), 0.0)
    return htop, hbot


def truncated_cell_corners_above_ffl():
    htop = np.mean([max(h, 0.0) for h in _raw_heights(TOP_CORNERS)])
    hbot = np.mean([max(h, 0.0) for h in _raw_heights(BOT_CORNERS)])
    return htop, hbot


METHODS = [
    ("cell_center\nabove_ffl", cell_center_above_ffl),
    ("cell_corners\nabove_ffl", cell_corners_above_ffl),
    ("truncated_cell_corners\nabove_ffl", truncated_cell_corners_above_ffl),
]

CELL_COLOR = "#a6cee3"
FILL_COLOR = "#fdae61"
FFL_COLOR = "#1f4e79"
POINT_COLOR = "#d7301f"


def _draw_cell(ax):
    poly = plt.Polygon(
        [TL, TR, BR, BL],
        closed=True,
        facecolor=CELL_COLOR,
        edgecolor="black",
        linewidth=1.5,
        zorder=2,
    )
    ax.add_patch(poly)
    xs, ys = zip(*[TL, TR, BR, BL])
    ax.scatter(xs, ys, color="#3182bd", s=35, zorder=4)
    ax.axhline(FFL_Y, color=FFL_COLOR, linewidth=2, zorder=3)


def _fill_above_ffl(ax):
    """Shade the part of the top face that lies above the FFL line."""
    tx, ty = TL
    tx2, ty2 = TR
    if ty >= FFL_Y and ty2 >= FFL_Y:
        pts = [TL, TR]
    else:
        # linear interpolation of the top edge crossing y = FFL_Y
        frac = (FFL_Y - ty) / (ty2 - ty)
        xc = tx + frac * (tx2 - tx)
        if ty < FFL_Y:
            pts = [(xc, FFL_Y), TR]
        else:
            pts = [TL, (xc, FFL_Y)]
    poly_pts = pts + [(x, FFL_Y) for x, _ in reversed(pts)]
    ax.add_patch(
        plt.Polygon(poly_pts, closed=True, facecolor=FILL_COLOR, alpha=0.85, zorder=2.5)
    )


def _setup_axes(ax):
    ax.set_xlim(-0.6, 5.1)
    ax.set_ylim(-2.0, 1.3)
    ax.set_aspect("equal")
    ax.axis("off")


def _direct_panel(ax, htop, hbot):
    _draw_cell(ax)
    _fill_above_ffl(ax)
    hmid = 0.5 * (htop + hbot)
    ymid = FFL_Y + hmid
    ax.plot([TL[0], TR[0]], [ymid, ymid], "--", color=POINT_COLOR, linewidth=1, zorder=5)
    ax.scatter([2.1], [ymid], color=POINT_COLOR, s=90, zorder=6)
    ax.text(
        2.1,
        ymid + 0.28,
        rf"$h_{{mid}}$ = {hmid:.2f}",
        color=POINT_COLOR,
        fontsize=12,
        fontweight="bold",
        ha="center",
    )


def _integration_panel(ax, htop, hbot):
    _draw_cell(ax)
    _fill_above_ffl(ax)
    ytop = FFL_Y + htop
    ybot = FFL_Y + hbot
    xspan = (3.4, 4.9)
    ax.plot(xspan, [ytop, ytop], "--", color=POINT_COLOR, linewidth=1, zorder=5)
    ax.plot(xspan, [ybot, ybot], "--", color=POINT_COLOR, linewidth=1, zorder=5)
    if abs(ytop - ybot) > 0.03:
        ax.annotate(
            "",
            xy=(3.6, ytop),
            xytext=(3.6, ybot),
            arrowprops={"arrowstyle": "<->", "color": POINT_COLOR, "linewidth": 2},
            zorder=6,
        )
    else:
        ax.scatter([3.6], [ytop], marker="x", color=POINT_COLOR, s=90, zorder=6)
    ax.text(
        3.55,
        max(ytop, ybot) + 0.32,
        rf"$h_{{top}}$={htop:.2f}   $h_{{bot}}$={hbot:.2f}",
        color=POINT_COLOR,
        fontsize=12,
        fontweight="bold",
        ha="center",
    )


def main():
    fig, axes = plt.subplots(3, 2, figsize=(13, 12))
    fig.suptitle(
        "Direct calculation vs. integration for each height-above-FFL method,\n"
        "for a cell whose top face straddles the free fluid level",
        fontsize=15,
    )

    axes[0, 0].set_title("Direct calculation", fontsize=16, fontweight="bold", pad=20)
    axes[0, 1].set_title("Integration", fontsize=16, fontweight="bold", pad=20)

    fig.subplots_adjust(left=0.22, right=0.98, top=0.86, bottom=0.08, hspace=0.35)
    fig.canvas.draw()

    for row, (label, method_fn) in enumerate(METHODS):
        htop, hbot = method_fn()
        ax_direct, ax_integ = axes[row, 0], axes[row, 1]

        _setup_axes(ax_direct)
        _setup_axes(ax_integ)
        _direct_panel(ax_direct, htop, hbot)
        _integration_panel(ax_integ, htop, hbot)

        ax_direct.text(
            -0.1,
            0.5,
            label,
            transform=ax_direct.transAxes,
            fontsize=13,
            fontweight="bold",
            ha="right",
            va="center",
            clip_on=False,
        )

    legend_elements = [
        plt.Line2D([0], [0], color=FFL_COLOR, lw=2, label="FFL (free fluid level)"),
        plt.Line2D(
            [0],
            [0],
            marker="o",
            color="w",
            markerfacecolor="#3182bd",
            markersize=8,
            label="cell corner",
        ),
        plt.Line2D(
            [0],
            [0],
            marker="o",
            color="w",
            markerfacecolor=POINT_COLOR,
            markersize=10,
            label="direct calculation point ($h_{mid}$)",
        ),
        plt.Line2D(
            [0], [0], color=POINT_COLOR, lw=2, label=r"integration span ($h_{bot} \to h_{top}$)"
        ),
    ]
    fig.legend(
        handles=legend_elements,
        loc="lower center",
        ncol=4,
        frameon=False,
        fontsize=11,
        bbox_to_anchor=(0.5, 0.0),
    )

    fig.savefig("sw_calc_geometry_grid.png", dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    main()
