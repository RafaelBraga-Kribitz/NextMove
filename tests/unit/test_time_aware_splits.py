"""Covers every `must_haves.truths` / behavior-block item for plan 01-10 Task 3's
`time_aware_split`: the half-open boundary, deterministic tiebreak, empty/single-timestamp edge
cases, and the repository-wide ban on random-shuffling splitters.
"""

from __future__ import annotations

import ast
import inspect
from datetime import UTC, datetime, timedelta
from pathlib import Path

from nextmove.features.splits import RandomSplitRefused, SplitResult, time_aware_split

_T0 = datetime(2024, 1, 1, tzinfo=UTC)
_T1 = datetime(2024, 1, 2, tzinfo=UTC)
_T2 = datetime(2024, 1, 3, tzinfo=UTC)


def _snapshot(customer_id: str, as_of_ts: datetime) -> dict:
    return {"customer_id": customer_id, "as_of_ts": as_of_ts}


def test_snapshot_exactly_on_boundary_lands_in_train() -> None:
    snapshots = [_snapshot("a", _T0), _snapshot("a", _T1), _snapshot("a", _T2)]
    result = time_aware_split(snapshots, boundary_ts=_T1)
    assert _snapshot("a", _T1) in result.train
    assert _snapshot("a", _T1) not in result.test


def test_snapshot_one_microsecond_after_boundary_lands_in_test() -> None:
    one_us_after = _T1 + timedelta(microseconds=1)
    snapshots = [_snapshot("a", _T0), _snapshot("a", one_us_after)]
    result = time_aware_split(snapshots, boundary_ts=_T1)
    assert _snapshot("a", _T0) in result.train
    assert _snapshot("a", one_us_after) in result.test
    assert _snapshot("a", one_us_after) not in result.train


def test_membership_is_deterministic_under_two_input_orders() -> None:
    snapshots = [_snapshot("b", _T0), _snapshot("a", _T0), _snapshot("c", _T2), _snapshot("a", _T2)]
    reordered = list(reversed(snapshots))

    result_a = time_aware_split(snapshots, boundary_ts=_T1)
    result_b = time_aware_split(reordered, boundary_ts=_T1)

    assert result_a.train == result_b.train
    assert result_a.test == result_b.test


def test_ties_on_as_of_ts_are_ordered_by_customer_id() -> None:
    snapshots = [
        _snapshot("z", _T0),
        _snapshot("a", _T0),
        _snapshot("m", _T0),
        _snapshot("x", _T2),  # a second distinct timestamp so the single-timestamp fast path
        # does not short-circuit this test before the tiebreak within the _T0 group matters.
    ]
    result = time_aware_split(snapshots, boundary_ts=_T1)
    assert [s["customer_id"] for s in result.train] == ["a", "m", "z"]


def test_empty_input_returns_empty_partitions_with_a_reason() -> None:
    result = time_aware_split([], boundary_ts=_T1)
    assert result == SplitResult(train=(), test=(), boundary_ts=_T1, reason=result.reason)
    assert result.train == ()
    assert result.test == ()
    assert result.reason is not None
    assert "no snapshots" in result.reason


def test_single_distinct_timestamp_returns_empty_partitions_with_a_reason() -> None:
    snapshots = [_snapshot("a", _T0), _snapshot("b", _T0), _snapshot("c", _T0)]
    result = time_aware_split(snapshots, boundary_ts=_T1)
    assert result.train == ()
    assert result.test == ()
    assert result.reason is not None
    assert (
        "single" in result.reason or "one" in result.reason.lower() or "as_of_ts" in result.reason
    )


def test_never_raises_on_empty_or_single_timestamp_input() -> None:
    # Explicit negative: these inputs must not raise and must not silently fall back to any
    # other strategy -- the absence of an exception here is itself the assertion.
    time_aware_split([], boundary_ts=_T1)
    time_aware_split([_snapshot("a", _T0)], boundary_ts=_T1)


def test_splits_module_exposes_no_shuffle_random_state_or_seed_parameter() -> None:
    signature = inspect.signature(time_aware_split)
    param_names = set(signature.parameters)
    assert "shuffle" not in param_names
    assert "random_state" not in param_names
    assert "seed" not in param_names


def test_random_split_refused_is_a_declared_exception_type() -> None:
    assert issubclass(RandomSplitRefused, Exception)


# ---------------------------------------------------------------------------------------
# Repository-wide ban on random-shuffling splitters (T-01-27): fails the suite if any module
# under src/ or tests/ imports one, naming the offending file.
# ---------------------------------------------------------------------------------------

_FORBIDDEN_SPLITTER_IMPORTS: frozenset[str] = frozenset(
    {
        "sklearn.model_selection.train_test_split",
        "sklearn.model_selection.ShuffleSplit",
        "sklearn.model_selection.KFold",
        "sklearn.model_selection.StratifiedShuffleSplit",
        "sklearn.utils.shuffle",
    }
)
_FORBIDDEN_MODULES: frozenset[str] = frozenset({"sklearn.model_selection"})


def _iter_python_files(*roots: str) -> list[Path]:
    repo_root = Path(__file__).resolve().parents[2]
    files: list[Path] = []
    for root in roots:
        base = repo_root / root
        if base.is_dir():
            files.extend(base.rglob("*.py"))
    return files


def test_no_module_under_src_or_tests_imports_a_random_shuffling_splitter() -> None:
    violations: list[str] = []
    for path in _iter_python_files("src", "tests"):
        if path.resolve() == Path(__file__).resolve():
            continue  # this file names the forbidden identifiers as data, not as an import
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                for alias in node.names:
                    dotted = f"{node.module}.{alias.name}"
                    if dotted in _FORBIDDEN_SPLITTER_IMPORTS or node.module in _FORBIDDEN_MODULES:
                        violations.append(f"{path}: from {node.module} import {alias.name}")
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in _FORBIDDEN_MODULES:
                        violations.append(f"{path}: import {alias.name}")
    assert violations == [], f"random-shuffling splitter import(s) found: {violations}"
