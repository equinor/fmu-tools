"""Test code for rms local module function."""
import os

import pytest

import fmu.tools

SNIPPET1 = """
def add(a, b):
    return(a + b)

def say_hello(name):
    return(f"Hello {name}")
"""


@pytest.mark.parametrize(
    "modulename, shall_fail",
    [
        ("mymod.py", False),
        ("mymod.py_1", False),
        ("mymod", False),
        ("invalid_name", True),
    ],
)
def test_rms_import_localmodule(tmp_path, modulename, shall_fail):
    """Test import of a module via rms.import_localmodule."""

    pycomp = tmp_path / "myproject" / "pythoncomp"
    print(pycomp)
    pycomp.mkdir(parents=True)

    os.chdir(pycomp)
    with open(modulename, "w") as stream:
        stream.write(SNIPPET1)
    os.chdir(pycomp.parent)

    fake_project = os.getcwd()

    if not shall_fail:
        mylib = fmu.tools.rms.import_localmodule(fake_project, "mymod")
        id1 = id(mylib)

        assert mylib.add(3, 4) == 7
        assert mylib.say_hello("world") == "Hello world"

        id1 = id(mylib)
        id2 = id(fmu.tools.rms.import_localmodule(fake_project, "mymod"))
        assert id1 != id2
    else:
        with pytest.raises(ValueError, match="Cannot detect module"):
            mylib = fmu.tools.rms.import_localmodule(fake_project, "mymod")


def test_rms_import_invalid_name(tmp_path):
    """Test import of a module that is invalid."""

    pycomp = tmp_path / "myproject" / "pythoncomp"
    print(pycomp)
    pycomp.mkdir(parents=True)

    os.chdir(pycomp)
    with open("mymod.py", "w") as stream:
        stream.write(SNIPPET1)
    os.chdir(pycomp.parent)

    fake_project = object()
    with pytest.raises(Exception, match=r"The project object is invalid"):
        _ = fmu.tools.rms.import_localmodule(fake_project, "mymod")
