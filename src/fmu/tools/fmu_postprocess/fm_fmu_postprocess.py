import os
import sys
import argparse
import glob
import re
import yaml
import logging
import importlib
import subprocess
import difflib

import pandas as pd

import ecl2df
from fmu.tools.rms import volumetrics

from .qc_fmu_postprocess import prepare_share_dir

DESCRIPTION = """
A generic post-processor for FMU runs, to be run in each realization
directory after simulation"""

logger = logging.getLogger("fm_fmu_postprocess")
logging.basicConfig()


def get_parser():
    parser = argparse.ArgumentParser(description=DESCRIPTION)
    parser.add_argument(
        "--runpath", type=str, default=".", help="Runpath of the realization"
    )

    parser.add_argument("--config", type=str, help="fmu_postprocess yml config file")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument(
        "--eclbase", type=str, help="Eclipse basename (only partial string needed)"
    )

    return parser


def process_rms_volumetrics(
    rmsvoldir="share/results/volumes", pattern="*.txt", config=None
):
    """Process RMS volumetrics files, into CSV files

    By default all *.txt files will be assumed to be ouputted from rms
    volumetrics job.

    A similar file with extension .csv is written if conversion is successful.
    The "_1" suffix from RMS is removed as it is not in use for FMU runs.

    If file extension differ from txt, the computed cvs file names will suffer.

    Args:
        rmsvoldir (str): Relative paths for where volumetrics output is
        pattern (str): Glob-pattern for files to look for in rmsvoldir
        config (dict):  Configuration options for rms volumetrics processing.

    Returns:
        list of str, filenames successfully written to (csv).
    """
    if config is None:
        config = {}

    csvfiles = []
    files = glob.glob(os.path.join(rmsvoldir, pattern))
    volumetrics_frames = {}
    for filename in files:
        dframe = None
        try:
            dframe = volumetrics.rmsvolumetrics_txt2df(filename)
        except (TypeError, pd.errors.EmptyDataError):
            continue

        # Try merging in FIPNUM-data if information is
        # found in the config object
        dframe = merge_fipnum_to_rmsvols(dframe, config)

        volumetrics_frames[filename] = dframe

        csvfilename = (
            os.path.basename(filename).replace("_1.txt", "").replace(".txt", "")
            + ".csv"
        )
        logger.info("Writing RMS volumetrics to %s", str(csvfilename))
        dframe.to_csv(os.path.join(rmsvoldir, csvfilename), index=False)
        csvfiles += csvfilename

    rms_volumetrics_frame = merge_rms_volumetrics(volumetrics_frames, config)
    if not rms_volumetrics_frame.empty:
        rms_volumetrics_frame.to_csv(
            os.path.join(rmsvoldir, "rms_volumetrics.csv"), index=False
        )

    return csvfiles


