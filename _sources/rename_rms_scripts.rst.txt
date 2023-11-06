rms.rename_rms_scripts
======================

A common annoyance in RMS projects is that RMS saves its Python scripts
on-disk with non-Python file extensions such as ``.py_1``, ``.py_2``, etc.
RMS also does not offer a way for users to see which Python scripts are
currently being used in a workflow, meaning that old or unused scripts can
unnecessarily add clutter to a project. This script, which must be invoked 
outside of RMS without RMS running, allows you to find and fix these things.

*This script will modify your RMS Python script file names and pythoncomp 
.master file!* Use with some caution, take a backup, but some safeguards 
are built in.

Usage
^^^^^

.. argparse::
  :module: fmu.tools.rms.rename_rms_scripts
  :func: _get_parser
  :prog: rename_rms_scripts
