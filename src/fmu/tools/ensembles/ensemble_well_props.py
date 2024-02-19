"""Compute well properties/stats along a (planned) well path based on ensemble data.

The implementation is through a console script, which reads a YAML config file.

Output will be RMS well file and/or CSV files, in addition to screen info.
"""

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence, no_type_check

import pandas as pd
import xtgeo
import yaml

GCELLNAMES = ["ICELL", "JCELL", "KCELL"]


@dataclass
class ScreenInfo:
    quiet: bool = False
    moreverbose: bool = False

    def oprint(self, *args):
        """Ordinary print info for users."""
        if not self.quiet:
            print(">>", *args)

    def cprint(self, *args):
        """Ordinary but clean print withou leading >>, useful for e.g. dataframes."""
        if not self.quiet:
            print("\n", *args)

    def xprint(self, *args):
        """Extra print if more verbose output is asked for."""
        if not self.quiet and self.moreverbose:
            print(">x", *args)


def get_parser_args(args):
    """Set up parser for command line end point."""
    if args is None:
        args = sys.argv[1:]

    parser = argparse.ArgumentParser(
        description="Compute ensemble properties along a given well.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--config", "-c", type=str, help="Config file in YAML format.")
    parser.add_argument(
        "--example", action="store_true", help="Dump example config file as template"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Be more verbose to screen"
    )
    parser.add_argument(
        "--quiet", "-q", action="store_true", help="Silence all screen messages"
    )

    myargs = parser.parse_args(args)

    if len(args) < 1:
        parser.print_help()
        sys.exit(0)

    return myargs


def dump_example_config():
    """Dump an example config file as example.yml."""

    example = """
    ensemble:
      # root to FMU run/case
      root: /scratch/fmu/nn/01_drogon_ahm
      realizations:
        # spesify as range (both ends incuded) OR as entries
        range: 0-30
        # entries: [0, 4, 5, 7, 13]
      # full name of iteration folder, e.g. 'iter-2' or 'pred'
      iteration: iter-0

    well:
      # path (full or relative) to well (which must be in RMS ascii well format)
      file: /some/path/to/mywell.w
      # lognames to import (optional, to speed up, default is "all" which can be slow)
      # a recommendation is to ONLY include the required MD log
      lognames: ["PHIT", "MD"]
      # name of MDepth log in file (a measured depth log is required)
      mdlog: MD
      # delta = sampling rate, default is 2 (if metric units: means 2 meters)
      # A large delta will speed up run but decrease accuracy
      delta: 1
      # which MD ranges to evaluate, list in list where inner is [min, max]
      mdranges: [[1690, 1710], [1730, 1830]]

    gridproperties:
      grid:
        # filestub is path after 'root / "realization-N" / iteration'
        filestub: share/results/grids/geogrid.roff
        # if grid is without structural uncertainty => reuse: True
        reuse: false

      # list of properties to analyse with codes (discrete, e.g. facies) or
      # range interval; the final report will combine all these criteria!
      # The filestub is a relative path the the ensemble run
      properties:
        - name: Facies
          filestub: share/results/grids/geogrid--facies.roff
          discrete: true
        - name: PHIT
          filestub: share/results/grids/geogrid--poro.roff
        - name: PERM
          filestub: share/results/grids/geogrid--perm.roff
    report:
      # produce a RMS ascii well file with average logs (can be imported to RMS)
      average_logs:
        fileroot: some
      # report cumulative length statistics on CSV format, note that multiple criteria
      # is possible and the result will be a "AND" combination
      cumulative_lengths:
        # output will be one file for reals, and one file for statistics e.g.
        # cumlen.csv and cumlen_summary.csv
        fileroot: cumlen
        criteria:
          Facies:
            codes: [1, 3, 4] # several numbers possible
          PHIT:
            interval: [0.22, 0.4]  # only two numbers
          PERM:
            interval: [1000, 100000]  # only two numbers
      # the fields below gives an opportunity to study more details of the calculations
      keep_intermediate_logs: false
      show_in_terminal: true

    """

    example = example.split("\n")[1:]

    with open("example.yml", "w", encoding="utf-8") as stream:
        for line in example:
            line = line.replace(" " * 4, "", 1)
            stream.write(f"{line}\n")
    print("See example.yml, and use this as template for your case!")


