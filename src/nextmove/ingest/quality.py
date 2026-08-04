"""D-21's reject-rate threshold and D-22's one-line data-quality summary.

`evaluate_reject_rate` reads `IngestResult.reject_rate`, which `ingest_events` now populates
from **both** validation stages -- contract rejects and semantic-gate rejects -- because the
semantic gates run inside `ingest_events` itself, per batch, before the flush (see
`pipeline.py`'s module docstring). This function's correctness rests entirely on that
ordering: with the gates running after `ingest_events` returned, the rate this function read
was contract-only, and the configured threshold could never fire on a semantic violation --
exactly the slow-degradation class DATA-03 exists to catch (RESEARCH Pitfall 2). A future
refactor that moves the gates back outside `ingest_events` would break this function's
correctness silently; there is no defensive check against it here because none is
mechanically possible from this module alone.
"""

from __future__ import annotations

from nextmove.config.models import DataQualityConfig
from nextmove.ingest.pipeline import IngestResult


class RejectRateExceeded(Exception):
    """Raised when `IngestResult.reject_rate` exceeds `DataQualityConfig.max_reject_rate` and
    `fail_run_on_exceed` is true. Carries the observed rate, the configured threshold, and the
    per-stage reject counts, so the exception itself names whether contract violations,
    semantic violations, or both pushed the run over the line."""

    def __init__(
        self,
        observed_rate: float,
        threshold: float,
        rows_rejected_contract: int,
        rows_rejected_semantic: int,
    ) -> None:
        self.observed_rate = observed_rate
        self.threshold = threshold
        self.rows_rejected_contract = rows_rejected_contract
        self.rows_rejected_semantic = rows_rejected_semantic
        super().__init__(
            f"reject rate {observed_rate:.6f} exceeds configured threshold {threshold:.6f} "
            f"(contract={rows_rejected_contract}, semantic={rows_rejected_semantic})"
        )


def evaluate_reject_rate(result: IngestResult, config: DataQualityConfig) -> None:
    """Raise `RejectRateExceeded` when `result.reject_rate` exceeds `config.max_reject_rate`
    and `config.fail_run_on_exceed` is true. The threshold is an inclusive ceiling: a rate
    exactly equal to it passes."""
    if not config.fail_run_on_exceed:
        return
    if result.reject_rate > config.max_reject_rate:
        raise RejectRateExceeded(
            observed_rate=result.reject_rate,
            threshold=config.max_reject_rate,
            rows_rejected_contract=result.rows_rejected_contract,
            rows_rejected_semantic=result.rows_rejected_semantic,
        )


def format_dq_summary(result: IngestResult) -> str:
    """D-22's one-line data-quality summary: rows in, rows quarantined split into its
    contract and semantic components, the reject rate, and the passed/failed gate names.
    Takes only `result` -- `gates_passed`/`gates_failed` live on the `IngestResult` because
    the function that builds it is the function that ran the gates."""
    gates_passed = ",".join(result.gates_passed) if result.gates_passed else "(none)"
    gates_failed = ",".join(result.gates_failed) if result.gates_failed else "(none)"
    return (
        f"rows_in={result.rows_in} rows_landed={result.rows_landed} "
        f"rows_quarantined={result.rows_quarantined} "
        f"(contract={result.rows_rejected_contract}, semantic={result.rows_rejected_semantic}) "
        f"reject_rate={result.reject_rate:.4%} "
        f"gates_passed={gates_passed} gates_failed={gates_failed}"
    )