def merge_rms_volumetrics(frames, config):
    """Merge a dict of dataframes that represent RMS volumetrics.

    Only frames that look like RMS volumetrics will be attempted.

    The names of each dataframe (the key in the dict) will be used to
    suffix overlapping column names.

    Args:
        dict or list of pd.Dataframe
    """

    # These are the index columns that can present in volumetrics frames.
    # We will merge on the maximal subset of each frames columns of this list,
    # any frames which has less than the max number of accepted index columns
    # will not be attempted merged.
    volumetrics_index_cols = {"ZONE", "REGION", "FACIES", "LICENSE"}
    frame_index_cols = {}
    for frame in frames.values:
        frame_index_cols = frame_index_cols.union(
            set(frame.columns).intersection(volumetrics_index_cols)
        )

    logger.info("Will merge RMS volumetrics on keys %s", str(frame_index_cols))

    ### CONTINUE WORKING HERE!!!

    frames_by_filename = list(volumetrics_frames.keys())
    print(frames_by_filename)
    if len(frames_by_filename) == 2:
        # Don't support anything else yet.
        frame0 = volumetrics_frames[frames_by_filename[0]]
        frame1 = volumetrics_frames[frames_by_filename[1]]
        frame0_indexcols = volumetrics_index_cols.intersection(frame0.columns)
        frame1_indexcols = volumetrics_index_cols.intersection(frame1.columns)
        if frame0_indexcols != frame1_indexcols:  # set comparison
            logger.info(
                "Giving up merging %s and %s, not compatible columns",
                frames_by_filename[0],
                frames_by_filename[1],
            )
        else:
            # Rename non-index columns, to ensure we can identify them later
            id_strings = identifying_substrings(
                [frames_by_filename[0], frames_by_filename[1]]
            )
            print(id_strings)
            logger.info(
                "Suffixing common columns in %s by %s",
                frames_by_filename[0],
                id_strings[0].upper(),
            )
            logger.info(
                "Suffixing common columns in %s by %s",
                frames_by_filename[1],
                id_strings[1].upper(),
            )
            common_columns = (
                set(frame0.columns).intersection(frame1.columns) - index_cols
            )
            logger.info("Common columns are %s", str(common_columns))
            frame0.rename(
                columns={
                    col: col + "_" + id_strings[0].upper() for col in common_columns
                },
                inplace=True,
            )
            frame1.rename(
                columns={
                    col: col + "_" + id_strings[1].upper() for col in common_columns
                },
                inplace=True,
            )
            print(frame0)
            print(frame1)
            print(pd.merge(frame0, frame1, on=list(frame0_indexcols)))


def merge_fipnum_to_rmsvols(dframe, inplace=True, config=None):
    """Try to map in FIPNUM for each row, for later merging with Eclipse
        volumetrics. Multiple rows can map to the same FIPNUM. We assume
        that zone+region in RMS is always a finer subdivision compared to FIPNUM.

        Args:
            dframe (pd.DataFrame)
            inplace (bool): Modify incoming dataframe or return a copy. Default True
            config (dict)

        Returns
            pd.DataFrame - same as input, but perhaps  with a FIPNUM column added.
        """
    if not inplace:
        dframe = dframe.copy()
    if config is None:
        return dframe
    if "REGION" not in dframe:
        raise ValueError("REGION column not found in dataframe. RMS volumetrics data?")
    if "FIPNUM" in dframe:
        logger.error("FIPNUM already in dataframe, will not add again")
        return dframe
    if "region2fipnum" in config:
        if isinstance(config["region2fipnum"], dict):
            if set(dframe["REGION"].unique()).issubset(config["region2fipnum"].keys()):
                print("proper subset")
                dframe["FIPNUM"] = dframe["REGION"].map(config["region2fipnum"])
            else:
                logger.error("region2fipnum did not contain all regions")
        else:
            logger.warning("Unsupported region2fipnum converter")
    if "fipnum2region" in config:
        if isinstance(config["fipnum2region"], dict):
            if len(set(config["fipnum2region"].values())) == len(
                config["fipnum2region"]
            ):
                # Construct reverse dictionary
                region2fipnum = dict(
                    (value, key) for key, value in config["fipnum2region"].items()
                )
                if set(dframe["REGION"].unique()).issubset(region2fipnum.keys()):
                    dframe["FIPNUM"] = dframe["REGION"].map(region2fipnum)
                else:
                    logger.error("fipnum2region did not contain all regions")
    return dframe


