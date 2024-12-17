import copy
from typing import Dict, List

import numpy as np
import xtgeo


def create_bw_per_facies(
    project,
    grid_name: str,
    bw_name: str,
    original_petro_log_names: List[str],
    facies_log_name: str,
    facies_code_names: Dict[int, str],
    debug_print: bool = False,
) -> None:
    """Function to be imported and applied in a RMS python job
    to create new petrophysical logs from original logs,
    but with one log per facies.
    All grid blocks for the blocked wells not belonging to the facies
    is set to undefined.

    Purpose:
        Create the blocked well logs to be used to condition
        petrophysical realizations where all grid cells are
        assumed to belong to only one facies. This script will
        not modify any of the original logs, only create new logs where only
        petrophysical log values for one facies is selected
        and all other are set ot undefined.

    Input:
        grid model name,
        blocked well set name,
        list of original log names to use,
        facies log name,
        facies code with facies name dictionary

    Output:
        One new petro log per facies per petro variables in the
        input list of original log names. The output will be saved in
        the given blocked well set specified in the input.

    """

    original_log_names = copy.copy(original_petro_log_names)
    original_log_names.append(facies_log_name)
    bw = xtgeo.blockedwells_from_roxar(
        project, grid_name, bw_name, lognames=original_log_names
    )
    print(" ")
    print(f"Update blocked well set {bw_name} for grid model {grid_name}:")

    for well in bw.wells:
        if debug_print:
            print(f"Wellname: {well.name}")

        # Update the new logs by only keeping petro variables
        # belonging to the current facies
        df = well.get_dataframe()
        new_log_names = []
        for facies_code, fname in facies_code_names.items():
            filtered_rows = df[facies_log_name] != int(facies_code)
            for petro_name in original_petro_log_names:
                if petro_name in well.lognames:
                    new_log_name = fname + "_" + petro_name
                    well.create_log(new_log_name)

                    df[new_log_name] = df[petro_name]
                    df[new_log_name][filtered_rows] = np.nan
                    if debug_print:
                        print(f"  Create new log: {new_log_name}")
                    new_log_names.append(new_log_name)

        well.set_dataframe(df)
        if debug_print:
            print(f"Well:  {well.name}")
            print(f"All logs:  {well.lognames_all}")
            print("Dataframe for facies log and new logs:")
            df_updated = well.get_dataframe()
            selected_log_names = []
            selected_log_names.append(facies_log_name)
            selected_log_names.extend(new_log_names)
            print(f"{df_updated[selected_log_names]}")

        print(f"Create new logs for well {well.name}")
        if debug_print:
            print("-" * 100)

        well.to_roxar(
            project,
            grid_name,
            bw_name,
            well.name,
            lognames=new_log_names,
            update_option="overwrite",
        )

    print("New logs: ")
    for name in new_log_names:
        print(f" {name}")
