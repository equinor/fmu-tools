"""Private module in qcforward, used to compare blocked wells with grid props.

The idea here is to compare blocked wells (cells) with actual values in order
warn user and/or stop runs if discrepancies are too large.

The resulting report will look like this:

::

             WELL COMPARE(BW:MOD) WARNRULE   STOPRULE  MATCH%  STATUS  NAMETAG
    INDEX
        0    A_6  PHIT:PHIT       any<90%    any<70%    99%     OK      MYDATA
        1    A_6  Facies:FACIES   any<90%    any<70%    91%     OK      MYDATA
        2    A_5  PHIT:PHIT       any<90%    any<70%    93%     OK      MYDATA
        3    A_5  Facies:FACIES   any<90%    any<70%    77%     WARN    MYDATA
        4    A_4  PHIT:PHIT       any<90%    any<70%    88%     WARN    MYDATA
        5    A_4  Facies:FACIES   any<90%    any<70%    73%     WARN    MYDATA
        6    all  PHIT:PHIT       all<95%    all<80%    88%     OK      MYDATA
        7    all  Facies:FACIES   all<95%    all<80%    88%     OK      MYDATA

The input spesification is on the following form if outside RMS:

::

    DATA1 = {
        "nametag": "MYDATA1",
        "verbosity": "debug",
        "path": PATH,
        "bwells": WELLFILES,
        "grid": GRIDFILE,
        "gridprops": [["PHIT", ROFFFILE], ["FACIES", ROFFFILE]],
        "compare": {"Facies": "FACIES", "PHIT": "PHIT"},  # bwname: modelname
        "actions": [
            {"warn": "anywell < 80%", "stop": "anywell < 70%"},
            {"warn": "allwells < 90%", "stop": "allwells < 80%"},
        ],
        "report": {"file": REPORT, "mode": "write"},
        "dump_yaml": SOMEYAML,
        "tolerance": 0.01
    }

If one need to have different actions for different comparisons, use e.g.:

::

    DATA2 = deepcopy(DATA1)
    DATA2["compare"] = {"VSH": "Vshale"}
    DATA2["actions"] =
        [
            {"warn": "anywell < 86%", "stop": "anywell < 75%"},
            {"warn": "allwells < 97%", "stop": "allwells < 89%"},
        ],

and rerrun.

Note that ``any`` and ``all`` will work as shortform to ``anywell`` and ``allwell``.

"""

import json
from collections import OrderedDict
from pathlib import Path
from typing import Any, Optional, Union

import pandas as pd
from jsonschema import validate

import fmu.tools
from fmu.tools._common import _QCCommon
from fmu.tools.qcdata import QCData
from fmu.tools.qcforward._qcforward import ActionsParser, QCForward, actions_validator

QCC = _QCCommon()


class _LocalData:
    def __init__(self):
        """Defining and hold data local (or special) for this routine."""
        self.actions = None
        self.compare = None
        self.infotext = "BW vs GRIDPROPS"
        self.nametag = None
        self.reportfile = None
        self.tolerance = 0.01  # tolerance when comparing
        self.show_data = None
        self.tvd_range = None

        QCC.print_debug("Initialized local data _LocalData")

    def parse_data(self, data):
        """Parsing the actual data"""

        self.nametag = data.get("nametag", "unset_nametag")
        if "report" in data:
            self.reportfile = (
                data["report"].get("file")
                if isinstance(data["report"], dict)
                else data["report"]
            )

        self.actions = actions_validator(data["actions"])

        self.compare = data["compare"]
        self.tolerance = data.get("tolerance", self.tolerance)
        self.show_data = data.get("show_data", self.show_data)
        self.tvd_range = data.get("tvd_range", self.tvd_range)
        QCC.print_debug("Parsing data is done")


