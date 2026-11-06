"""Create initial water saturation properties from Simplified-J functions."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import ValidationError

from fmu.tools.properties import SwFunction

from ._compute import compute
from ._config import SwConfig, load_swconfig
from ._io import FileBackend, RmsBackend

if TYPE_CHECKING:
    import xtgeo

try:
    from fmu.tools.version import version as __version__
except ImportError:
    __version__ = "0.0.0"

DESCRIPTION = """Swmodel - create initial water, oil and gas saturation parameters
based on Simplified J-function."""

_LOG_FORMAT = "%(levelname)s:%(name)s:%(message)s"
_HANDLER_NAME = "swmodel-stream-handler"
_SWMODEL_LOGGER_NAME = "fmu.tools.swmodel"
_SWFUNCTION_LOGGER_NAME = SwFunction.__module__

logger = logging.getLogger(__name__)


def get_parser() -> argparse.ArgumentParser:
    """Create argument parser for the swmodel CLI."""

    parser = argparse.ArgumentParser(description=DESCRIPTION)
    parser.add_argument(
        "CONFIGFILE", type=Path, help="swmodel configuration file in yaml format."
    )
    parser.add_argument(
        "--key_path",
        help=(
            "Dot-separated path to a specific config section within the config file "
            "(e.g. 'section.subsection')"
        ),
        default="",
    )
    parser.add_argument("--debug", action="store_true", help="Debug output")
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s (fmu-tools version {__version__})",
    )
    parser.add_argument(
        "--output_folder",
        type=Path,
        default=Path("./share/results/grids"),
        help="Write saturation files to this folder. Created if it does not exist.",
    )
    parser.add_argument(
        "--output_all",
        action="store_true",
        default=False,
        help="In addition to sw and sw_h, write so and sg",
    )
    return parser


def _configure_named_logger(logger_name: str, level: int) -> None:
    named_logger = logging.getLogger(logger_name)
    named_logger.setLevel(level)
    named_logger.propagate = False

    for handler in named_logger.handlers:
        if handler.get_name() == _HANDLER_NAME:
            handler.setLevel(level)
            handler.setFormatter(logging.Formatter(_LOG_FORMAT))
            return

    handler = logging.StreamHandler()
    handler.set_name(_HANDLER_NAME)
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter(_LOG_FORMAT))
    named_logger.addHandler(handler)


def _configure_logging(debug: bool = False) -> None:
    level = logging.DEBUG if debug else logging.INFO
    _configure_named_logger(_SWMODEL_LOGGER_NAME, level)
    _configure_named_logger(_SWFUNCTION_LOGGER_NAME, level)
    _configure_named_logger("xtgeo", logging.DEBUG if debug else logging.WARNING)


def _load_swconfig_or_raise(
    config: str | Path | dict[str, Any] | SwConfig,
    *,
    key_path: str = "",
) -> SwConfig:
    """Load SwConfig and add context to validation errors."""

    try:
        return load_swconfig(config, key_path=key_path)
    except ValidationError as error:
        if isinstance(config, (str, Path)):
            location = f"in {Path(config)}"
        else:
            location = "from provided mapping"

        if key_path:
            location = f"{location} (key_path={key_path!r})"

        raise RuntimeError(f"Invalid SwConfig {location}: {error}") from error


def run_swmodel(
    project: Any,
    config: str | Path | dict[str, Any] | SwConfig,
    *,
    key_path: str = "",
    output_all: bool = False,
    debug: bool = False,
) -> dict[str, xtgeo.GridProperty]:
    """Run swmodel inside RMS and write the results back to the project."""

    _configure_logging(debug=debug)
    cfg = _load_swconfig_or_raise(config, key_path=key_path)
    backend = RmsBackend(project, cfg)
    grid, gridprops = backend.load_grid_and_properties()
    _gridname, props = compute(
        cfg,
        grid=grid,
        gridprops=gridprops,
        output_all=output_all,
    )
    backend.write(props)
    return props


def main() -> None:
    """Run the file-based swmodel CLI."""

    parser = get_parser()
    args = parser.parse_args()
    _configure_logging(debug=args.debug)

    config_file = args.CONFIGFILE.resolve()
    cfg = _load_swconfig_or_raise(config_file, key_path=args.key_path)

    backend = FileBackend(cfg)
    grid, gridprops = backend.load_grid_and_properties()
    gridname, props = compute(
        cfg,
        grid=grid,
        gridprops=gridprops,
        output_all=args.output_all,
    )
    backend.write(gridname, props, args.output_folder)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        logger.exception("Fatal error in swmodel")
        raise
    else:
        logger.info("Done")
