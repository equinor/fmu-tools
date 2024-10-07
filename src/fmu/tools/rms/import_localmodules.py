"""Import a local module made inside RMS, and refresh the content."""

import importlib
import logging
import shutil
import sys
import tempfile
import warnings
from os.path import join
from pathlib import Path
from typing import no_type_check

logger = logging.getLogger(__name__)


@no_type_check
def _detect_pyfile(path, module_root_name):
    """A module shall be named ``*.py``, but may have different 'actual' name in RMS.

    Returns:
        actual_file: e.g. mymodule_name_ondisk.py_1
        module: e.g. name_seen_in_rms.py
    """

    usepath = Path(path)
    proposed = [
        usepath / (module_root_name + ".py"),
        usepath / (module_root_name + ".py_1"),
        usepath / (module_root_name + ".py_2"),
        usepath / (module_root_name),
    ]

    for proposal in proposed:
        logger.info("Look for %s", proposal)
        if proposal.is_file():
            logger.info("-> Found %s", proposal)
            if ".py" not in proposal.name:
                warnings.warn(
                    "Warning: Please avoid modules without a .py ending!", UserWarning
                )
            return proposal, module_root_name + ".py"

    return None, None


@no_type_check
def _detect_module_or_package(path, module_root_name):
    """Detect a module of package external of rms."""

    usepath = Path(path)

    if (usepath / (module_root_name + ".py")).is_file():
        # module is a single file
        return True

    return (usepath / module_root_name / "__init__.py").is_file()


@no_type_check
def _localmodule_inside_rms(project, module_root_name):
    """Import a library module in RMS which exists inside the RMS project."""

    if isinstance(project, str):
        # allow project to be a string; mostly for unit testing
        prj = project
    else:
        try:
            prj = project.filename
        except AttributeError as err:
            raise RuntimeError(
                "The project object is invalid, perhaps not inside RMS?"
            ) from err

    mypath = prj + "/pythoncomp"

    actualfile, module = _detect_pyfile(mypath, module_root_name)

    if not actualfile:
        raise ValueError(f"Cannot detect module {module_root_name}. Check spelling etc")

    # Now empty sys.path for this module, allowing a refresh when library is modified:
    sysm = sys.modules.copy()
    for key, val in sysm.items():
        if module in str(val):
            logger.info("Delete from modules: %s", key)
            del sys.modules[key]

    # since modules in RMS may have invalid endings; copy to a tempfile instead
    # with correct name, and let that part be in sys.path temporarily
    with tempfile.TemporaryDirectory() as tmpdirname:
        sys.path.insert(0, tmpdirname)
        fname = shutil.copy(actualfile, join(tmpdirname, module))
        logger.info("Using tmp file: %s", fname)

        xmod = importlib.import_module(module_root_name)
        sys.path.pop(0)  # avoid accumulation in sys.path by removing tmppath from stack
        return xmod


@no_type_check
def _localmodule_outside_rms(module_root_name, path):
    """Import a library module in RMS which exists outside the RMS project."""

    if not _detect_module_or_package(path, module_root_name):
        raise ValueError(f"Cannot detect module {module_root_name}. Check spelling etc")

    # Now empty sys.path for this module, allowing a refresh when library is modified:
    sysm = sys.modules.copy()
    for key, val in sysm.items():
        if module_root_name in key:
            logger.info("Delete from modules: %s", key)
            del sys.modules[key]

    sys.path.insert(0, path)

    xmod = importlib.import_module(module_root_name)

    sys.path.pop(0)  # avoid accumulation in sys.path
    return xmod


@no_type_check
def import_localmodule(project, module_root_name, path=None):
    """Import a library module in RMS which exists either inside or outside RMS.

    Inside a RMS project it can be beneficial to have a module that serves as a library,
    not only a front end script. Several problems exist in current RMS:

        - RMS has no awareness of this 'PYTHONPATH', i.e. <project>/pythoncomp
        - RMS will, once loaded, not refresh any changes made in the module
        - Python requires extension .py, but RMS often adds .py_1 for technical reasons,
          which makes it impossible for the end-user to understand why it will not work,
          as the 'instance-name' (script name inside RMS) and the actual file name will
          differ.

    This function solves all these issues, and makes it possible to import a RMS project
    library in a much easier way::

        import fmu.tools as tools

        # mylib.py is inside the RMS project
        plib = tools.rms.import_localmodule(project, "mylib")

        plib.somefunction(some_arg)

        # exlib.py is outside the RMS project e,g, at ../lib/exlib.py
        elib = tools.rms.import_localmodule(project, "exlib", path="../lib")

        elib.someotherfunction(some_other_arg)

    Args:
        project: RMS 'magic' project variable
        module_root_name: A string that is the root name of your module. E.g. if
            the module is named 'blah.py', the use 'blah'.
        path: If None then it will use a module seen from RMS, being technically stored
            in pythoncomp folder. If set, then it should be a string for the file path
            and load a module stored outside RMS.

    """
    if not path:
        return _localmodule_inside_rms(project, module_root_name)
    return _localmodule_outside_rms(module_root_name, path)
