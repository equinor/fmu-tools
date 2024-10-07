"""Fix RMS Python script file extensions and gather useful information"""

import argparse
import logging
import os
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

_logger = logging.getLogger(__name__)


_BEGIN_HEADER = "Begin GEOMATIC file header"
_END_HEADER = "End GEOMATIC file header"
_BEGIN_PARAM = "Begin parameter"
_END_PARAM = "End parameter"


def _get_parser() -> argparse.ArgumentParser:
    """Set up a parser for the command line utility"""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "path",
        type=str,
        help=("Path to the RMS project"),
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Print logging information, a list of Python scripts that are "
        "are not used in any RMS workflow, and a list of Python scripts that"
        " do not have PEP8 compliant filenames.",
    )
    parser.add_argument(
        "-b",
        "--backup",
        action="store_true",
        help="Make a backup of the pythoncomp/ directory before doing anything",
    )
    parser.add_argument(
        "-t",
        "--test-run",
        action="store_true",
        help="Do a test run without making any file changes. Prints verbose "
        "information about the changes that will be made without making them.",
    )
    return parser


class PythonCompMaster:
    """The PythonCompMaster class parses a .master specific to those
    found in an RMS pythoncomp/ directory. These .master files are
    structured as so::

        Begin GEOMATIC header
        End GEOMATIC header
        Begin ParentParams object
            PSJParams object
            PSJParams object
            ...
        End ParentParams object

    Each PSJParams object points to a Python script, and these objects
    are referenced in the root .master file if and when they are
    included in a workflow. PSJParams objects are stored like so:

    Begin parameter
    id                                      = PSJParams
    instance_name                           = script_name_in_rms.py
    elapsedrealtime                         = 2.5200000405311584e-01
    elapsedcputime                          = 0.0000000000000000e+00
    tableoffset                             = 0
    description.size                        = 0
    opentime                                = 2022-12-20 07:18:38:766
    identifier                              = 000000...fdbea80000022f
    changeuser                              = msfe
    changetime                              = 2022-12-20 07:19:32:244
    standalonefilename                      = script_name_in_rms.py_1
    End parameter

    where the

    - `instance_name` is the filename displayed in RMS,
    - `standalonefilename` is the filename as stored on disk,
    - `identifier` is a 384-bit string that looks like a hash, but
       frequently increments by one bit sequentially

    The `instance_name` and `standalonefilename` can become out of
    sync, and the `standalonefilename` in particular can frequently be
    given a `.py_1` extension rather than a `.py` extension.

    This class offers methods to collect and correct these degenerate
    filenames.
    """

    def __init__(self, path: Union[str, Path], write: Optional[bool] = True) -> None:
        self._write = write
        _logger.info(f"File writing set to {self._write}")
        _path = Path(path)
        self._root = _path / ".master"
        if not self._root.exists():
            raise FileNotFoundError("Invalid path, root .master file does not exist")

        self._path = _path / "pythoncomp" / ".master"
        if not self._path.exists():
            raise FileNotFoundError(
                "Invalid path, pythoncomp/.master file does not exist"
            )

        lock_file = _path / "project_lock_file"
        if lock_file.exists():
            raise RuntimeError("project_lock_file exists, make sure RMS is closed")

        self._parent = self._path.parent
        self._parse(self._path)

    def _parse(self, path: Union[str, Path]) -> None:
        """Parses a pythoncomp/.master file. Results are stored internally."""
        with open(path, encoding="utf-8") as fin:
            lines = [line.strip() for line in fin.readlines()]

        try:
            header_start = lines.index(_BEGIN_HEADER)
            header_end = lines.index(_END_HEADER)
        except ValueError as exc:
            raise ValueError("Invalid pythoncomp/.master file") from exc

        if header_start != 0 or header_start >= header_end:
            raise ValueError("Invalid pythoncomp/.master file")

        self._header = self._params_to_dict(lines[1:header_end])
        inner_params = self._parse_parentparams(lines[header_end + 1 :])
        self._entries = self._parse_psjparams(inner_params)

    def _parse_parentparams(self, params: List[str]) -> List[str]:
        """Parses a ParentParams object in a pythoncomp/.master file.

        This object is essentially a wrapper object around all of the
        PSJParams objects. It does not seem to store any relevant or
        important metadata itself.
        """
        if params[0].strip() != _BEGIN_PARAM:
            raise ValueError(
                'Invalid pythoncomp/.master file (missing "Begin parameter" header)'
            )

        key, val = tuple(params[1].split("=", maxsplit=1))
        key, val = key.strip(), val.strip()
        if key != "id":
            raise ValueError(
                'Invalid pythoncomp/.master file (param "id" not where expected)'
            )

        # All parameters should be grouped in a ParentParams object
        if val != "ParentParams":
            raise ValueError(
                'Invalid pythoncomp/.master file (param type is not "ParentParams")'
            )
        start = params[1:].index(_BEGIN_PARAM)
        return params[start:-1]

    def _parse_psjparams(self, params: List[str]) -> Dict[str, Dict[str, str]]:
        """Parses the list of PSJParams lines from the .master file into a
        list of dictionaries, where each dictionary represents the values
        of the PSJParams object, plus an added `path` entry to its on-disk
        location.
        """
        entries: Dict[str, Dict[str, str]] = {}
        start, end = self._param_begin_end(params)
        while start != -1:
            entry = self._params_to_dict(params[start:end])
            if entry["id"] != "PSJParams":
                raise ValueError(
                    "Invalid pythoncomp/.master file"
                    f" ({entry['id']} found where only PSJParams expected)"
                )

            entry["path"] = str(self._parent / entry["standalonefilename"])

            iname = entry["instance_name"]
            if iname in entries:
                raise ValueError(
                    "Invalid pythoncomp/.master file"
                    f" (found duplicate instance_name: {iname}, aborting)"
                )
            entries[iname] = entry
            params = params[end + 1 :]
            start, end = self._param_begin_end(params)

        _logger.info(f"Found {len(entries)} Python entries")
        return entries

    def _param_begin_end(self, params: List[str]) -> Tuple[int, int]:
        """Inspects the given list for the nearest `Begin parameter` and
        `End parameter` demarcation of a PSJParams parameter object, and
        returns their index (or -1 if not there).
        """
        try:
            start = params.index(_BEGIN_PARAM) + 1
        except ValueError:
            start = -1
        try:
            end = params.index(_END_PARAM)
        except ValueError:
            end = -1

        if start > end:
            raise ValueError(
                "Invalid pythoncomp/.master file"
                " (Begin/End parameter unmatched or out of order)"
            )
        return start, end

    def _params_to_dict(self, lines: List[str]) -> Dict[str, str]:
        """Converts the list of lines representing a single PSJParams
        object into a dictionary containing its values.
        """
        split_lines = [line.split("=", maxsplit=1) for line in lines]
        tuple_lines = [(line[0].strip(), line[1].strip()) for line in split_lines]
        return dict(tuple_lines)

    def _will_overwrite_file(self, iname: str) -> bool:
        """Checks if there exists a filename on-disk with a name equivalent
        to the provided `instance_name`. If so, we cannot safely fix this
        Python script to have equivalent names in RMS and on-disk without
        overwriting a file.
        """
        fname = self._parent / iname
        return fname.exists()

    def _fix_bad_overwrite(self, iname: str) -> bool:
        """Tries to resolve an overwrite issue of the following form:

        Entry A:
            instance_name:      a.py
            standalonefilename: a.py_1

        Entry B:
            instance_name:      b.py
            standalonefilename: a.py

        With A, we want to move the standalonefilename to `a.py` but
        in doing so we'd overwrite B's standalonefilename script on
        disk. So, we recursively try to fix B's on-disk file
        first (and hope it doesn't suffer from the same issue).
        """
        blocking_entry = None
        for entry in self._entries.values():
            if entry["standalonefilename"] == iname:
                blocking_entry = entry["instance_name"]
                break

        # Something is not right here, bail out
        if blocking_entry is None:
            return False

        # Entry has a blocking file, but we make a recursive call to try
        # and resolve it. This should fix all forward blockers unless the
        # state of files on disk has gone wrong (e.g. some file got
        # deleted)
        if (
            self._will_overwrite_file(blocking_entry) is True
            and self._fix_bad_overwrite(blocking_entry) is False
        ):
            return False

        self._update_file_on_disk(blocking_entry)
        return True

    def _update_file_on_disk(self, iname: str) -> None:
        """Updates the filename on disk to the instance_name in RMS, as
        well as its dict representation.
        """
        new_path = str(self._parent / iname)
        if self._write is True:
            os.rename(self._entries[iname]["path"], new_path)
        _logger.info(f"Moved {self._entries[iname]['path']} to {new_path}")
        self._entries[iname]["standalonefilename"] = self._entries[iname][
            "instance_name"
        ]
        self._entries[iname]["path"] = new_path

    @property
    def parent(self) -> str:
        """Path to the pythoncomp/ directory"""
        return str(self._parent)

    @property
    def path(self) -> str:
        """Path to the pythoncomp/.master file"""
        return str(self._path)

    @property
    def header(self) -> Dict[str, str]:
        """The dict representing the GEOMATIC header of the .master file."""
        return self._header

    @property
    def entries(self) -> Dict[str, Dict[str, str]]:
        """The list of Python file entries"""
        return self._entries

    def get_inconsistent_entries(self) -> List[str]:
        """Inspects all Python entries for Python scripts that have an
        `instance_name` that differs from its `standalonefilename`, i.e.
        the RMS name does not match the name of the file on disk.
        """
        f = (  # noqa
            lambda k: self._entries[k]["instance_name"]
            != self._entries[k]["standalonefilename"]
        )
        return list(filter(f, self._entries.keys()))

    def get_invalid_extensions(self) -> List[str]:
        """Inspects all Python entries for Python scripts that have a
        non-standard file extension (not `.py`) on disk. Frequently this
        means they are `.py_1` but other variations exist (or occasionally
        there is no file extension at all).
        """
        f = (  # noqa
            lambda k: self._entries[k]["standalonefilename"].endswith(".py") is False
        )
        return list(filter(f, self._entries.keys()))

    def get_invalid_instance_names(self) -> List[str]:
        """Inspects all Python entries for Python scripts that have a
        non-standard file extension (not `.py`) in RMS.
        """
        f = lambda k: self._entries[k]["instance_name"].endswith(".py") is False  # noqa
        return list(filter(f, self._entries.keys()))

    def get_pep8_noncompliant(self) -> List[str]:
        """Returns a list of instance names that are not PEP8 compliant."""

        def _noncompliant_pep8(iname):
            return (
                any(c.isupper() for c in iname)
                or iname[0].isdigit()
                or any(c == "-" for c in iname)
            )

        return list(filter(_noncompliant_pep8, self._entries.keys()))

    def get_nonexistent_standalonefilenames(self) -> List[str]:
        """Inspects all Python entries for Python scripts that have a
        non-existent file. Assumes the path is up-to-date and correct.
        """
        f = lambda k: Path(self._entries[k]["path"]).exists() is False  # noqa
        return list(filter(f, self._entries.keys()))

    def get_unused_scripts(self) -> List[str]:
        """Returns a list of Python scripts that aren't used in any workflow."""
        main_master = self._parent.parent / ".master"
        with open(main_master, "r", encoding="utf-8") as fin:
            lines = [
                line.strip().split(" = ", maxsplit=1)[-1] for line in fin.readlines()
            ]
        unused = []
        for entry in self._entries:
            if entry not in lines:
                unused.append(entry)
        return unused

    def get_entry(self, iname: str) -> Dict[str, str]:
        """Returns an entry reference by its iname"""
        return self._entries[iname]

    def fix_standalone_filenames(self) -> List[str]:
        """Attempts to fix the Python files on disk that are inconsistent
        with the files in RMS. This fix is rather simple and just copies
        the `instance_name` to be the `standalonefilename` under the
        presumption that RMS will have prevented someone from making
        duplicate instance names. This might be an unreasonable assumption
        given the necessity of this script in the first place.

        If the names in RMS do not have a Python extension we skip them
        rather than try to figure it out.
        """
        invalid_inames = self.get_invalid_instance_names()
        for iname in invalid_inames:
            self._entries[iname]["skipped"] = "instance_name in RMS does not end in .py"

        nonexistent_fnames = self.get_nonexistent_standalonefilenames()
        for iname in nonexistent_fnames:
            self._entries[iname]["skipped"] = "standalonefilename does not exist!"

        skip = invalid_inames + nonexistent_fnames
        _logger.info(f"Skipping {len(skip)} entries")

        entries = self.get_inconsistent_entries()
        _logger.info(f"Found {len(entries)} inconsistent entries")
        for iname in entries:
            if (
                iname in skip
                or self._entries[iname]["instance_name"]
                == self._entries[iname]["standalonefilename"]
            ):
                # We may have forward-fixed an entry already when resolving
                # an overwrite error
                continue

            if (
                self._will_overwrite_file(iname) is True
                and self._fix_bad_overwrite(iname) is False
            ):
                self._entries[iname]["skipped"] = (
                    "fixing will overwrite non-identical file"
                )
                skip.append(iname)
            else:
                self._update_file_on_disk(iname)

        return skip

    def write_master_file(self) -> None:
        """Writes the fixed .master file out, with a non-optional backup."""
        if not self._write:
            _logger.info("Skipped writing .master")
            return

        os.rename(self._path, self._parent / "backup.master")
        _logger.info("Backed-up .master as backup.master")
        # .master files align the values to keys at the 40th character
        fstr = "{0:<40}= {1}\n"
        with open(self._path, "w", encoding="utf-8") as fout:
            # GEOMATIC header
            fout.write(f"{_BEGIN_HEADER}\n")
            for key, val in self._header.items():
                fout.write(fstr.format(key, val))
            fout.write(f"{_END_HEADER}\n")

            # Begin ParentParams
            fout.write(f"{_BEGIN_PARAM}\n")
            fout.write(fstr.format("id", "ParentParams"))
            fout.write(fstr.format("instance_name", ""))
            # All PSJParams
            for entry in self._entries.values():
                fout.write(f"{_BEGIN_PARAM}\n")
                for key, val in entry.items():
                    if key in ("path", "skipped"):
                        continue
                    # The elapsed runtimes end with a space in original file
                    if key.startswith("elapsed"):
                        val += " "
                    fout.write(fstr.format(key, val))
                fout.write(f"{_END_PARAM}\n")
            # End ParentParams
            fout.write(f"{_END_PARAM}\n")
        _logger.info("Wrote new .master")


