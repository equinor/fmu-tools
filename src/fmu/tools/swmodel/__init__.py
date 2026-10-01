"""Tools for Simplified-J saturation modelling."""

from __future__ import annotations

from typing import Any

from ._compute import clip_swl, compute, compute_so_sg, compute_sw
from ._config import (
    JFunction,
    PhaseJFunction,
    SwAlgorithm,
    SwConfig,
    SwOutputNames,
    load_config,
)


def run_swmodel(*args: Any, **kwargs: Any):
    """Lazily import the RMS entry point to avoid `python -m` warnings."""

    from .swmodel import run_swmodel as _run_swmodel

    return _run_swmodel(*args, **kwargs)


__all__ = [
    "JFunction",
    "PhaseJFunction",
    "SwAlgorithm",
    "SwConfig",
    "SwOutputNames",
    "clip_swl",
    "compute",
    "compute_so_sg",
    "compute_sw",
    "load_config",
    "run_swmodel",
]
