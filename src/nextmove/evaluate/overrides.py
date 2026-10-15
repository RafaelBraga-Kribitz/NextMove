"""Operator overrides (D4, UC1): logged human decisions that feed back into evaluation.

An override replaces the engine's chosen action for one decision with another candidate. It is
stored append-only in `data/overrides/overrides.jsonl` (never a DVC output, so a pipeline rerun
cannot erase it) and is validated against the hard constraints before it is accepted: a human
may overrule the model, not the rules. Evaluation prices every override against the simulated
world -- the expected profit of the original action versus the override -- so the override loop
is visible in the evaluation report and in the demo.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

from nextmove.decisions.assembly import ContextStore
from nextmove.evaluate.world import OutcomeOracle
from nextmove.storage import Zone, resolve_artifact_path

__all__ = [
    "OVERRIDE_COLUMNS",
    "OverrideRecord",
    "append_override",
    "evaluate_overrides",
    "read_overrides",
]

OVERRIDE_COLUMNS = [
    "override_id",
    "decision_id",
    "customer_id",
    "day",
    "original_candidate",
    "override_candidate",
    "reason",
    "operator",
    "created_at",
    "expected_profit_original_cents",
    "expected_profit_override_cents",
    "override_effect_cents",
]


class OverrideRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    override_id: str
    decision_id: str = Field(min_length=1)
    customer_id: str = Field(min_length=1)
    day: int = Field(ge=0)
    original_candidate: str = Field(min_length=1)
    override_candidate: str = Field(min_length=1)
    reason: str = Field(min_length=3, max_length=500)
    operator: str = Field(min_length=1, max_length=100)
    created_at: datetime


def _path(root: Path | None) -> Path:
    return resolve_artifact_path("overrides.jsonl", Zone.OVERRIDES, root)


def append_override(
    root: Path | None,
    *,
    decision_id: str,
    customer_id: str,
    day: int,
    original_candidate: str,
    override_candidate: str,
    reason: str,
    operator: str,
) -> OverrideRecord:
    record = OverrideRecord(
        override_id=str(uuid.uuid4()),
        decision_id=decision_id,
        customer_id=customer_id,
        day=day,
        original_candidate=original_candidate,
        override_candidate=override_candidate,
        reason=reason,
        operator=operator,
        created_at=datetime.now(UTC),
    )
    path = _path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(record.model_dump_json() + "\n")
    return record


def read_overrides(root: Path | None) -> list[OverrideRecord]:
    path = _path(root)
    if not path.is_file():
        return []
    return [
        OverrideRecord.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def evaluate_overrides(
    records: list[OverrideRecord], store: ContextStore, oracle: OutcomeOracle
) -> pd.DataFrame:
    """Expected profit (simulated ground truth) of the original action versus the override."""
    from nextmove.config.models import ActionsConfig
    from nextmove.decisions.actions import CatalogActionProvider

    actions: ActionsConfig = store.resolved.config.actions
    catalog = {c.id: c for c in CatalogActionProvider(actions)._candidates}
    rows = []
    margins = store.margin_rate
    values = store.avg_order_value_cents
    for record in records:
        prior = len(store.exposure_days_before(record.customer_id, record.day))
        if store.has_row(record.customer_id, record.day):
            context = store.context(record.customer_id, record.day)
            value, margin = float(context.order_value_cents), float(context.margin_rate)
        else:
            category = oracle.primary_category(record.customer_id)
            value = float(values.get(category, 0))
            margin = float(margins.get(category, 0.0))

        def profit(
            candidate_id: str,
            record: OverrideRecord = record,
            prior: int = prior,
            value: float = value,
            margin: float = margin,
        ) -> float:
            candidate = catalog.get(candidate_id)
            if candidate is None:
                return float("nan")
            p = oracle.p_convert(
                record.customer_id, record.day, candidate.archetype, candidate.params, prior
            )
            return p * value * (margin - candidate.discount_bps / 10_000) - candidate.cost_cents

        original = profit(record.original_candidate)
        override = profit(record.override_candidate)
        rows.append(
            {
                **{k: getattr(record, k) for k in OVERRIDE_COLUMNS[:8]},
                "created_at": record.created_at.isoformat(),
                "expected_profit_original_cents": original,
                "expected_profit_override_cents": override,
                "override_effect_cents": override - original,
            }
        )
    frame = pd.DataFrame(rows, columns=OVERRIDE_COLUMNS)
    frame["day"] = frame["day"].astype("int64")
    for column in OVERRIDE_COLUMNS[-3:]:
        frame[column] = frame[column].astype(float)
    for column in (
        "override_id",
        "decision_id",
        "customer_id",
        "original_candidate",
        "override_candidate",
        "reason",
        "operator",
        "created_at",
    ):
        frame[column] = frame[column].astype(str)
    return frame