def identifying_substrings(strings):
    """
    For a list of incoming string, make a new list of strings that is able to
    identify each of them.

    e.g, if "somepath/geogrid_vol_oil.csv" and "somepath/simgrid_vol_oil.csv"
    is provided, then the substrings that identifies them is "geo" and "sim".
    This works by removing subsequences of the strings that are equal, but only
    subsequences of 3 or more characters.

    When more than two strings are provided, this function works recursively comparing
    each element to the first string, thus the result may depend on the ordering
    of the input.

    Args:
        list of str

    Return
        list of str, the identifying substrings of the input list.
    """
    if isinstance(strings, str):
        raise TypeError
    if not strings:
        return ""
    if len(strings) > 2:
        return (
            identifying_substrings([strings[0], strings[1]])
            + identifying_substrings([strings[0]] + strings[2:])[1:]
        )

    if len(strings) < 2:
        return strings[0]

    str1 = strings[0].replace(" ", "")
    str2 = strings[1].replace(" ", "")

    if str1 == str2:
        raise ValueError("Strings are identical, can't identify them")

    match = difflib.SequenceMatcher(None, str1, str2).get_matching_blocks()

    str1_new = list(str1)
    for matcher in match:
        if matcher.size > 2:
            str1_new[matcher.a : matcher.a + matcher.size] = [" "] * matcher.size
    str2_new = list(str2)
    for matcher in match:
        if matcher.size > 2:
            str2_new[matcher.b : matcher.b + matcher.size] = [" "] * matcher.size
    str1_new = "".join(str1_new).strip()
    str2_new = "".join(str2_new).strip()
    # If there are whitespace, add a underscore to separate:
    # The whitespace should only come from occurence of multiple identifying
    # substrings.
    str1_new = re.sub(r"\s+", "_", str1_new)
    str2_new = re.sub(r"\s+", "_", str2_new)
    return [str1_new, str2_new]


def process_ecl2df(eclbase, outputdir="share/results/tables", config=None):
    if config is None:
        config = {}

    eclfiles = ecl2df.EclFiles(eclbase)
    csvfileswritten = []
    try:
        # Not yet available in ecl2df:
        subprocess.call("prtvol2csv " + eclbase, shell=True)
        # This tool is from 'subscript', and writes to
        # share/results/volumes/simulator_volume_fipnum.csv
    except Exception:
        logging.info("Failed running prtvol2csv")
        pass

    ecl2df_tasks = {
        # Key is filename to write to, value is a dict that will be used as arguments
        # to ecl2df.<module>.df(eclfiles, **). Unless specified, module-name is picked
        # from the filename to write to.
        "compdat.csv": {},
        "equil.csv": {},
        "faults.csv": {},
        "fipreports.csv": {},
        "gruptree.csv": {},
        "nnc.csv": {"coords": True},
        "pillars.csv": {"rstdates": "all", "stackdates": True, "region": "EQLNUM"},
        "grid.csv": {},  # heavy..
        "pvt.csv": {},
        "rft.csv": {},
        "satfunc.csv": {},
        "trans.csv": {},
        "trans-fipnum.csv": {
            "boundaryfilter": True,
            "group": True,
            "addnnc": True,
            "coords": True,
            "vectors": ["FIPNUM"],
        },
        "wcon.csv": {},
        "unsmry--monthly.csv": {"module": "summary", "time_index": "monthly"},
        "unsmry--yearly.csv": {"module": "summary", "time_index": "yearly"},
        "unsmry--lastdate.csv": {"module": "summary", "time_index": "last"},
    }
    # Todo: If grid is available, add eqlnum x,y to equil f.ex.

    ecl2df_frames = {}
    for csvfilename, opts in ecl2df_tasks.items():
        if "module" in opts:
            module = opts["module"]
            del opts["module"]
        else:
            module = csvfilename.replace(".csv", "").split("-")[0]
        ecl2df_module = importlib.import_module("ecl2df." + module)
        try:
            # Warning: This can call C-code, which happily errors on invalid
            # input data, taking down the entire Python process. How to resolve?
            dframe = ecl2df_module.df(eclfiles, **opts)
            ecl2df_frames[csvfilename] = dframe
            dframe.to_csv(os.path.join(outputdir, csvfilename), index=False)
            csvfileswritten += os.path.join(outputdir, csvfilename)
            logger.info(
                "Written to %s, %d columns, %d rows",
                str(outputdir + "/" + csvfilename),
                len(dframe.columns),
                len(dframe),
            )
        except Exception as e_msg:
            logger.info("ecl2df." + module + " failed with message: " + str(e_msg))
            pass

    # Stack on wells, groups, regions and bpr (if available)
    stack_dataset_timeindex = "monthly"
    stack_dataset = "unsmry--" + stack_dataset_timeindex + ".csv"
    stack_tasks = {"well": "W*:*", "region": "R*:*", "block": "BPR:*", "group": "G:*"}
    if stack_dataset in ecl2df_frames:
        stackframe = ecl2df_frames[stack_dataset]
        existing_cols = stackframe.columns
        for stack_name, stack_pattern in stack_tasks.items():
            columns = [
                col
                for col in existing_cols
                if col[0] == stack_pattern[0] and ":" in col
            ]
            if not columns:
                logging.info("Skipping stacking " + stack_name + " due to missing data")
                continue
            tuples = [tuple(col.split(":")) for col in columns]
            stackdata = stackframe[columns]
            stackdata.columns = pd.MultiIndex.from_tuples(
                tuples, names=["DATE", stack_name.upper()]
            )
            stackdata = stackdata.stack().reset_index(level=stack_name.upper())
            csvfilename = os.path.join(
                outputdir,
                "unsmry--" + stack_name + "--" + stack_dataset_timeindex + ".csv",
            )
            stackdata.reset_index().to_csv(csvfilename, index=False)
            csvfileswritten += csvfilename
            logger.info(
                "Written to %s, %d columns, %d rows",
                csvfilename,
                len(stackdata.columns),
                len(stackdata),
            )
            # TODO: For blocks, split into i,j,k, and remove integer block indices.


