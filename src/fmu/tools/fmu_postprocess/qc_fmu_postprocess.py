import os
import glob
import argparse
import logging

# import configsuite
from fmu import ensemble

DESCRIPTION = """
FMU postprocessing script.

Depends on the accompanying forward model script

    fm_fmu_postprocessing.py

to have been run in each realization.

This particular workflow script will do the ensemble aggregations for the
data we want, and dump to <casedir>/share/results on /scratch.
Data is fetched from <casedir>/realization-*/iter-*/share/results

If multiple ensemblesets are aggregated by supplying more than one
case on the command line, a new "casedir" bearing the combination of the
casedirnames will be created, and have the share dir populated.
"""

logger = logging.getLogger(__name__)
logging.basicConfig()

DEFAULT_REAL_DATA = (
    ["share/results/tables/*csv", "share/results/volumes/*csv", "gendata_rft.csv"],
)


def get_parser():
    """Setup parser for command line utility"""

    parser = argparse.ArgumentParser(description=DESCRIPTION)
    parser.add_argument(
        "casedirs",
        type=str,
        nargs="+",
        help="Directories containing EnsembleSets (cases)",
    )
    parser.add_argument(
        "--share",
        type=str,
        default=None,
        help=(
            "Where should we put the share directory with "
            "aggregated data. Default is in casedir, "
            "but set this if you have multiple casedirs."
        ),
    )
    return parser


def prepare_share_dir(casedirs, share=None):
    """Prepare and create a share directory for output, computed
    from the case directory nnames.

    Args:
        casedirs (list of str), one or more casedirectories,
            each containing an EnsembleSet
        share (str): If not None, this will override the automatically
            computed dir from casedirs

    Returns:
        str: path to a directory that is guaranteed to exist (but may
            not be empty)
    """
    if len(casedirs):
        if share is None:
            # If multiple cases, and no --share supplied, do something smart
            # Strip away path part:
            casedirs = [c.split(os.path.sep)[-1] for c in casedirs]
            if len(casedirs) != len(set(casedirs)):
                logger.error("Repeating casedir names, supply --share manually")
                raise ValueError
            sharedir = "./" + "_".join(casedirs) + "/share"
        else:
            sharedir = share + "/share"
    else:
        if share is not None:
            sharedir = casedirs[0] + "/share"

    ensure_directory_exists(sharedir + os.path.sep)
    ensure_directory_exists(os.path.join(sharedir, "results") + os.path.sep)
    ensure_directory_exists(os.path.join(sharedir, "results", "tables") + os.path.sep)
    ensure_directory_exists(os.path.join(sharedir, "results", "volumes") + os.path.sep)

    return sharedir


def build_ensemble_dir_list(casedirs):
    """Build an EnsembleSet object from the casedirs.

    Usually a casedir is an individual EnsembleSet, with the ensembles
    iter-0, iter-1, pred etc, but to support multiple casedirs,
    each ensemble-name will be prefixed with a string from the casedir-name.

    Args:
        casedirs (list of str)

    Returns:
        dict. key is a name of an ensemble, and value is the wildcard path
            to the ensemble, like foo/bar/myensemble/realization-*/iter-4,
            corresponding to a key myensemble_iter-4
    """
    ensemble_dirs = {}
    for casedir in casedirs:

        # Strip potential trailing slash from casedir
        # this could come from bash tab-completion
        if casedir[-1] == os.path.sep:
            casedir = casedir[:-1]

        # Get the directory name (strip parent directory names)
        ens_name_prefix = casedir.split(os.path.sep)[-1] + "_"
        # (to be used in the ENSEMBLE column)

        # Construct list of iter/pred directory names, search through all realizations:
        iterpreds = set(
            [
                os.path.split(realizationpath)[-1]
                for realizationpath in glob.glob(
                    os.path.join(casedir, "realization-*/*")
                )
            ]
        )
        for dirname in iterpreds:
            ensemble_dirs[ens_name_prefix + dirname] = os.path.join(
                casedir, "realization-*", dirname
            )

    return ensemble_dirs