def _make_backup(parent: str) -> None:
    dir_name = Path(parent).name
    _logger.info(f"Making a copy of pythoncomp/ as backup_{dir_name}")
    shutil.copytree(parent, f"backup_{dir_name}", symlinks=True)
    print(f"Backed up {parent} as backup_{dir_name}")


def _print_skipped(skipped: List[str], master: PythonCompMaster) -> None:
    print("Skipped the following Python script(s):")
    for iname in skipped:
        entry = master.get_entry(iname)
        print(
            f"""
- instance_name:      {entry["instance_name"]}
- standalonefilename: {entry["standalonefilename"]}
- reason:             {entry["skipped"]}
"""
        )


def _print_unused(unused: List[str], master: PythonCompMaster) -> None:
    print(
        "The following file(s) are included in the RMS project"
        " but do not appear to be used in any workflow"
    )
    for iname in unused:
        entry = master.get_entry(iname)
        print(
            f"""
- instance_name:      {entry["instance_name"]}
- standalonefilename: {entry["standalonefilename"]}
"""
        )
    print(
        "They must be manually deleted from within RMS. Be sure to double-check them."
    )


def _print_pep8(noncompliant: List[str], master: PythonCompMaster) -> None:
    print("The following file(s) have PEP8 non-compliant instance name(s)")
    for iname in noncompliant:
        entry = master.get_entry(iname)
        print(
            f"""
- instance_name:      {entry["instance_name"]}
- standalonefilename: {entry["standalonefilename"]}
"""
        )
    print("They must be changed in RMS to all lowercase, no hyphen, no number names.")


def main() -> None:
    parser = _get_parser()
    args = parser.parse_args()

    logging.basicConfig()

    if args.verbose or args.test_run:
        _logger.setLevel(logging.INFO)

    # Don't write files if it's a test run
    master = PythonCompMaster(args.path, write=not args.test_run)

    if args.backup:
        _make_backup(master.parent)

    skipped = master.fix_standalone_filenames()
    master.write_master_file()
    _print_skipped(skipped, master)

    if args.verbose or args.test_run:
        unused = master.get_unused_scripts()
        _print_unused(unused, master)

        noncompliant = master.get_pep8_noncompliant()
        _print_pep8(noncompliant, master)


if __name__ == "__main__":
    main()