class BlockedWellsVsGridProperties(QCForward):
    def run(
        self,
        data: Union[dict, str],
        reuse: Optional[bool] = False,
        project: Optional[Any] = None,
    ):
        """Main routine for evaluating blockedwells vs gridproperties

        The routine depends on existing XTGeo functions for this purpose.

        Args:
            data (dict or str): The input data either as a Python dictionary or
                a path to a YAML file
            reuse (bool or list): Reusing some "timeconsuming to read" data in the
                instance. If True, then grid and gridprops will be reused as default.
                Alternatively it can be a list for more fine grained control, e.g.
                ["grid", "gridprops", "bwells"]
            project (Union[object, str]): For usage inside RMS, None if running files

        """
        self._data = self.handle_data(data, project)
        self._validate_input(self._data, project)

        QCC.verbosity = self._data.get("verbosity", 0)

        # parse data that are special for this check
        QCC.print_info("Parsing additional data...")
        self.ldata = _LocalData()
        self.ldata.parse_data(self._data)

        # now need to retrieve blocked properties and grid properties from the "compare"
        # dictionary:
        wsettings = {"lognames": list(self.ldata.compare.keys())}

        if project:
            # inside RMS, get gridprops implicitly from compare values
            self._data["gridprops"] = list(self.ldata.compare.values())

        if not isinstance(self.gdata, QCData):
            self.gdata = QCData()

        self.gdata.parse(
            data=self._data, reuse=reuse, project=project, wells_settings=wsettings
        )

        dfr, comb = self.compare_bw_props()

        QCC.print_debug(f"Results: \n{dfr}")
        status = self.evaluate_qcreport(
            dfr, "blocked wells vs grid props", stopaction=False
        )

        # make it possible to print the underlying dataframe, either some wells (.e.g
        # the failing) or all wells. If 'fail' it will only show those lines that
        # contains FAIL
        show = self.ldata.show_data
        if show is None or show is False:
            pass
        elif isinstance(show, dict):
            if "lines" not in show or "wellstatus" not in show:
                raise ValueError(
                    f"The 'showdata' entry is in an invalid form or format: {show}"
                )

            lines = show["lines"].upper()
            wstatus = show["wellstatus"].upper()

            print(
                f"\n** Key 'show_data' is active, here showing lines with {lines} "
                f"for wells classified as {wstatus} **"
            )
            # filter out all line with word FAIL or WARN or ... , h/t HAVB
            fcomb = comb[comb.astype(str).agg("".join, axis=1).str.contains(lines)]
            if len(fcomb) > 0:
                mask = dfr["STATUS"] == wstatus
                wells = [well for well in dfr[mask]["WELL"].unique() if well != "all"]
                if wells:
                    print(f"Wells within {wstatus} criteria are: {wells}:\n")
                    print(fcomb[fcomb["WELLNAME"].isin(wells)].to_string())
                else:
                    print(f"No wells within {wstatus} criteria")
            else:
                print(f"No lines are matching {lines}. Wrong input?:\n")

        else:
            print("Show all well cells for all wells:")
            if len(comb) > 0:
                print(comb.to_string())

        if status == "STOP":
            QCC.force_stop("STOP criteria is found!")

    def compare_bw_props(self) -> pd.DataFrame:
        """Given data, do a comparison of blcked wells cells vs props, via XTGeo."""

        # dataframe for the blocked wells
        dfbw = self.gdata.bwells.get_dataframe()
        if self._gdata.project is not None:
            # when parsing blocked wells from RMS, cell indices starts from 0, not  1
            dfbw["I_INDEX"] += 1
            dfbw["J_INDEX"] += 1
            dfbw["K_INDEX"] += 1

        # filtering on depth tvd_range:
        if self.ldata.tvd_range and isinstance(self.ldata.tvd_range, list):
            zmin = self.ldata.tvd_range[0]
            zmax = self.ldata.tvd_range[1]
            if zmin >= zmax:
                raise ValueError("The zmin value >= zmax in 'tvd_range'")
            dfbw = dfbw[dfbw["Z_TVDSS"] >= zmin]
            dfbw = dfbw[dfbw["Z_TVDSS"] <= zmax]
            if dfbw.empty:
                raise RuntimeError(
                    f"No wells left after tvd_range: {self.ldata.tvd_range}"
                )

        # dataframe for the properties, need some processing (column names)
        dfprops = self.gdata.gridprops.get_dataframe(ijk=True, grid=self.gdata.grid)
        dfprops = dfprops.rename(
            columns={"IX": "I_INDEX", "JY": "J_INDEX", "KZ": "K_INDEX"}
        )

        # merge the dataframe on I J K index
        comb = pd.merge(
            dfbw,
            dfprops,
            how="inner",
            on=["I_INDEX", "J_INDEX", "K_INDEX"],
            suffixes=("__bw", "__model"),  # in case the names are equal -> add suffix
        )
        QCC.print_debug("Made a combined dataframe!")
        QCC.print_debug(f"\n {comb}")

        diffs = {}

        # compare the relevant properties
        for bwprop, modelprop in self._ldata.compare.items():
            usebwprop = bwprop if bwprop != modelprop else bwprop + "__bw"
            usemodelprop = modelprop if bwprop != modelprop else modelprop + "__model"
            dname = bwprop + ":" + modelprop
            dnameflag = dname + "_flag"
            comb = self._eval_tolerance(comb, usebwprop, usemodelprop, dname, dnameflag)
            diffs[dname] = dnameflag

        return self._evaluate_diffs(comb, diffs), comb

    def _eval_tolerance(self, df_in, bwprop, modelprop, diffname, diffnameflag):
        """Make a flag log for diffs based on tolerance input."""
        comb = df_in.copy()
        tol = self.ldata.tolerance

        relative = isinstance(tol, dict) and "rel" in tol
        tolerance = tol if isinstance(tol, float) else list(tol.values())[0]

        comb[diffname] = comb[bwprop] - comb[modelprop]
        comb[diffnameflag] = "MATCH"
        if relative:  # adjust relative to be weighted on mean() value
            comb[bwprop + "_mean"] = comb[bwprop].mean()
            comb[diffname + "_rel"] = comb[diffname] / comb[bwprop + "_mean"]
            comb.loc[abs(comb[diffname + "_rel"]) > tolerance, diffnameflag] = "FAIL"
        else:
            comb.loc[abs(comb[diffname]) > tolerance, diffnameflag] = "FAIL"

        return comb

    def _evaluate_diffs(self, comb, diffs) -> pd.DataFrame:
        result: OrderedDict = OrderedDict(
            [
                ("WELL", []),
                ("COMPARE(BW:MODEL)", []),
                ("WARNRULE", []),
                ("STOPRULE", []),
                ("MATCH%", []),
                ("STATUS", []),
            ]
        )

        wells = list(comb["WELLNAME"].unique())
        wells.append("all")

        QCC.print_info("Compare per well...")
        for wname in wells:
            subset = comb[comb["WELLNAME"] == wname]
            for diff, flag in diffs.items():
                result["WELL"].append(wname)
                result["COMPARE(BW:MODEL)"].append(diff)
                if wname != "all":
                    match = subset[flag].value_counts(normalize=True)["MATCH"] * 100.0
                else:
                    match = comb[flag].value_counts(normalize=True)["MATCH"] * 100.0

                result["MATCH%"].append(match)
                status = "OK"

                for therule in self.ldata.actions:
                    warnrule = ActionsParser(
                        therule.get("warn", None), mode="warn", verbosity=QCC.verbosity
                    )
                    stoprule = ActionsParser(
                        therule.get("stop", None), mode="stop", verbosity=QCC.verbosity
                    )

                    for _, issue in enumerate([warnrule, stoprule]):
                        if (wname != "all" and not issue.all) or (
                            wname == "all" and issue.all
                        ):
                            rulename = issue.mode.upper() + "RULE"
                            result[rulename].append(issue.expression)
                            if issue.compare == "<" and match < issue.limit:
                                status = issue.mode.upper()

                result["STATUS"].append(status)

        dfr = self.make_report(
            result, reportfile=self.ldata.reportfile, nametag=self.ldata.nametag
        )
        QCC.print_info("Dataframe is created")
        return dfr

    @staticmethod
    def _validate_input(data, project):
        """Validate data against JSON schemas, TODO complete schemas"""

        spath = Path(fmu.tools.__file__).parent / "qcforward" / "_schemas"

        schemafile = "bw_vs_gridprops_asfile.json"

        if project:
            schemafile = "bw_vs_gridprops_asroxapi.json"

        with open((spath / schemafile), "r", encoding="utf-8") as thisschema:
            schema = json.load(thisschema)

        validate(instance=data, schema=schema)