def parse_config(configfile):
    """Parse YAML file."""
    try:
        with open(configfile, "r", encoding="utf-8") as stream:
            config = yaml.safe_load(stream)
    except IOError:
        print(f"Could not read file: {configfile}")
        raise

    return config


@dataclass
class PropsData:
    """Holding property data and criteria"""

    name: str
    filestub: str
    discrete: bool = False
    codes: Optional[list] = None
    interval: Optional[list] = None


@dataclass
class ConfigData:
    """Other class data than config are evaluated from config in post_init."""

    config: dict
    root: Optional[Path] = None
    reals: Optional[list] = None
    itera: Optional[str] = None

    wellfile: Optional[Path] = None
    welldelta: int = 2

    gridfile: Optional[Path] = None
    gridreuse: bool = False

    proplist: Optional[List[PropsData]] = None

    report_avg_file: Optional[str] = None
    report_cum_file: Optional[str] = None
    report_keep_intermediate: bool = False
    report_show_in_terminal: bool = True

    def __post_init__(self):
        """Derive input data from config."""

        self.root = Path(self.config["ensemble"]["root"])

        if "range" in self.config["ensemble"]["realizations"]:
            start, stop = self.config["ensemble"]["realizations"]["range"].split("-")
            self.reals = list(range(int(start), int(stop) + 1))
        elif "entries" in self.config["ensemble"]["realizations"]:
            self.reals = self.config["ensemble"]["realizations"]["entries"]
        else:
            raise ValueError("For 'realizations': 'range' or 'entries' is missing")

        self.itera = self.config["ensemble"]["iteration"]

        self.wellfile = self.config["well"]["file"]
        self.lognames = self.config["well"].get("lognames", "all")
        self.mdlog = self.config["well"].get("mdlog", "MDepth")
        self.mdranges = self._validate_mdranges(self.config["well"]["mdranges"])
        self.welldelta = self.config["well"].get("delta", 2)

        cfgprop = self.config["gridproperties"]
        self.gridfilestub = Path(cfgprop["grid"]["filestub"])
        self.gridreuse = cfgprop["grid"].get("reuse", False)

        self.proplist = []
        props = cfgprop["properties"]
        for prop in props:
            name = prop["name"]
            filestub = prop["filestub"]
            discrete = prop.get("discrete", False)

            propcase = PropsData(name, filestub, discrete)
            self.proplist.append(propcase)

        rpt = self.config["report"]
        if "average_logs" in rpt:
            self.report_avg_file = rpt["average_logs"].get("fileroot", None)
            if self.report_avg_file:
                self.report_avg_file += ".rmswell"

        if "cumulative_lengths" in rpt:
            self.report_cum_file = rpt["cumulative_lengths"].get("fileroot", None)
            crit = rpt["cumulative_lengths"].get("criteria", None)
            if crit is None:
                raise ValueError("Criteria is missing for 'cumulative_length' option")

            for propcase in self.proplist:
                if crit and propcase.name in crit:
                    codes = crit[propcase.name].get("codes", None)
                    interval = crit[propcase.name].get("interval", None)
                    if not codes and propcase.discrete:
                        raise ValueError(
                            f"Discrete property {propcase.name} must have "
                            "'codes' as criteria"
                        )
                    if not interval and not propcase.discrete:
                        raise ValueError(
                            f"Continuous property {propcase.name} must have "
                            "'interval' as criteria"
                        )

                    propcase.codes = self._validate_codes(codes)
                    propcase.interval = self._validate_interval(interval)

        self.report_keep_intermediate = rpt.get("keep_intermediate_logs", False)
        self.report_show_in_terminal = rpt.get("show_in_terminal", True)

    @staticmethod
    def _validate_mdranges(mdranges: List[Sequence[float]]) -> List[Sequence[float]]:
        """Check that mdranges are on proper form and that intervals do not overlap"""
        if not mdranges:
            raise ValueError("Mandatory input 'mdranges' is not set!")

        previous_stop = -999999.0
        for mdsubset in mdranges:
            start, stop = mdsubset
            if not isinstance(start, (int, float)) or not isinstance(
                stop, (int, float)
            ):
                raise ValueError("Values in mdranges must be numbers")

            if stop <= start:
                raise ValueError(
                    f"Stop value in mdranges ranges is less than start: {mdsubset}"
                )
            if start < previous_stop:
                raise ValueError(f"Ranges cannot be overlapping: {mdranges}")

            previous_stop = stop

        return mdranges

    @staticmethod
    def _validate_codes(codes):
        """Check that codes input looks sane."""
        if codes is None:
            return None

        if isinstance(codes, list):
            for code in codes:
                if not isinstance(code, int):
                    raise ValueError(f"Code is not integer: {code} in {codes}")
        else:
            raise ValueError("The 'codes' input is not a list")

        return codes

    @staticmethod
    def _validate_interval(interval):
        """Check that interval input looks sane."""
        if interval is None:
            return None

        if isinstance(interval, list):
            if len(interval) != 2:
                raise ValueError(
                    f"Interval list input must be 2 items exactly: {interval}"
                )
            imin, imax = interval
            if not isinstance(imin, (int, float)):
                raise ValueError(
                    f"First number in interval (minimum) is not a number: {interval}"
                )
            if not isinstance(imax, (int, float)):
                raise ValueError(
                    f"Second number in interval (maximum) is not a number: {interval}"
                )
            if imin >= imax:
                raise ValueError(f"Minimum cannot be >= than maximum: {interval}")

        else:
            raise ValueError("The 'interval' is not a list")

        return interval