def find_realization_data(realization_globs, ensemble_dirs):
    """Glob through realizations in ensembles looking for filenames
    that match. Use this to determine the list of files
    that exist in any ensemble/realization"""

    file_list = []
    assert realization_globs
    if not isinstance(realization_globs, list):
        realization_globs = [realization_globs]

    for ensemble_dir in ensemble_dirs:
        for real_dir in glob.glob(ensemble_dir):
            for real_glob in realization_globs:
                globber = os.path.join(real_dir, real_glob)
                real_files = glob.glob(globber)
                file_list += [
                    real_file.replace(real_dir, "").lstrip(os.path.sep)
                    for real_file in real_files
                ]

    return list(set(file_list))


def build_ensemble_set(ensembledirs):
    ens_set = ensemble.EnsembleSet("dummy")
    for ens_name, ens_path in ensembledirs.items():
        try:
            ens = ensemble.ScratchEnsemble(ens_name, ens_path)
        except AttributeError:
            # when does this happen?
            # Should we catch more exceptions?
            pass
        if len(ens):
            ens_set.add_ensemble(ens)
    return ens_set


def check_casedirs(casedirs):
    """Fail if the provided casedirs do not exist or is not directories

    Args:
        casedirs (list of str): List of directories, absolute or relative
            to ERT cases. Not including realization-*/iter-*."""
    for casedir in casedirs:
        if not os.path.exists(casedir):
            logger.error("{} does not exist".format(casedir))
            raise IOError
        if not os.path.isdir(casedir):
            logger.error("{} is not a directory".format(casedir))
            raise ValueError


def prepare_results_dir(sharedir, resultdirname):
    """
    """
    assert len(resultdirname.split(os.path.sep)) == 1
    assert os.path.exists(sharedir)

    resultsdir = os.path.join(sharedir, "results")
    if not os.path.exists(resultsdir):
        os.makedirs(resultsdir)
    if not os.path.exists(os.path.join(resultsdir, "tables")):
        os.makedirs(os.path.join(resultsdir, "tables"))
    if not os.path.exists(os.path.join(resultsdir, "volumes")):
        os.makedirs(os.path.join(resultsdir, "volumes"))

    logger.info("Will write results to %s", str(resultsdir))
    return resultsdir


def ensure_directory_exists(filename):
    dirname = os.path.dirname(filename)
    if not os.path.exists(dirname):
        os.makedirs(dirname)


def main():
    parser = get_parser()
    args = parser.parse_args()

    sharedir = prepare_share_dir(args.casedirs, args.share)

    check_casedirs(args.casedirs)

    logger.info("Running on casedirs: %s", str(args.casedirs))

    resultsdir = prepare_results_dir(sharedir, "results")

    print(resultsdir)

    ensemble_dirs = build_ensemble_dir_list(args.casedirs)
    ens_set = build_ensemble_set(ensemble_dirs)

    # Determine a set of data to load from each realization.
    # When we ask for it here, it exists in at least one realization, but not
    # in all, and it might be missing in some ensembles altogheter, but that
    # we should handle
    realization_data = find_realization_data(
        DEFAULT_REAL_DATA[
            "share/results/tables/*csv", "share/results/volumes/*csv", "gendata_rft.csv"
        ],
        ensemble_dirs.values(),
    )

    # Load and merge everything we have found:
    for dataname in realization_data:
        try:
            if dataname.endswith(".csv"):
                ens_set.load_csv(dataname)
        except (ValueError, KeyError) as e_msg:
            logger.warning(e_msg)

    # Call plugin system to perturb loaded dataframes

    # Dump data to results dir
    logger.info("Sucessfully loaded data: %s", str(ens_set.keys()))

    # Now resultsdir and the internal fmu-ensemble filenames overlap in "share/results"
    resultsdir_short = resultsdir.replace("share/results", "")

    for dataname in set(realization_data).intersection(ens_set.keys()):
        if dataname.endswith(".csv"):
            csvfilename = os.path.join(resultsdir_short, dataname)
            logger.info("Writing %s", str(csvfilename))
            ensure_directory_exists(csvfilename)
            ens_set.get_df(dataname, merge="parameters.txt").to_csv(
                csvfilename, index=False
            )

    print("qc_fmu_postprocess: Done")


if __name__ == "__main__":
    main()
