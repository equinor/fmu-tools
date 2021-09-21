The qcforward functions
=======================

The ``qcforward`` class provides functionality (methods) to check the result
of various issues during an ensemble run.

All methods share a *design philosopy*

* The client (user) scripts shall be small and simple and easy to use also
  for modellers with little Python experience.
* Input will be a python dictionary, or a YAML file
* If possible (and within scope of method), the ``qcforward`` methods
  should be possible to run both inside RMS and outside RMS.
* Exception of the previous bullet point may occur e.g. if an Eclipse
  initialisation is required first; then running the qcforward job outside RMS
  is logical.
* All methods shall have a similar appearance (... as similar as possible)

Methods:


* :ref:`Compare well zonation and grid <qcforward-welzonvsgrid>`
* :ref:`Grid quality indicators <qcforward-gridqualindicators>`
* :ref:`Blocked wells vs grid properties <qcforward-bwvsprops>`
* :ref:`Run grid statistics <qcforward-gridstatistics>`

.. include:: qcforward/wellzon_vs_grid.inc

.. include:: qcforward/gridquality.inc

.. include:: qcforward/bw_vs_gridprops.inc

.. include:: qcforward/grid_statistics.inc