def get_eclbasename(hint=None):
    """Locate the Eclipse DATA file that we should process

    If only a single DATA file is in eclipse/model, then it is easy

    If there are multiple, we will exclude NOSIM, unless a hint is provided.

    A hint is any string that occurs in the filename for *DATA

    Args:
        hint (str): A string that is used as a search string in the DATA filename
    Returns:
        str: A filename including *DATA
    """
    datafiles = glob.glob("eclipse/model/*DATA")
    if len(datafiles) == 1:
        return datafiles[0]

    # Wash the globbed results
    datafiles = [datafile for datafile in datafiles if "NOSIM" not in datafile]
    if len(datafiles) == 1:
        if hint is not None:
            if hint not in datafiles[0]:
                logger.error(
                    "You wanted eclbase similar to %s, but could only find %s",
                    str(hint),
                    str(datafiles[0]),
                )
                # continuing, the user will have to pick up this error.
        return datafiles[0]

    if hint is not None:
        datafiles = [datafile for datafile in datafiles if hint in datafile]
        if len(datafiles) == 1:
            return datafiles[0]

    logger.error(
        (
            "Can't decide DATA file among {}, check the "
            "--eclbase command line option"
        ).format(str(datafiles))
    )
    sys.exit(1)


def parse_config(yamlfile):
    """Parse a yaml file with configuration for how to do postprocessing

    Currently it just uses yaml directly, but exposes the result as a
    namespace object to facilitate conversion to ConfigSuite

    Args:
        yamlfile (str)

    Returns:
        Namespace object  (but only namespace at the first level
    """
    config = yaml.safe_load(open(yamlfile))

    class Dict2namespace(object):
        def __init__(self, some_dict):
            self.__dict__.update(some_dict)

        def __contains__(self, key):
            return key in self.__dict__

    return Dict2namespace(config)


def main():
    parser = get_parser()
    args = parser.parse_args()

    if args.verbose:
        print("Setting info log level")
        logger.setLevel(logging.INFO)

    if not os.path.exists(args.runpath):
        logger.error("Directory %s does not exist", args.runpath)
        sys.exit(1)
    if not os.path.isdir(args.runpath):
        logger.error("%s must be a directory", args.runpath)

    os.chdir(args.runpath)

    if not os.path.exists("parameters.txt"):
        logger.warning("No parameters.txt found, is this really a runpath?")

    prepare_share_dir(".")

    if args.config:
        config = yaml.safe_load(args.config)
    else:
        config = None

    process_rms_volumetrics(config=config)

    eclbasename = get_eclbasename(hint=args.eclbase)
    process_ecl2df(eclbasename)
    print("Done on runpath: " + args.runpath)


if __name__ == "__main__":
    main()
