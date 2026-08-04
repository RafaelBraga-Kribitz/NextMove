"""Shared pytest fixtures for the nextmove test suite."""

from pathlib import Path

import pytest


@pytest.fixture
def tiny_profile_name() -> str:
    """Name of the ~50-100 customer fast-run config profile used by unit tests.

    Distinct from the `demo` (~2k customers, CI end-to-end) and `ci` profiles.
    The profile itself is added under config/profiles/ by plan 01-03.
    """
    return "tiny"


@pytest.fixture
def repo_root() -> Path:
    """Absolute path to the repository root."""
    return Path(__file__).resolve().parent.parent
