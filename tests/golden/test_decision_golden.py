"""AC-3: given fixed context, config hash, model versions and seed, the decision is
byte-identical across runs.

Two layers: (1) a checked-in golden file of decisions from a deterministic, BLAS-free stub
model, so any change to ranking, the trace, the contract or the explanation templates shows up
as a diff; (2) run-to-run identity with the real trained models on the tiny profile.
"""

import json
from pathlib import Path

from nextmove.config.loader import load_config
from nextmove.decisions.actions import build_providers
from nextmove.decisions.assembly import ContextStore
from nextmove.decisions.engine import DecisionEngine
from nextmove.models.train import load_model
from nextmove.policies.baselines import RulesOnlyPolicy
from nextmove.policies.expected_value import ExpectedValuePolicy
from nextmove.rules import RuleSet
from tests.decision_helpers import CATEGORIES, CONFIG, StubResponseModel, engine_for, make_context

GOLDEN = Path(__file__).parent / "fixtures" / "decisions_golden.jsonl"


def _golden_lines() -> list[str]:
    ev = ExpectedValuePolicy(
        StubResponseModel(), CONFIG.config.policies.expected_value, CATEGORIES, 3, "ev_stub"
    )
    lines = []
    for policy in (ev, RulesOnlyPolicy(CONFIG.config.policies.baselines)):
        # A pinned hash: the golden file tracks engine behaviour, not unrelated config edits.
        engine = engine_for(policy, min_confidence=0.5, config_hash="golden-config")
        for index, (stock, contacts, cart) in enumerate(
            [(150, (), 0.0), (150, (3,), 2.0), (4, (), 2.0), (150, (0, 1), 0.0), (60, (9,), 1.0)]
        ):
            context = make_context(
                customer_id=str(index), stock=stock, contacts=contacts, cart_state_units=cart
            )
            lines.append(engine.decide(context).model_dump_json())
    return lines


def test_decisions_match_golden_file() -> None:
    lines = _golden_lines()
    if not GOLDEN.exists():  # pragma: no cover - first generation only
        GOLDEN.write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert GOLDEN.read_text(encoding="utf-8").splitlines() == lines


def test_golden_decisions_are_valid_json_with_reasoning() -> None:
    for line in GOLDEN.read_text(encoding="utf-8").splitlines():
        data = json.loads(line)
        assert data["reasoning"]
        assert "none" in data["reasoning_trace"]["candidates_considered"]


def test_real_model_decisions_are_identical_across_runs(tiny_pipeline: Path) -> None:
    resolved = load_config("tiny")
    cfg = resolved.config
    train_end, validation_end, horizon = cfg.evaluation.windows(cfg.simulator.horizon_days)
    day = validation_end + 1

    def run() -> list[str]:
        store = ContextStore(
            resolved, tiny_pipeline, days=[day], business_reference_cutoff=train_end
        )
        rows = store.day_rows(day)
        contexts = [
            store.context(cid, day, row=rows[cid]) for cid in store.eligible_customers(day, rows)
        ]
        policy = ExpectedValuePolicy(
            load_model("gbm", tiny_pipeline),
            cfg.policies.expected_value,
            store.categories,
            cfg.models.attribution_top_k,
        )
        engine = DecisionEngine(
            policy,
            RuleSet.from_config(cfg.constraints),
            build_providers(cfg.actions, ["catalog"]),
            cfg.actions,
            resolved.config_hash,
            cfg.policies.expected_value.min_confidence,
        )
        return [r.decision.model_dump_json() for r in engine.decide_batch(contexts)]

    first, second = run(), run()
    assert first, "expected at least one eligible customer"
    assert first == second
