"""
Extract simbox information necessary to be able to both create a box grid
with the simbox size, resolution and orientation and as input to calculate
cell center position of each grid cell in simbox grid. Note, only that depth
of the simbox is irrelevant where this is meant to be used in distance-based
localization and therefore
not saved.
"""
# NOTE: A bug in RMS14.2.2 cause the origin to be wrong.
# But RMS15.0.1.0 and newer works.

from typing import Any

import yaml


def get_simbox_param(project: Any, grid_model_name: str, zone_index: int) -> dict:
    if grid_model_name in project.grid_models:
        grid_model = project.grid_models[grid_model_name]
        grid3D = grid_model.get_grid()
        cell_increments = grid3D.simbox.cell_increments
        simbox_indexer = grid3D.simbox_indexer
        ijk_handedness = simbox_indexer.ijk_handedness
        zonation = simbox_indexer.zonation
        layer_range = list(zonation[zone_index][0])
        nlayers = len(layer_range)
        dimensions = simbox_indexer.dimensions
        zone_name = grid3D.zone_names[zone_index]
        simbox = {
            "name": str(zone_name),
            "origin": [float(grid3D.origin[0]), float(grid3D.origin[1])],
            "rotation": float(grid3D.rotation),
        }
        simbox["size"] = [
            float(cell_increments["x_increment"] * dimensions[0]),
            float(cell_increments["y_increment"] * dimensions[1]),
            float(cell_increments["z_increments"][zone_index] * nlayers),
        ]
        simbox["dimensions"] = [
            int(dimensions[0]),
            int(dimensions[1]),
            int(nlayers),
        ]
        simbox["handedness"] = str(ijk_handedness)
        return simbox
    raise ValueError(f"Unknown grid model {grid_model_name}")


def write_simbox(filename: str, simbox: dict) -> None:
    simbox_data_yml = yaml.dump(simbox, default_flow_style=False, sort_keys=False)
    print(f"Write file:  {filename}")
    with open(filename, "w") as file:
        file.write(simbox_data_yml)
        file.write("\n")
    print(
        "NOTE: If the RMS simulation box data written is to be used to\n"
        "      define ERTBOX parameters for use in ERT update of field parameters\n"
        "      remember that geomodel zones with top or base conform gridding\n"
        "      may need more grid layers if the grid vary from realization to\n"
        "      realization. For zones in geogrid with proportional gridding,\n"
        "      it is ok to use the data from RMS simulation box as data for ERTBOX\n"
        "      for the zone in ERT."
    )


# if __name__ == "__main__":
#    grid_model_names = ["Geogrid_Valysar", "Geogrid_Therys", "Geogrid_Volon"]
#    for grid_model_name in grid_model_names:
#        filename = "tmp_simbox_" + grid_model_name + ".yml"
#        zone_index = 0
#        simbox = get_simbox_param(project, grid_model_name, zone_index)
#        write_simbox(filename, simbox)
