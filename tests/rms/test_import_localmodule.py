"""Test code for rms local module function."""

import os
import sys

import pytest

import fmu.tools.rms as toolsrms
from fmu.tools._common import preserve_cwd

SNIPPET1 = """
def add(a, b):
    return(a + b)

def say_hello(name):
    return(f"Hello {name}")
"""


@preserve_cwd
@pytest.mark.skipif(sys.version_info > (3, 11), reason="Fails in Python 3.12")
@pytest.mark.parametrize(
    "modulename, shall_warn, shall_fail",
    [
        ("mymod.py", False, False),
        ("mymod.py_1", False, False),
        ("mymod", True, False),
        ("invalid_name", False, True),
    ],
)
def test_rms_import_localmodule(tmp_path, modulename, shall_warn, shall_fail):
    """Test import of a module via rms.import_localmodule."""
    pycomp = tmp_path / "myproject" / "pythoncomp"
    pycomp.mkdir(parents=True)

    os.chdir(pycomp)
    with open(modulename, "w", encoding="utf-8") as stream:
        stream.write(SNIPPET1)
    os.chdir(pycomp.parent)

    fake_project = os.getcwd()

    if not shall_fail:
        if shall_warn:
            with pytest.warns(UserWarning, match="Please avoid modules without"):
                mylib = toolsrms.import_localmodule(fake_project, "mymod")
        else:
            mylib = toolsrms.import_localmodule(fake_project, "mymod")
            id1 = id(mylib)

            assert mylib.add(3, 4) == 7
            assert mylib.say_hello("world") == "Hello world"

            id1 = id(mylib)
            id2 = id(toolsrms.import_localmodule(fake_project, "mymod"))
            assert id1 != id2
    else:
        with pytest.raises(ValueError, match="Cannot detect module"):
            mylib = toolsrms.import_localmodule(fake_project, "mymod")


@preserve_cwd
def test_rms_import_invalid_name(tmp_path):
    """Test import of a module that is invalid."""

    pycomp = tmp_path / "myproject" / "pythoncomp"
    pycomp.mkdir(parents=True)

    os.chdir(pycomp)
    with open("mymod.py", "w", encoding="utf-8") as stream:
        stream.write(SNIPPET1)
    os.chdir(pycomp.parent)

    fake_project = object()
    with pytest.raises(Exception, match=r"The project object is invalid"):
        _ = toolsrms.import_localmodule(fake_project, "mymod")


@preserve_cwd
def test_rms_import_ex1_localmodule_external_single(tmp_path):
    """Test import of a external (file) module via rms.import_localmodule."""

    myproj = tmp_path / "ex1" / "myproject1"
    myproj.mkdir(parents=True)
    extlib = myproj / ".." / "otherlib"
    extlib.mkdir(parents=True)

    os.chdir(extlib)
    with open("some.py", "w", encoding="utf-8") as stream:
        stream.write(SNIPPET1)

    os.chdir(myproj)

    fake_project = "dummy"

    mylib = toolsrms.import_localmodule(fake_project, "some", path="../otherlib")

    assert mylib.add(3, 4) == 7
    assert mylib.say_hello("world") == "Hello world"


@preserve_cwd
def test_rms_import_ex2_localmodule_external_package(tmp_path):
    """Test import of a external (package) module via rms.import_localmodule."""

    myproj = tmp_path / "ex2" / "myproject2"
    myproj.mkdir(parents=True)
    extlib = myproj / ".." / "lib" / "mypackage"
    extlib.mkdir(parents=True)

    os.chdir(extlib)
    with open("mymod.py", "w", encoding="utf-8") as stream:
        stream.write(SNIPPET1)

    with open("__init__.py", "w", encoding="utf-8") as stream:
        stream.write("from . import mymod")

    os.chdir(myproj)

    fake_project = "dummy"

    mylib = toolsrms.import_localmodule(fake_project, "mypackage", path="../lib")

    assert mylib.mymod.add(3, 4) == 7
    assert mylib.mymod.say_hello("world") == "Hello world"

    mylib = toolsrms.import_localmodule(fake_project, "mymod", path="../lib/mypackage")

    assert mylib.add(3, 4) == 7
    assert mylib.say_hello("world") == "Hello world"
