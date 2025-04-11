from typing import Any

DEBUG_OFF = 0
DEBUG_ON = 1
DEBUG_VERBOSE = 2
DEBUG_VERY_VERBOSE = 3


class ZoneMapping:
    """
    Keep info about available zones in modelling grid,
    its zone numbers in the zone parameter and corresponding zone names.
    The grid object contains info about zone names for the grid and
    number of layers per zone as the most important info in this class.
    The zone parameter (3D parameter with zone number per grid cell) contains
    a table with corresponding zone name and zone number.
    """

    def __init__(
        self,
        grid_model: Any,
        grid: Any,
        real_number: int = 0,
        fmu_mode: bool = False,
        debug_level: int = DEBUG_OFF,
    ):
        assert grid_model
        assert grid
        self.grid_model = grid_model
        self.grid = grid
        self.real_number = real_number

        # Key is zone index in the zones in the grid
        self.grid_zone_dict: dict[int, dict] = {}

        # Key is zone_number and value is zone name
        self.zone_code_names: dict[int, str] = {}

        # Key is zone_number
        self.grid_zone_index_dict: dict[int, int] = {}

        if not fmu_mode:
            # The zone parameter
            zone_param = get_zone_parameter(
                self.grid_model,
                realization_number=self.real_number,
                debug_level=debug_level,
            )
            self.zone_code_names = zone_param.code_names
            self.zone_param_name = zone_param.name
        else:
            self.zone_code_names = {1: "Zone1"}
            self.zone_param_name = "Zone1"

        indexer = self.grid.simbox_indexer
        zonation = indexer.zonation
        if debug_level >= DEBUG_VERY_VERBOSE:
            print(f"--- Zone parameter with zone_code_names: {self.zone_code_names}")
            print(f"--- Grid with zone names: {self.grid.zone_names}")

        zone_names_from_grid = self.grid.zone_names
        for zone_index in zonation:
            self.grid_zone_dict[zone_index] = {}

        assert len(zone_names_from_grid) == len(zonation)

        # same index in zonation and in zone_names corresponds to the same zone
        for zone_index in zonation:
            zone_name = zone_names_from_grid[zone_index]
            self.grid_zone_dict[zone_index]["name_from_grid"] = zone_name

            layer_ranges = zonation[zone_index]
            assert (
                len(layer_ranges) == 1
            )  # No repeated layer numbering for simbox indexer
            layer_range = layer_ranges[0]
            start = layer_range[0]
            end = layer_range[-1]
            number_of_layers = end + 1 - start
            self.grid_zone_dict[zone_index]["nlayers"] = number_of_layers
            self.grid_zone_dict[zone_index]["start_layer"] = start
            self.grid_zone_dict[zone_index]["end_layer"] = end

            zone_number = self.get_zone_number(zone_name)
            self.grid_zone_dict[zone_index]["zone_number"] = zone_number
            self.grid_zone_index_dict[zone_number] = zone_index

    def validate_zone_number_for_grid(self, zone_number: int) -> None:
        if zone_number not in self.grid_zone_index_dict:
            if zone_number in self.zone_code_names:
                raise ValueError(
                    f"Zone name: {self.zone_code_names[zone_number]} "
                    f"with zone code: {zone_number} in zone parameter "
                    "does not exist in the grid."
                )
            raise ValueError(
                f"Zone number: {zone_number} is not found in zone parameter."
            )

    def get_number_of_zones_in_grid(self) -> int:
        return len(self.grid.simbox_indexer.zonation)

    def get_zone_names_from_grid(self) -> list[str]:
        """
        Zone names got from the grid object.
        """
        return self.grid.zone_names

    def get_zone_names_from_param(self) -> dict[int, str]:
        """
        Zone names corresponding to the grid zones, but the names are
        got from the zone parameter.
        """
        zone_name_dict = {}
        nzones = self.get_number_of_zones_in_grid()
        for zone_index in range(nzones):
            zone_number = self.get_zone_number_for_zone_index(zone_index)
            zone_name_dict[zone_number] = self.zone_code_names[zone_number]
        return zone_name_dict

    def get_zone_numbers(self) -> list[int]:
        return list(self.zone_code_names.keys())

    def get_zone_numbers_in_grid(self) -> list[int]:
        nzones = self.get_number_of_zones_in_grid()
        zone_numbers = []
        for zone_index in range(nzones):
            zone_numbers.append(self.grid_zone_dict[zone_index]["zone_number"])
        return zone_numbers

    def get_zone_number(self, zone_name: str) -> int:
        # Unique zone name for each zone code
        for code, name in self.zone_code_names.items():
            if zone_name == name:
                return code
        raise ValueError(
            f"Unknown zone name: {zone_name}. "
            f"Check that zone names in grid and zone parameter {self.zone_param_name} "
            "are consistent."
        )

    def get_zone_name_for_zone_number(self, zone_number: int) -> str:
        return self.zone_code_names[zone_number]

    def get_zone_name_for_zone_index(
        self, zone_index: int, zone_name_from_param: bool = True
    ) -> str:
        """
        Return zone name in zone_code table in zone parameter or
        alternatively zone name from grid.
        """
        if not zone_name_from_param:
            # Zone name from grid
            return self.grid.zone_names[zone_index]
        # zone name from param
        zone_number = self.get_zone_number_for_zone_index(zone_index)
        return self.zone_code_names[zone_number]

    def get_zone_number_for_zone_index(self, zone_index: int) -> int:
        return self.grid_zone_dict[zone_index]["zone_number"]

    def get_zone_index_for_zone_number(self, zone_number: int) -> int:
        self.validate_zone_number_for_grid(zone_number)
        return self.grid_zone_index_dict[zone_number]

    def is_zone_number_defined(self, zone_number: int) -> bool:
        zone_numbers_in_grid = self.get_zone_numbers_in_grid()
        return zone_number in zone_numbers_in_grid

    def number_of_layers_for_zone_number(self, zone_number: int) -> int:
        self.validate_zone_number_for_grid(zone_number)
        index = self.grid_zone_index_dict[zone_number]
        return self.grid_zone_dict[index]["nlayers"]

    def number_of_layers_for_zone_index(self, zone_index: int):
        return self.grid_zone_dict[zone_index]["nlayers"]

    def get_start_end_layer_for_zone_number(self, zone_number: int) -> tuple[int, int]:
        self.validate_zone_number_for_grid(zone_number)
        index = self.grid_zone_index_dict[zone_number]
        return self.grid_zone_dict[index]["start_layer"], self.grid_zone_dict[index][
            "end_layer"
        ]

    def get_start_end_layer_for_zone_index(self, zone_index: int) -> tuple[int, int]:
        return self.grid_zone_dict[zone_index]["start_layer"], self.grid_zone_dict[
            zone_index
        ]["end_layer"]

    def get_number_of_layers_per_zone(self) -> list[int]:
        nzones = self.get_number_of_zones_in_grid()
        number_of_layers_per_zone = []
        for zone_index in range(nzones):
            number_of_layers_per_zone.append(
                self.number_of_layers_for_zone_index(zone_index)
            )
        return number_of_layers_per_zone


def get_zone_parameter(
    grid_model: Any,
    name: str = "Zone",
    realization_number: int = 0,
    debug_level: int = DEBUG_OFF,
):
    """Description:
    Return zone parameter for given grid model.
    """
    properties = grid_model.properties
    if name in properties:
        zone_parameter = properties[name]
        if debug_level >= DEBUG_VERY_VERBOSE:
            print(f"--- Found existing zone parameter with name {zone_parameter.name}")

        if zone_parameter.is_empty(realisation=realization_number):
            raise ValueError(f"Zone parameter: {zone_parameter.name} is empty.")
    else:
        raise ValueError(f"Zone parameter {name} does not exists.")
    return zone_parameter


def get_zone_mapping(
    project: Any, grid_model_name: str, debug_level: int = DEBUG_OFF
) -> ZoneMapping:
    grid_model = project.grid_models[grid_model_name]
    grid = grid_model.get_grid(project.current_realisation)
    return ZoneMapping(
        grid_model,
        grid,
        real_number=project.current_realisation,
        debug_level=debug_level,
    )
