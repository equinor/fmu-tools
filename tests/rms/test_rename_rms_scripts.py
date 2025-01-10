import logging
from filecmp import cmp
from os import chdir, listdir
from pathlib import Path
from shutil import copytree
from textwrap import dedent

import pytest

from fmu.tools._common import preserve_cwd
from fmu.tools.rms.rename_rms_scripts import PythonCompMaster, main

logging.basicConfig(level=logging.INFO)


TESTDIR = Path(__file__).parent / "rename_rms_scripts_data"
TESTPROJ = TESTDIR / "snakeoil.rms13.0.3"
EXPECTED = TESTDIR / "expected.snakeoil.rms13.0.3"


@pytest.fixture()
def project():
    return PythonCompMaster(TESTPROJ)


def test_invalid_project(tmp_path):
    """Raise if we can't be sure the project dir is an RMS project"""
    with pytest.raises(
        expected_exception=FileNotFoundError,
        match="Invalid path, root .master file does not exist",
    ):
        PythonCompMaster(tmp_path)


def test_missing_master(tmp_path):
    """Raise when pythoncomp/ has no .master to parse"""
    root_master = tmp_path / ".master"
    root_master.write_text("")
    pythoncomp = tmp_path / "pythoncomp"
    pythoncomp.mkdir()

    with pytest.raises(
        expected_exception=FileNotFoundError,
        match="Invalid path, pythoncomp/.master file does not exist",
    ):
        PythonCompMaster(tmp_path)


def test_lock_file(tmp_path):
    """Raise if an RMS lock files exists and it's not safe to make
    changes
    """
    root_master = tmp_path / ".master"
    root_master.write_text("")
    pythoncomp = tmp_path / "pythoncomp"
    pythoncomp.mkdir()
    python_master = pythoncomp / ".master"
    python_master.write_text("")

    lock_file = tmp_path / "project_lock_file"
    lock_file.write_text("")
    with pytest.raises(
        expected_exception=RuntimeError,
        match="project_lock_file exists, make sure RMS is closed",
    ):
        PythonCompMaster(tmp_path)


@pytest.mark.parametrize(
    "content",
    [
        "Begin GEOMATIC header file",
        "End GEOMATIC header file",
        "Begin GEOMATIC header file\nEnd GEOMATIC header file",
        "#comment\nBegin GEOMATIC header file",
        dedent(
            """Begin GEOMATIC header file
End GEOMATIC header file
Begin parameter
instance_name                           =
End parameter"""
        ),
        dedent(
            """Begin GEOMATIC header file
End GEOMATIC header file
Begin parameter
id                                      = PSJParams
instance_name                           =
End parameter"""
        ),
    ],
)
def test_invalid_master(tmp_path, content):
    """Some light (and probably unnecessary) checks that the PythonComp
    .master file is valid
    """
    root_master = tmp_path / ".master"
    root_master.write_text("")
    pythoncomp = tmp_path / "pythoncomp"
    pythoncomp.mkdir()
    master = pythoncomp / ".master"
    master.write_text(content)

    with pytest.raises(
        expected_exception=ValueError,
        match="Invalid pythoncomp/.master file",
    ):
        PythonCompMaster(tmp_path)


def test_header_parse(project):
    """Non-exhaustive checks that we parse the GEOMATIC header
    correctly.
    """
    assert "type" in project.header
    assert "name" in project.header
    assert project.header["type"] == "PythonComp"
    assert "fileversion" in project.header
    assert project.header["fileversion"] == "2021.0000"


def test_prop_parent(project):
    """Parent prop is correct"""
    assert project.parent == str(TESTPROJ / "pythoncomp")


def test_prop_path(project):
    """Path prop is correct"""
    assert project.path == str(TESTPROJ / "pythoncomp" / ".master")


def test_get_inconsistent_entries(project):
    """Entries with inconsistent instance_names and standalonefilenames are
    correctly found.
    """
    entries = project.get_inconsistent_entries()
    assert len(entries) == 5
    assert "b.py" in entries
    assert "c.py" in entries
    assert "d.py" in entries
    assert "e.py" in entries
    assert "f" in entries


def test_get_invalid_extensions(project):
    """Entries with non-.py file extensions are correctly found."""
    entries = project.get_invalid_extensions()
    assert len(entries) == 4
    assert "b.py" in entries
    assert "c.py" in entries
    assert "d.py" in entries
    assert "f" in entries


