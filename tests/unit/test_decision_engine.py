"""C1/C2: the decision engine over stub and adversarial policies (AC-1, AC-2, AC-4)."""

import random

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from nextmove.decisions.contract import Decision
from nextmove.policies.base import ScoredCandidate
from nextmove.policies.baselines import AlwaysDiscountPolicy, DoNothingPolicy
from nextmove.policies.expected_value import ExpectedValuePolicy
from tests.decision_helpers import CATEGORIES, CONFIG, StubResponseModel, engine_for, make_context

EV_CONFIG = CONFIG.config.policies.expected_value


def _ev_engine(min_confidence=None):
    policy = ExpectedValuePolicy(
        StubResponseModel(), EV_CONFIG, CATEGORIES, top_k=3, name="ev_stub"
    )
    return engine_for(policy, min_confidence=min_confidence)


def test_every_decision_is_schema_valid_and_considers_restraint() -> None:
    engine = _ev_engine()
    for contacts in [(), (1,), (0, 2), (3, 5, 9)]:
        for stock in (5, 200):
            decision = engine.decide(make_context(contacts=contacts, stock=stock))
            again = Decision.model_validate_json(decision.model_dump_json())
            assert again == decision
            considered = decision.reasoning_trace.candidates_considered
            assert "none" in considered and "wait" in considered
            assert decision.reasoning.strip()
            assert decision.reasoning_trace.runner_up is not None


def test_ev_decision_carries_interval_confidence_and_attributions() -> None:
    decision = _ev_engine().decide(make_context())
    assert decision.expected_outcome.estimate is not None
    low, high = decision.expected_outcome.interval
    assert low <= decision.expected_outcome.estimate <= high
    assert 0.0 <= decision.confidence <= 1.0
    assert decision.policy.model_versions == {"response_model": "stub-1"}


def test_baseline_decision_states_missing_model_fields() -> None:
    decision = engine_for(DoNothingPolicy()).decide(make_context())
    assert decision.action.type == "none"
    assert decision.confidence is None
    assert "confidence" in decision.unavailable
    assert "fixed rules" in decision.reasoning


def test_discount_suppressed_under_scarcity_and_explained() -> None:
    decision = engine_for(AlwaysDiscountPolicy()).decide(make_context(stock=2))
    assert decision.action.type == "none"
    assert "inventory_scarcity_gate" in decision.reasoning_trace.fired_rules
    assert "low stock" in decision.reasoning


def test_low_confidence_falls_back_to_restraint() -> None:
    engine = _ev_engine(min_confidence=1.01)
    decision = engine.decide(make_context())
    assert decision.action.type == "none"
    if "not confident enough" not in decision.reasoning:
        # The stub already preferred restraint; the fallback was not needed.
        assert decision.reasoning_trace.scores["none"].score >= max(
            s.score for s in decision.reasoning_trace.scores.values()
        )


def test_all_candidates_excluded_goes_to_human_review() -> None:
    from nextmove.config.models import ConstraintsConfig, ConstraintSpec
    from nextmove.decisions.actions import build_providers
    from nextmove.decisions.engine import DecisionEngine
    from nextmove.rules import RuleSet, Verdict, constraint_registry, register_constraint

    if "block_everything" not in constraint_registry():

        @register_constraint("block_everything")
        class BlockEverything:
            def __init__(self, spec):
                self.spec = spec

            def evaluate(self, candidate, context):
                return Verdict(True, "test rule excludes every option")

    rules = RuleSet.from_config(
        ConstraintsConfig(
            rules=[
                ConstraintSpec(
                    name="block", kind="block_everything", mode="hard", precedence="compliance"
                )
            ]
        )
    )
    cfg = CONFIG.config
    engine = DecisionEngine(
        DoNothingPolicy(),
        rules,
        build_providers(cfg.actions, ["catalog"]),
        cfg.actions,
        CONFIG.config_hash,
    )
    decision = engine.decide(make_context())
    assert decision.needs_human_review
    assert decision.action.type == "none"
    assert "human review" in decision.reasoning


class _AdversarialPolicy:
    """Scores the riskiest candidates highest, with seeded noise."""

    name = "adversarial"
    model_versions: dict[str, str] = {}

    def __init__(self, seed: int) -> None:
        self.rng = random.Random(seed)

    def score(self, context, survivors, penalties):
        return [
            ScoredCandidate(
                candidate=c,
                score=c.discount_bps + 1000 * c.contact + self.rng.random(),
                uplift=0.01,
                uplift_interval=(0.0, 0.02),
                win_rate=1.0,
            )
            for c in survivors
        ]


@settings(
    max_examples=10_000,
    deadline=None,
    derandomize=True,
    suppress_health_check=[HealthCheck.too_slow],
)
@given(
    stock=st.integers(0, 300),
    contacts=st.lists(st.integers(0, 30), max_size=5).map(lambda d: tuple(sorted(d))),
    category=st.sampled_from(CATEGORIES),
    seed=st.integers(0, 2**16),
)
def test_ac2_engine_never_emits_a_hard_excluded_action(stock, contacts, category, seed) -> None:
    engine = engine_for(_AdversarialPolicy(seed))
    context = make_context(stock=stock, contacts=contacts, category=category)
    result = engine.decide_batch([context])[0]
    chosen = result.chosen
    excluded = {r.candidate_id for r in result.filter_outcome.filtered}
    assert chosen.id not in excluded
    max_bps = next(r for r in CONFIG.config.constraints.rules if r.kind == "discount_ceiling")
    assert chosen.discount_bps <= max_bps.params["max_discount_bps"]
    if chosen.contact:
        assert context.contacts_within(7) < 2
    if context.business.is_scarce(category):
        assert chosen.archetype not in ("discount_low", "discount_high", "bundle")
