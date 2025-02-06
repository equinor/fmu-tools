# Define a file format for ERT containing scaling factors for each
# pair of observations and field parameter value.
import json

scaling_factor_dict = {
    "field": "aps_Valysar_GRF1",
    "ert_id_list":
        [
            {
                "ert_id_name": "WGOR_A4_2",
                "scaling":
                    [
                        {
                            "index": (10, 55),
                            "value": 0.776,
                        },
                        {
                            "index": (11, 55),
                            "value": 0.7,
                        },
                        {
                           "index": (10, 56),
                            "value": 0.8,
                        },
                        {
                            "index": (11, 56),
                            "value": 0.6,
                        },
                    ]
            },
            {
                "ert_id_name": "WGOR_A4_1",
                "scaling":
                    [
                        {
                            "index": (10, 55),
                            "value": 0.776,
                        },
                        {
                            "index": (11, 55),
                            "value": 0.7,
                        },
                        {
                           "index": (10, 56),
                            "value": 0.8,
                        },
                        {
                            "index": (11, 56),
                            "value": 0.6,
                        },
                    ]
            },
        ]
    }

# Alternative where all combinations of (field_name, ert_id) specified has the same scaling factor
scaling_factor_group_dict = [
    {
        "fields": [ "aps_Valysar_GRF1","aps_Valysar_GRF2","aps_Valysar_GRF3"],
        "ert_id_list": ["WGOR_A4_1", "WGOR_A4_2", "WGOR_A4_3"],
        "scaling":
            [
                {
                    "index": (10, 55),
                    "value": 0.776,
                },
                {
                    "index": (11, 55),
                    "value": 0.7,
                },
                {
                    "index": (10, 56),
                    "value": 0.8,
                },
                {
                    "index": (11, 56),
                    "value": 0.6,
                },
            ]
    },
    {
        "fields": [ "aps_Therys_GRF1","aps_Therys_GRF2","aps_Therys_GRF3"],
        "ert_id_list": ["WWCT_A4_1","WWCT_A4_2","WWCT_A4_3","WWCT_A4_4","WWCT_A4_5","WWCT_A4_6"],
        "scaling":
            [
                {
                    "index": (10, 55),
                    "value": 0.5,
                },
                {
                    "index": (11, 55),
                    "value": 0.45,
                },
                {
                    "index": (10, 56),
                    "value": 0.55,
                },
                {
                    "index": (11, 56),
                    "value": 0.65,
                },
            ]
    },
]


# Alternative where all combinations of (field_name, ert_id) specified has the same scaling factor
# and the scaling factor is specified as a 2D map (matrix)
scaling_factor_maps_dict = [
    {
        "fields": [ "aps_Valysar_GRF1","aps_Valysar_GRF2","aps_Valysar_GRF3"],
        "ert_id_list": ["WGOR_A4_1", "WGOR_A4_2", "WGOR_A4_3"],
        "scaling_map": {
            "nx": 7,
            "ny": 5,
            "index_order": "C", # j + i*ny
            "map_values":
                [
                      0, 0, 0, 0.01, 0.04,
                    0.1, 0.2, 0.3, 0.2, 0.1,
                    0.2, 0.3, 0.5, 0.3, 0.2,
                    0.3, 0.4, 0.7, 0.4, 0.3,
                    0.2, 0.8, 1.0, 0.8, 0.4,
                    0.1, 0.4, 0.7, 0.5, 0.3,
                    0.0, 0.2, 0.5, 0.3, 0.1,
                ]
            }
    },
    {
        "fields": [ "aps_Therys_GRF1","aps_Therys_GRF2","aps_Therys_GRF3"],
        "ert_id_list": ["WWCT_A4_1","WWCT_A4_2","WWCT_A4_3","WWCT_A4_4","WWCT_A4_5","WWCT_A4_6"],
        "scaling_map": {
            "nx": 7,
            "ny": 5,
            "index_order": "C", # j + i*ny
            "map_values":
                [
                      0, 0, 0, 0.01, 0.04,
                    0.1, 0.2, 0.3, 0.2, 0.1,
                    0.2, 0.3, 0.5, 0.3, 0.2,
                    0.3, 0.4, 0.7, 0.4, 0.3,
                    0.2, 0.8, 1.0, 0.8, 0.4,
                    0.1, 0.4, 0.7, 0.5, 0.3,
                    0.0, 0.2, 0.5, 0.3, 0.1,
                ]
            }
    },
]

print(json.dumps(scaling_factor_dict, sort_keys=True, indent=3))
print()
print(json.dumps(scaling_factor_group_dict, sort_keys=True, indent=3))
print()
print(json.dumps(scaling_factor_maps_dict, sort_keys=True, indent=3))

