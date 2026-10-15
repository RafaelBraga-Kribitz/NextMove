"""C2: explanations are templated, faithful to the trace, and never surveillance-framed."""

import re

import pytest

from nextmove.explain.templates import FEATURE_PHRASES, ExplanationInput, render_explanation
from nextmove.models.features import CONTEXT_FEATURES
from nextmove.policies.baselines import RulesOnlyPolicy
from nextmove.policies.expected_value import ExpectedValuePolicy
from tests.decision_helpers import CATEGORIES, CONFIG, StubResponseModel, engine_for, make_context

#: Anti-pattern 10: raw granular tracking references. Any match fails the release.
SURVEILLANCE_PATTERNS = [
    r"\b\d{1,2}:\d{2}\b",  # clock times
    r"\byou (viewed|looked at|clicked|searched|visited)\b",
    r"\bwe (saw|tracked|watched|noticed) you\b",
    r"\bsession[_ ]id\b",
    r"\bsku\b",
    r"[a-z_]+-\d{5}",  # product identifiers
    r"\bevent\b",
    r"\b(at|on) \d{4}-\d{2}-\d{2}\b",  # dates of individual actions
]


def _scan(text: str) -> list[str]:
    return [p for p in SURVEILLANCE_PATTERNS if re.search(p, text, flags=re.IGNORECASE)]


def test_every_model_feature_has_a_relevance_phrase() -> None:
    assert set(CONTEXT_FEATURES) <= set(FEATURE_PHRASES)


def _explanations():
    ev = ExpectedValuePolicy(
        StubResponseModel(), CONFIG.config.policies.expected_value, CATEGORIES, 3, "ev_stub"
    )
    rules_only = RulesOnlyPolicy(CONFIG.config.policies.baselines)
    texts = []
    for policy in (ev, rules_only):
        engine = engine_for(policy, min_confidence=0.5)
        for stock in (3, 150):
            for contacts in [(), (2,), (0, 1)]:
                for cart in (0.0, 3.0):
                    context = make_context(stock=stock, contacts=contacts, cart_state_units=cart)
                    texts.append(engine.decide(context).reasoning)
    return texts


def test_generated_explanations_contain_no_surveillance_phrasing() -> None:
    texts = _explanations()
    assert len(texts) == 24
    for text in texts:
        assert _scan(text) == [], text
        assert text.startswith("Recommendation:")


@pytest.mark.parametrize(
    "bad",
    ["You viewed jacket at 02:13.", "We tracked you on the site", "sku fashion_apparel-00001"],
)
def test_scanner_catches_surveillance_phrasing(bad: str) -> None:
    assert _scan(bad)


def test_low_confidence_fallback_is_stated() -> None:
    text = render_explanation(
        ExplanationInput(
            action_label="Do nothing this cycle.",
            action_type="none",
            is_restraint=True,
            uplift=0.0,
            uplift_interval=(0.0, 0.0),
            expected_profit_cents=0.0,
            runner_up_label="Content email sent immediately.",
            runner_up_uplift=0.004,
            runner_up_profit_cents=3.0,
            filtered_rules={},
            penalty_rules=["fatigue_penalty"],
            attributions=[("contacts_total", -0.2), ("month_sin", 0.1)],
            attributions_for_runner_up=True,
            confidence=0.3,
            low_confidence_fallback=True,
            min_confidence=0.5,
            policy_note=None,
        )
    )
    assert "not confident enough" in text
    assert "30%" in text and "50%" in text
    assert "how many messages they have received overall" in text
    assert "recently contacted" in text
