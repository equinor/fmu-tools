"""Private class in qcproperties"""

from fmu.tools._common import _QCCommon

QCC = _QCCommon()


class ConfigParser:
    """
    Class for parsing and preparing the input data for extracting statistics
    with QCProperties. The input data is formatted and grouped into relevant
    attributes based on where it will be utilized.
    """

    def __init__(
        self,
        data: dict,
    ):
        QCC.verbosity = data.get("verbosity", 0)

        if "csvfile" in data:
            raise KeyError(
                "Use of 'csvfile' keyword in data is deprecated. "
                "To output a csv-file use the to_csv method on "
                "the QCProperties() instance instead!"
            )

        self._aggregation_controls: dict = {
            "properties": [],
            "selectors": [],
            "weights": {},
        }

        self._prop2df_controls: dict = {
            "unique_parameters": [],
            "properties_input_names": [],
            "selectors_input_names": [],
            "filters": {},
            "name_mapping": {},
            "usercodes": {},
        }

        self._data_loading_input: dict = {"pfiles": {}, "pdates": {}}

        # set data loading input
        for item in ["grid", "wells", "bwells", "path", "verbosity"]:
            if item in data:
                self._data_loading_input[item] = data[item]

        # set aggregation controls and parameter data
        self._parse_properties(data["properties"])
        self._parse_selectors(data.get("selectors", {}))
        self._parse_filters(data.get("filters", {}))
        self._aggregation_controls["selector_combos"] = data.get(
            "selector_combos", True
        )
        self._aggregation_controls["output_percentage"] = data.get(
            "output_percentage", False
        )
        self._aggregation_controls["verbosity"] = QCC.verbosity

    # ==================================================================================
    # Properties
    # ==================================================================================

    @property
    def data_loading_input(self) -> dict:
        """Attribute to use for loading data to XTGeo"""
        return self._data_loading_input

    @property
    def aggregation_controls(self) -> dict:
        """Attribute to use for statisticts aggregation"""
        return self._aggregation_controls

    @property
    def prop2df_controls(self) -> dict:
        """Attribute to use for creating dataframe from properties"""
        return self._prop2df_controls

    # ==================================================================================
    # Hidden class methods
    # ==================================================================================

    def _parse_properties(self, properties):
        """Add property data to relevant attributes"""

        if isinstance(properties, list):
            properties = {param: {"name": param} for param in properties}

        for column_name, values in properties.items():
            name = values["name"]
            self._aggregation_controls["properties"].append(column_name)
            self._prop2df_controls["properties_input_names"].append(name)
            self._prop2df_controls["name_mapping"][name] = column_name
            self._add_to_parameters(name)

            if "weight" in values:
                self._aggregation_controls["weights"][column_name] = values["weight"]
                self._add_to_parameters(values["weight"])
            if "range" in values:
                self._prop2df_controls["filters"][name] = {"range": values["range"]}
            if "pfile" in values:
                self._data_loading_input["pfiles"][name] = values["pfile"]

        QCC.print_debug(f"properties: {properties}")

    def _parse_selectors(self, selectors):
        """Add selector data to relevant attributes"""

        if isinstance(selectors, list):
            selectors = {param: {"name": param} for param in selectors}

        for column_name, values in selectors.items():
            name = values["name"]
            self._aggregation_controls["selectors"].append(column_name)
            self._prop2df_controls["selectors_input_names"].append(name)
            self._prop2df_controls["name_mapping"][name] = column_name
            self._add_to_parameters(name)

            if "include" in values and "exclude" in values:
                raise ValueError("can't both include and exclude values in filtering")
            if "include" in values:
                self._prop2df_controls["filters"][name] = {"include": values["include"]}
            if "exclude" in values:
                self._prop2df_controls["filters"][name] = {"exclude": values["exclude"]}
            if "codes" in values:
                self._prop2df_controls["usercodes"][name] = values["codes"]
            if "pfile" in values:
                self._data_loading_input["pfiles"][name] = values["pfile"]

        QCC.print_debug(f"selectors: {selectors}")

    def _parse_filters(self, filters):
        """Add additional filters to relevant attributes"""
        for name, values in filters.items():
            self._add_to_parameters(name)

            if "pfile" in values:
                self._data_loading_input["pfiles"][name] = values["pfile"]

            # support using a selector prop as filter. If the selctor
            # has filters specified in its values, they will be ignored
            if name in self._prop2df_controls["filters"]:
                QCC.give_warn(
                    f"Filters for {name} found both in 'filters' and 'selectors' "
                    "or 'properties'. The filter on the selector/property is ignored."
                )
            self._prop2df_controls["filters"][name] = values

        # Filter format check
        for values in self._prop2df_controls["filters"].values():
            if "include" in values:
                if isinstance(values["include"], str):
                    values["include"] = [values["include"]]
                if not all(isinstance(item, str) for item in values["include"]):
                    values["include"] = [str(item) for item in values["include"]]

            if "exclude" in values:
                if isinstance(values["exclude"], str):
                    values["exclude"] = [values["exclude"]]
                if not all(isinstance(item, str) for item in values["exclude"]):
                    values["exclude"] = [str(item) for item in values["exclude"]]

            if "range" in values and not (
                isinstance(values["range"], list) and len(values["range"]) == 2
            ):
                raise TypeError("Filter range must be input as list with two values")

        QCC.print_debug(f"Filters: {self._prop2df_controls['filters']}")

    def _add_to_parameters(self, param):
        """Add parameter to list of unique parameters"""
        if param not in self._prop2df_controls["unique_parameters"]:
            self._prop2df_controls["unique_parameters"].append(param)