@dataclass
class WellCase:
    well: xtgeo.Well
    mdlog: str
    mdranges: list
    delta: int = 2

    def __post_init__(self):
        """Various post init operations."""
        self.well.rescale(delta=self.delta)

        dflist = []
        for rnge in self.mdranges:
            dfrorig = self.well.dataframe.copy()
            rmin, rmax = rnge
            dfr = dfrorig[(dfrorig[self.mdlog] >= rmin) & (dfrorig[self.mdlog] <= rmax)]
            dfr = dfr.reset_index(drop=True)
            dflist.append(dfr)

        self.well.dataframe = pd.concat(dflist, ignore_index=True)


@dataclass
class EnsembleWellProps:
    """The ensemble well props is use for post loop analysis."""

    well: xtgeo.Well
    realizations: list
    cfg: ConfigData
    sinfo: ScreenInfo

    added_logs: Optional[dict] = None  # added log per prop name; normally tmp
    added_flag_logs: Optional[list] = None
    cumlenreport: Optional[pd.DataFrame] = None
    cumlenreport_summary: Optional[pd.DataFrame] = None

    def __post_init__(self):
        allprops = {}
        for prop in self.cfg.proplist:
            plist = []
            for real in self.realizations:
                plist.append(f"{prop.name}_r{real}")
            allprops[prop.name] = plist
        self.added_logs = allprops

    @no_type_check
    def process_ensemble_avglogs(self) -> bool:
        """Make ensemble mean or mode (most-of) logs."""
        if not self.cfg.report_avg_file:
            return False

        dfr = self.well.dataframe
        for prop in self.cfg.proplist:
            pplist = self.added_logs[prop.name]
            if not prop.discrete:
                self.well.create_log(
                    f"{prop.name}_mean",
                    logtype="CONT",
                )
                dfr[f"{prop.name}_mean"] = dfr[pplist].mean(axis=1)
            else:
                self.well.create_log(
                    f"{prop.name}_mode",
                    logtype="DISC",
                    logrecord=self.well.get_logrecord(pplist[0]),
                )
                dfr[f"{prop.name}_mode"] = dfr[pplist].mode(axis=1)[0]  # most of
        return True

    @no_type_check
    def process_ensemble_cumlen(self) -> bool:
        """Provide cumulative length statistics."""

        if not self.cfg.report_cum_file:
            return False

        dfr = self.well.dataframe
        mdstart = dfr[self.cfg.mdlog].values[0]
        mdend = dfr[self.cfg.mdlog].values[-1]
        totlensegments = 0
        nsegments = len(self.cfg.mdranges)
        for intv in self.cfg.mdranges:
            lmin, lmax = intv
            if lmax > mdend:
                lmax = mdend
            totlensegments += lmax - lmin

        myreport = []
        added_flag_logs = []
        for real in self.realizations:
            cname = f"_COMB_r{real}"
            dfr[cname] = 1
            added_flag_logs.append(cname)

            for prop in self.cfg.proplist:
                idn = f"_r{real}"
                pidn = prop.name + idn
                pidx = "q" + pidn
                if prop.codes:
                    dfr[pidx] = 0
                    for code in prop.codes:
                        dfr.loc[dfr[pidn] == code, pidx] = 1
                    added_flag_logs.append(pidx)
                    dfr.loc[dfr[pidx] != 1, cname] = 0
                if prop.interval:
                    dfr[pidx] = 0
                    vmin, vmax = prop.interval
                    dfr.loc[(dfr[pidn] >= vmin) & (dfr[pidn] <= vmax), pidx] = 1
                    added_flag_logs.append(pidx)
                    dfr.loc[dfr[pidx] != 1, cname] = 0

            fractions = self.well.dataframe[cname].dropna().value_counts(normalize=True)
            cfrac = fractions.get(1, 0.0)

            clen = totlensegments * cfrac

            rline = [
                real,
                self.well.name,
                nsegments,
                cfrac,
                clen,
                totlensegments,
                mdend - mdstart,
                mdstart,
                mdend,
            ]
            myreport.append(rline)

        self.added_flag_logs = added_flag_logs
        dfr = self.cumlenreport = pd.DataFrame(
            myreport,
            columns=[
                "REAL",
                "WELLNAME",
                "NSEGMENTS",
                "GOODFRACTION",
                "GOODCUMLENGTH",
                "TOTALLENGTH_ACTIVE",
                "TOTALLENGTH_ALL",
                "MDSTART",
                "MDEND",
            ],
        )
        newdfr = dfr[["GOODFRACTION", "GOODCUMLENGTH"]]

        self.cumlenreport_summary = newdfr.describe(percentiles=[0.1, 0.5, 0.9])

        return True

    def optionally_delete_logs(self):
        keep = self.cfg.report_keep_intermediate
        if not keep and self.added_logs:
            wll = self.well
            for _, val in self.added_logs.items():
                wll.delete_logs(val)

    def optionally_delete_flag_logs(self):
        keep = self.cfg.report_keep_intermediate
        if not keep and self.added_flag_logs:
            wll = self.well
            wll.delete_logs(self.added_flag_logs)


