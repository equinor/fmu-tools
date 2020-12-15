.. highlight:: shell

============
Contributing
============

Contributions are welcome, and they are greatly appreciated! Every
little bit helps, and credit will always be given.

You can contribute in many ways:

Types of Contributions
----------------------


Report Bugs
~~~~~~~~~~~

Report issues and bugs at https://github.com/equinor/fmu-tools/issues.

If you are reporting a bug, please include:

* Your operating system name and version, if this is expected to be relevant.
* Any details about your local setup that might be helpful in troubleshooting.
* Detailed steps to reproduce the bug.

Fix Bugs
~~~~~~~~

Look through the Git issues for bugs. Anything tagged with "bug"
and "help wanted" is open to whoever wants to implement it.

Implement Features
~~~~~~~~~~~~~~~~~~

Look through the Git issues for features. Anything tagged with "enhancement"
and "help wanted" is open to whoever wants to implement it.

Write Documentation
~~~~~~~~~~~~~~~~~~~

fmu-tools could always use more documentation, whether as part of the
official fmu-tools docs, in docstrings, or even on the web in blog posts,
articles, and such.

Submit Feedback
~~~~~~~~~~~~~~~

The best way to send feedback is to file an issue
at https://github.com/equinor/fmu-tools/issues.

Your can also use our Equinor Slack channel (todo).

If you are proposing a feature:

* Explain in detail how it would work.
* Keep the scope as narrow as possible, to make it easier to implement.
* Remember that this is a community-driven project, and that contributions
  are welcome :)

Code standards
--------------

It is required to be complient to code standards. A summary:

PEP8 and PEP20
~~~~~~~~~~~~~~

* We use PEP8 standard (https://www.python.org/dev/peps/pep-0008/) with `black's` line
  length exception and PEP20 philosophy.

  This implies:

  * Line width max 88

  * All coding will be formatted using ``black`` (yes forced, no mercy)

  * Naming: files_as_this, ClassesAsThis, ExceptionsAsThis, CONSTANTS,
    function_as_this, method_as_this

  * Use a single underscore to protect instance variables, other private
    variables and and private classes. Private methods can also be stored in
    private files, starting with an underscore.

  * 4 space indents (spaces, no tabs)

  * Double quotes to delimit strings (black default), triple double quotes
    in docstrings.

  * One space before and after =, =, +, * etc

  * No space around  = in keword lists, e.g. my_function(value=27, default=None)

  * Avoid one or two letter variables, even for counters. And meaningful names, but don't
    overdo it.

  * See also: https://git.equinor.com/fmu-utilities/fmu-coding-practice/blob/master/python-style.md


In addition:
~~~~~~~~~~~~

* Start with documentation and tests. Think, design and communicate first!

* Docstrings shall start and end with """ and use Google style.

* Use pytest as testing engine

* Code shall be python 3.6 + compliant


Use flake8 and/or pylint to check
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

  python -m flake8 mycode.py

The pylint is rather strict and sometimes exceptions are needed... , but anyway
quite useful! A targeted ``.pylintrc`` file is in the project root.

  python -m pylint mycode.py

Get Started!
------------

Ready to contribute? Here's how to set up `fmu-tools` for local development.

1. Fork the `fmu-tools` repo in web browser to a personal fork
2. Work in virtual environment, always!
3. Clone your fork locally::

     $ git clone git@github.com:<your-user>/fmu-tools.git
     $ cd fmu-tools
     $ git remote add upstream git@github.com:equinor/fmu-tools.git

   This means your `origin` is now your personal fork, while the actual master
   is at `upstream`.

Running, testing etc
~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

  $ source <your virtual env>
  $ cd <your-fmu-tools-project-dir>
  $ git clone --depth 1 https://github.com/equinor/xtgeo-testdata ../.
  $ git pull upstream master
  $ git checkout -b <your-branch-name>
  $ python setup.py clean
  $ python setup.py develop or pip install -e .

  ... do coding, run tests etc

  $ git commit -p
  $ git push origin <your-branch-name>

  .. ask for review on github

Generating docs for preliminary view
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

  $ python setup.py build_sphinx
