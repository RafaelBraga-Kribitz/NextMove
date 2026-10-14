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


@pytest.fixture(scope="session")
def tiny_pipeline(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The tiny profile run through simulate -> ingest -> features -> experiment -> train, once
    per session, into a private output root. Decision-layer tests build on it."""
    import subprocess
    import sys

    root = tmp_path_factory.mktemp("tiny_pipeline")
    commands = [
        ["nextmove.simulator"],
        ["nextmove.ingest"],
        ["nextmove.features"],
        ["nextmove.evaluate", "experiment"],
        ["nextmove.models"],
    ]
    for command in commands:
        subprocess.run(
            [sys.executable, "-m", *command, "--profile", "tiny", "--out", str(root)],
            check=True,
            capture_output=True,
        )
    return root
