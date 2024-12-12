# Contributing

Contributions are welcome, and they are greatly appreciated! Every
little bit helps, and credit will always be given.

You can contribute in many ways:

## Types of Contributions

### Report Bugs

Report issues and bugs at
[https://github.com/equinor/fmu-tools/issues](https://github.com/equinor/fmu-tools/issues).

If you are reporting a bug, please include:

- Your operating system name and version, if this is expected to be relevant.
- Any details about your local setup that might be helpful in troubleshooting.
- Detailed steps to reproduce the bug.

### Fix Bugs

Look through the Git issues for bugs. Anything tagged with "bug"
and "help wanted" is open to whoever wants to implement it.

### Implement Features

Look through the Git issues for features. Anything tagged with "enhancement"
and "help wanted" is open to whoever wants to implement it.

### Write Documentation

fmu-tools could always use more documentation, whether as part of the
official fmu-tools docs, in docstrings, or even on the web in blog posts,
articles, and such.

### Submit Feedback

The best way to send feedback is to file an issue
at
[https://github.com/equinor/fmu-tools/issues](https://github.com/equinor/fmu-tools/issues).

If you are proposing a feature:

- Explain in detail how it would work.
- Keep the scope as narrow as possible, to make it easier to implement.
- Remember that this is a community-driven project, and that contributions
  are welcome :)

## Code standards

It is required to be complient to code standards. A summary:

### Formatted with ruff

All code should be formatted by ruff with a line length of 88 characters.

In addition:
- Start with documentation and tests. Think, design and communicate first!
- Docstrings shall start and end with """ and use Google style.
- Use pytest as testing engine
- Code shall be Python 3.9+ compliant


### Linting

```sh
  ruff check . && ruff format . --check
```

## Contribute

Ready to contribute? Here's how to set up `fmu-tools` for local development.

1. Fork the `fmu-tools` to a personal fork
2. Work in virtual environment, always!
3. Clone your fork locally:

```sh
    git clone git@github.com:<your-user>/fmu-tools.git
    cd fmu-tools
    git remote add upstream git@github.com:equinor/fmu-tools.git
```

This means your `origin` is now your personal fork, while the actual main
branch is at `upstream`.

### Running, testing etc

```sh
    source <your virtual env>
    cd <your-fmu-tools-project-dir>
    git clone --depth 1 https://github.com/equinor/xtgeo-testdata ../.
    git pull upstream main
    git checkout -b <your-branch-name>
    pip install -e ".[tests,docs]"
```

Once your changes are complete, commit and push them.

```sh
    git commit -p
    git push origin <your-branch-name>
```

And ask for review on GitHub.

### Generating docs for preliminary view

```sh
    sphinx-build -W -b html docs build/docs/html
```
