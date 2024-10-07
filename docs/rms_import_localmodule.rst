rms.import_localmodule
======================

Inside the RMS project it can be beneficial to have a module that serves as a library,
not only a front end script. Several problems exist in current RMS

* RMS has no awareness of this 'PYTHONPATH', i.e. <project>/pythoncomp
* RMS will, once loaded, not refresh any changes made in the module
* Python requires extension .py, but RMS often adds .py_1 for technical reasons,
  which makes it impossible for the end-user to understand why it will not work,
  as the 'instance-name' (script name inside RMS) and the actual file name will
  differ.

This function solves all these issues, and makes it possible to import a RMS project
library in a much easier way.


The library is inside rms
-------------------------

Given that the library module is made inside the RMS GUI, here is an example::

    import fmu.tools as tools

    # mylib.py is inside the RMS project
    plib = tools.rms.import_localmodule(project, "mylib")

    plib.somefunction(some_arg)

The library is outside RMS
--------------------------

Sometimes it is convenient that the library is made outside RMS, and the same function can
then be applied with a `path` keyword::

    import fmu.tools as tools

    # extlib.py is outside the RMS project, relative path ../lib/extlib.py

    plib = tools.rms.import_localmodule(project, "extlib", path="../lib")
    plib.somefunction(some_arg)

    # or as a package:
    # extlib is here a folder (package) is outside the RMS project, relative path ../lib/extlib
    # extlib/
    #        __init__.py
    #        calc.py

    plib = tools.rms.import_localmodule(project, "extlib", path="../lib")
    plib.calc.somefunction(some_arg)