@no_type_check
def loop_for_compute(
    config: dict, sinfo: ScreenInfo, _dryrun: bool = False
) -> EnsembleWellProps:
    """Collect for computing the ensemble statistics.

    Args:
        config: The input configuration dictonary
        sinfo: Messages to screen instance
        _dryrun: For testing, skipping computation
    """
    cfg = ConfigData(config)
    wcase = WellCase(
        xtgeo.well_from_file(cfg.wellfile, lognames=cfg.lognames),
        cfg.mdlog,
        cfg.mdranges,
        cfg.welldelta,
    )

    grd = None

    sinfo.oprint("Loop data over realizations...")
    used_realizations = []

    for real in cfg.reals:
        sinfo.oprint(f"Realization no. {real}")
        realiterpath = cfg.root / f"realization-{real}" / cfg.itera

        if not isinstance(grd, xtgeo.Grid) or not cfg.gridreuse:
            # one may choose to reuse grid if not structural uncertainty
            sinfo.oprint(f"Read grid geometry for realization {real}")
            gpath = realiterpath / cfg.gridfilestub
            try:
                grd = xtgeo.grid_from_file(gpath)
            except OSError:
                sinfo.oprint(f"Not able to read grid {gpath}, skip realization...")
                continue
            wcase.well.delete_logs(GCELLNAMES)
            wcase.well.make_ijk_from_grid(grd)

        for propcase in cfg.proplist:
            proppath = realiterpath / propcase.filestub
            sinfo.oprint(f"Read: {proppath}...")
            try:
                theprop = xtgeo.gridproperty_from_file(proppath)
            except OSError:
                sinfo.oprint(
                    f"Not able to read property {propcase.name} from {proppath}, "
                    "skip realization..."
                )
                continue
            theprop.geometry = grd

            if _dryrun is False:
                run_compute(real, wcase.well, propcase, theprop)
        used_realizations.append(real)

    sinfo.xprint("Delete logs referring to cells...")
    wcase.well.delete_logs(GCELLNAMES)
    return EnsembleWellProps(wcase.well, used_realizations, cfg, sinfo)


