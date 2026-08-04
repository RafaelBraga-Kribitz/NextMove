"""Session-scoped fixtures shared by the memory-budget and UC-occurrence integration suites
(plan 01-08 Task 3).

A full `demo`-profile run (2000 customers, the base `simulator.yaml`'s 548-day horizon --
`demo.yaml` overrides only `n_customers`, deliberately keeping the full horizon so UC1's
pre-Christmas timing and UC2's longitudinal fatigue accumulation are both reachable) takes real
wall-clock time. Both `test_uc_scenarios_occur.py` and `test_simulation_budget.py` need one, so
this module runs it exactly once per test session (in-process, under `tracemalloc`) and once
more as a subprocess (for the peak-RSS reading `resource.getrusage` needs, which must observe a
child process rather than the pytest process itself), and every test that needs a demo-scale
artifact reuses the same result rather than paying for its own run.
"""

import subprocess
import sys
import time
import tracemalloc
from dataclasses import dataclass
from pathlib import Path

import pytest

import nextmove.simulator.run as run_module
from nextmove.config.loader import ResolvedConfig, load_config
from nextmove.simulator.run import run_simulation


@dataclass(frozen=True)
class DemoRunResult:
    """One in-process `demo`-profile run's artifacts, its traced Python heap peak, its wall
    clock, and the largest `events_raw` part file written during the run (captured by
    instrumenting `write_part_file` for the duration of this one run -- by the time the run
    returns, `clear_staging` has already removed every part file, so this is the only point at
    which a per-part row count can be observed)."""

    out_root: Path
    resolved: ResolvedConfig
    written: dict[str, Path]
    peak_traced_bytes: int
    max_events_part_rows: int
    elapsed_seconds: float


@pytest.fixture(scope="session")
def demo_run_result(tmp_path_factory: pytest.TempPathFactory) -> DemoRunResult:
    out_root = tmp_path_factory.mktemp("demo_run")
    resolved = load_config("demo")

    max_events_part_rows = 0
    original_write_part_file = run_module.write_part_file

    def _tracking_write_part_file(rows, part_dir, *args, **kwargs):
        nonlocal max_events_part_rows
        if part_dir == "events_raw":
            row_count = len(rows)
            if row_count > max_events_part_rows:
                max_events_part_rows = row_count
        return original_write_part_file(rows, part_dir, *args, **kwargs)

    run_module.write_part_file = _tracking_write_part_file
    tracemalloc.start()
    start = time.time()
    try:
        written = run_simulation(resolved, out_root=out_root)
        elapsed = time.time() - start
        _current_bytes, peak_bytes = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
        run_module.write_part_file = original_write_part_file

    return DemoRunResult(
        out_root=out_root,
        resolved=resolved,
        written=written,
        peak_traced_bytes=peak_bytes,
        max_events_part_rows=max_events_part_rows,
        elapsed_seconds=elapsed,
    )


@dataclass(frozen=True)
class SubprocessRunResult:
    """One subprocess profile run's peak resident set size, or the reason it could not be
    measured on this platform. Never fabricated: `peak_rss_bytes` is `None` exactly when
    `skip_reason` names why -- callers must skip, not substitute a placeholder number."""

    out_root: Path
    peak_rss_bytes: int | None
    skip_reason: str | None
    elapsed_seconds: float


def _run_subprocess_profile(profile: str, out_root: Path) -> float:
    start = time.time()
    subprocess.run(
        [
            sys.executable,
            "-m",
            "nextmove.simulator",
            "--profile",
            profile,
            "--out",
            str(out_root),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return time.time() - start


def measure_subprocess_peak_rss(profile: str, out_root: Path) -> SubprocessRunResult:
    """Run `profile` as a subprocess and read the child's peak RSS from
    `resource.getrusage(RUSAGE_CHILDREN)`, normalizing the platform's reporting unit (kilobytes
    on Linux, bytes on macOS). `resource` is POSIX-only; on a platform without it (this
    project's Windows dev machine) this returns a `SubprocessRunResult` naming that as the skip
    reason, never a fabricated number. Plan 01-11's CI step asserts this does not skip on
    Linux, the platform D-16 makes the enforcing one.
    """
    try:
        import resource
    except ImportError:
        # Skip without paying for a subprocess run we could not measure anyway.
        return SubprocessRunResult(
            out_root=out_root,
            peak_rss_bytes=None,
            skip_reason="resource module unavailable on this platform (POSIX-only)",
            elapsed_seconds=0.0,
        )

    elapsed = _run_subprocess_profile(profile, out_root)
    raw_rss = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    peak_bytes = raw_rss if sys.platform == "darwin" else raw_rss * 1024
    return SubprocessRunResult(
        out_root=out_root, peak_rss_bytes=peak_bytes, skip_reason=None, elapsed_seconds=elapsed
    )


@pytest.fixture(scope="session")
def demo_subprocess_rss(tmp_path_factory: pytest.TempPathFactory) -> SubprocessRunResult:
    out_root = tmp_path_factory.mktemp("demo_subprocess")
    return measure_subprocess_peak_rss("demo", out_root)
