import numpy as np
import xtgeo
from scipy.spatial import cKDTree


def resample_surf_to_template(
    surf: xtgeo.RegularSurface, template: xtgeo.RegularSurface
) -> xtgeo.RegularSurface:
    """Resample a surface to match a template."""
    resampled_surf = template.copy()
    resampled_surf.resample(surf)
    return resampled_surf


def nearest_node_gridding(
    surf: xtgeo.RegularSurface,
    points: xtgeo.Points,
    distance_threshold: float | None = None,
) -> xtgeo.RegularSurface:
    """
    Perform nearest-node gridding on a surface using the given points.
    A distance_threshold can be used to mask nodes that are too further away
    than the threshold from the input points.
    """
    surf.gridding(points, method="nearest")

    if distance_threshold:
        distant_nodes = find_surface_nodes_away_from_points(
            surf, points, distance_threshold
        )
        surf.values = np.ma.masked_where(distant_nodes, surf.values)

    return surf


def find_surface_nodes_away_from_points(
    surf: xtgeo.RegularSurface, points: xtgeo.Points, threshold: float
) -> np.ndarray:
    """
    Flag surface nodes located further away than a distance threshold
    from the input points.
    """
    x, y, _z = surf.get_xyz_values()
    point_df = points.get_dataframe(copy=False)
    surface_nodes = np.column_stack((x.flatten(), y.flatten()))
    point_set = point_df[["X_UTME", "Y_UTMN"]].values

    tree = cKDTree(point_set)
    distances, _ = tree.query(surface_nodes, k=1)
    return (distances > threshold).reshape(surf.values.shape)
