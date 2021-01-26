""" Private class in qcproperties """

from typing import Union
from fmu.tools._common import _QCCommon

QCC = _QCCommon()


class PropStatParameterData:
    """Class for preparing the input parameter data for use with a PropStat()
    instance. Initializing this class will combine and group the input data
    into different class attributes.

    Args:
        properties (dict or list):
            Properties to compute statistics for. Can be given as list or as dictionary.
            If dictionary the key will be the column name in the output dataframe, and
            the value will be a dictionary with valid options:
                "name" (str or path): the actual name (or path) of the parameter / log.
                "weight" (str or path): a weight parameter (name or path if outside RMS)

        selectors (dict or list):
            Selectors are discrete properties/logs e.g. Zone. that are used to extract
            statistics for groups of the data. Can be given as list or as dictionary.
            If dictionary the key will be the column name in the output dataframe, and
            the value will be a dictionary with valid options:
                "name" (str or path): the actual name (or path) of the property / log.
                "include" or "exclude" (list): list of values to include/exclude
                "codes" (dict): a dictionary of codenames to update existing codenames.

        filters (dict):
            Additional filters, only discrete parameters are supported.
            The key is the name (or path) to the filter parameter / log, and the
            value is a dictionary with valid options:
                "include" or "exclude" (list): list of values to include/exclude

    Example::

            properties = {"PORO": {"name": "PHIT", "weight": "Total_Bulk"}},
            selectors = {
                "ZONE": {
                    "name": "Regions",
                    "exclude": ["Surroundings"],
                    "codes": {1: "East", 2: "North"},
                }
            },
            filters = {"Fluid": {"include": ["oil", "gas"]}}
    """

    def __init__(
        self,
        properties: Union[dict, list],
        selectors: Union[dict, list] = None,
        filters: dict = None,
        verbosity: int = None,
    ):

        self._params = []
        self._disc_params = []
        self._filters = {}
        self._codenames = {}
        self._properties = {}
        self._selectors = {}
        self._weights = {}

        QCC.verbosity = verbosity

        # adjust format of properties and selectors if input as list
        self._properties, self._selectors = self._input_conversion(
            properties, selectors
        )
        # combine data and set different instance attributes
        self._combine_data(filters)

        self._filter_values_to_string()

    @property
    def properties(self):
        """Attribute containing all properties"""
        return self._properties

    @property
    def selectors(self):
        """Attribute containing all selector properties"""
        return self._selectors

    @property
    def params(self):
        """Data attribute containing all unique parameters collected from the input"""
        return self._params

    @property
    def disc_params(self):
        """Discrete Parameters attribute"""
        return self._disc_params

    @disc_params.setter
    def disc_params(self, newdata):
        """Update the discrete parameter list."""
        self._disc_params = newdata

    @property
    def filters(self):
        """Filter attribute"""
        return self._filters

    @property
    def codenames(self):
        """Codenames attribute used to update codenames for dicrete parameters"""
        return self._codenames

    @property
    def weights(self):
        """Weight attribute"""
        return self._weights

    # ==================================================================================
    # Hidden class methods
    # ==================================================================================

    @staticmethod
    def _input_conversion(properties, selectors):
        """
        Check if property and selector data are given as list and
        return desired input dict format for _PropStatParameterData
        """
        properties_dict = {}
        selectors_dict = {}

        if isinstance(properties, list):
            for prop in properties:
                properties_dict[prop] = {"name": prop}
            properties = properties_dict

        if isinstance(selectors, list):
            for selctor in selectors:
                selectors_dict[selctor] = {"name": selctor}
            selectors = selectors_dict

        return properties, selectors

    def _add_properties_data(self):
        """ Add properties data to relevant attributes """
        for prop, values in self._properties.items():
            self._params.append(values["name"])

            if "weight" in values:
                self._weights[prop] = values["weight"]
                if values["weight"] not in self._params:
                    self._params.append(values["weight"])

    def _add_selector_data(self):
        """ Add selector data to relevant attributes """
        for values in self._selectors.values():
            prop = values["name"]
            if prop not in self._params:
                self._params.append(prop)
            if prop not in self._disc_params:
                self._disc_params.append(prop)

            if "include" in values and "exclude" in values:
                raise ValueError("can't both include and exclude values in filtering")

            if "include" in values:
                self._filters[prop] = {"include": values.get("include")}
            if "exclude" in values:
                self._filters[prop] = {"exclude": values.get("exclude")}

            if "codes" in values:
                self._codenames[prop] = values["codes"]

    def _add_filters(self, filters):
        """ Add additional filters to relevant attributes """
        for prop, values in filters.items():
            if prop not in self._params:
                self._params.append(prop)
                self._filters[prop] = values
                self._disc_params.append(prop)

            # support using a selector prop as filter. If the selctor
            # has filters specified in its values, they will be ignored
            if any(x["name"] == prop for x in self._selectors.values()):
                if prop in self._filters:
                    QCC.give_warn(
                        f"Filters for {prop} found both in 'filters' and 'selectors'. "
                        "The filter defined on the selector is ignored."
                    )
                self._filters[prop] = values

    def _combine_data(self, filters):
        """ create combined lists of all data sources"""

        self._add_properties_data()

        if self._selectors:
            self._add_selector_data()

        if filters is not None:
            self._add_filters(filters)

        QCC.print_debug(f"All Properties: {self.properties}")
        QCC.print_debug(f"All Selectors: {self.selectors}")
        QCC.print_debug(f"All Filters: {self.filters}")

    def _filter_values_to_string(self):
        """
        String convertion of filter list values to support using integers as input.
        Useful for properties with code values as code names.
        """
        for prop, values in self._filters.items():
            if "include" in values:
                self._filters[prop] = {"include": [str(x) for x in values["include"]]}
            if "exclude" in values:
                self._filters[prop] = {"exclude": [str(x) for x in values["exclude"]]}