def test_get_invalid_instance_names(project):
    """Entries with a non-.py extension in their instance_name are
    found.
    """
    entries = project.get_invalid_instance_names()
    assert len(entries) == 1
    assert "f" in entries


def test_get_nonexistent_standalonefilenames(project):
    """Entries in the .master file, but which do not exist on disk."""
    entries = project.get_nonexistent_standalonefilenames()
    assert len(entries) == 0


def test_get_pep8_noncompliant(project):
    """Entries with a filename that contains a capital letter, a hyphen, or
    begin with a number.
    """
    entries = project.get_pep8_noncompliant()
    assert len(entries) == 1
    assert "PEP8.py" in entries


def test_get_unused_scripts(project):
    """Entries that are in the the pythoncomp/.master file but not use in a
    workflow.
    """
    entries = project.get_unused_scripts()
    assert len(entries) == 1
    assert "c.py" in entries


def test_get_entry(project):
    """Get the full dictionary representing a PSJParam entry."""
    with pytest.raises(expected_exception=KeyError):
        project.get_entry("fail.py")
    entry = project.get_entry("a.py")
    assert entry["instance_name"] == "a.py"
    assert entry["standalonefilename"] == "a.py"


def test_fix_standalone_filenames(tmp_path):
    """Fix the project and check the results."""
    project_path = tmp_path / "snakeoil.rms13.0.3"
    copytree(TESTPROJ, project_path)
    project = PythonCompMaster(project_path)
    skipped = project.fix_standalone_filenames()
    assert len(skipped) == 1
    assert "f" in skipped
    assert (
        project.get_entry("f")["skipped"] == "instance_name in RMS does not end in .py"
    )

    for entry in project.entries:
        if entry in skipped:
            continue
        e = project.get_entry(entry)
        assert e["instance_name"] == e["standalonefilename"]
        with open(e["path"], "r", encoding="utf-8") as f:
            code = f.read().strip()
        assert code == f'print("{entry.split(".")[0]}")'

    unfixed = project.get_inconsistent_entries()
    assert len(unfixed) - len(skipped) == 0
    assert "f" in unfixed


def test_no_write_master_file(tmp_path):
    """Make sure no changes are written when we pass write=False"""
    project_path = tmp_path / "snakeoil.rms13.0.3"
    copytree(TESTPROJ, project_path)
    project = PythonCompMaster(project_path, write=False)
    project.fix_standalone_filenames()
    project.write_master_file()

    assert cmp(TESTPROJ / ".master", Path(project.parent).parent / ".master") is True
    orig_py = TESTPROJ / "pythoncomp"
    assert cmp(orig_py / ".master", project.path) is True

    assert set(listdir(orig_py)) == set(listdir(project.parent))


def test_write_master_file(tmp_path):
    """Make sure we output a correct .master file, and compare all other
    files with the expected test data.
    """
    project_path = tmp_path / "snakeoil.rms13.0.3"
    copytree(TESTPROJ, project_path)
    project = PythonCompMaster(project_path)
    project.fix_standalone_filenames()
    project.write_master_file()

    assert cmp(EXPECTED / ".master", Path(project.parent).parent / ".master") is True
    exp_py = EXPECTED / "pythoncomp"
    assert cmp(exp_py / ".master", project.path) is True

    assert set(listdir(exp_py)) == set(listdir(project.parent))


def test_cmdline_main(tmp_path, mocker):
    """Test the cmndline utility runs without errors. Both with and
    without test-run option.
    """
    project_path = tmp_path / "snakeoil.rms13.0.3"
    copytree(TESTPROJ, project_path)

    mocker.patch("sys.argv", ["rename_rms_scripts", str(project_path)])
    main()

    mocker.patch("sys.argv", ["rename_rms_scripts", str(project_path)], "--test-run")
    main()


@preserve_cwd
def test_cmdline_main_backup(tmp_path, mocker):
    """Test the backup of the pythoncomp through the cmndline."""
    project_path = tmp_path / "snakeoil.rms13.0.3"
    copytree(TESTPROJ, project_path)

    # change directory to store the backup in the tmp_path
    chdir(tmp_path)

    mocker.patch("sys.argv", ["rename_rms_scripts", str(project_path), "--backup"])
    main()

    # check that the backup exists
    assert (tmp_path / "backup_pythoncomp").exists()