def run_compute(real, well, prop, theprop):
    """Compute well props sampled from gridproperties for one propert and realization.

    The well.dataframe is updated in-place with new column(s)
    """

    idn = f"_r{real}"
    theprop.name = prop.name

    well.get_gridproperties(theprop, grid=tuple(GCELLNAMES), prop_id=idn)


@no_type_check
def process_ensemble(ens: EnsembleWellProps):
    """Process the ensemble (seen in well) according to client 'report' requirements.

    Args:
        ens: Instance of EnsembleWellProps which holds all relevant data
    """
    avgstatus = ens.process_ensemble_avglogs()

    cumstatus = ens.process_ensemble_cumlen()
    sinfo = ens.sinfo
    sinfo.oprint("Process ensemble data for well...")
    sinfo.xprint(f"The avgstatus is {avgstatus} and cumstatus is {cumstatus}")
    if avgstatus:
        ens.optionally_delete_logs()
        ens.optionally_delete_flag_logs()
        if ens.cfg.report_show_in_terminal:
            sinfo.cprint(f"Well data:\n{ens.well.dataframe.to_string()}")
        sinfo.oprint(f"Save to RMS well data file: {ens.cfg.report_avg_file}")
        ens.well.to_file(ens.cfg.report_avg_file)

    if cumstatus:
        ens.optionally_delete_logs()
        ens.optionally_delete_flag_logs()
        if ens.cfg.report_show_in_terminal:
            sinfo.cprint(f"\nPer realization:\n{ens.cumlenreport}")
            sinfo.cprint(f"\nSummary:\n{ens.cumlenreport_summary}")

        ens.cumlenreport.to_csv(ens.cfg.report_cum_file + ".csv")
        ens.cumlenreport_summary.to_csv(ens.cfg.report_cum_file + "_summary.csv")
        sinfo.oprint(
            f"Wrote summary to {ens.cfg.report_cum_file}.csv and "
            f"{ens.cfg.report_cum_file}_summary.csv"
        )


def main(args=None):
    """Main routine for ensemble_well_props.

    Args:
        args: Input config; if missing the command line is parsed for YAML file.
    """

    if isinstance(args, dict):
        screeninfo = ScreenInfo()
        config = args

    else:
        args = get_parser_args(args)

        if args.example:
            dump_example_config()
            return
        if args.config:
            screeninfo = ScreenInfo(args.quiet, args.verbose)
            config = parse_config(args.config)

    ens = loop_for_compute(config, screeninfo)
    process_ensemble(ens)


if __name__ == "__main__":
    main()
