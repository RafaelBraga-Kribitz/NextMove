"""Templated, manager-readable explanations rendered from the structured reasoning trace (C2).

No language model is involved (QUALITY_BAR anti-pattern 2): every sentence is a fixed template
filled from trace fields, so an explanation can never say something the trace does not
support. Wording follows `docs/EXPLANATION_STYLE_GUIDE.md`: relevance framing ("their history
of buying on discount"), never surveillance framing ("you viewed X at 02:13"); no timestamps,
product ids or raw event names; uncertainty stated, not hidden.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["ExplanationInput", "FEATURE_PHRASES", "render_explanation"]

#: Relevance-framed phrase for every model feature that can appear in an attribution.
FEATURE_PHRASES: dict[str, str] = {
    "has_ordered": "whether they have bought before",
    "rfm_recency_days": "time since their last purchase",
    "rfm_frequency_count": "how often they have bought recently",
    "rfm_monetary_cents": "how much they have spent recently",
    "session_visits_count": "how often they have visited recently",
    "session_depth_mean_views": "how much they browse per visit",
    "price_sensitivity_proxy": "their history of buying on discount",
    "message_fatigue_count": "how many messages they received in the last two weeks",
    "cart_state_units": "items waiting in their basket",
    "abandonment_history_count": "baskets left without buying",
    "dwell_long_count": "long looks at product pages",
    "dwell_medium_count": "brief looks at product pages",
    "scroll_count": "scrolling through product lists",
    "filter_apply_count": "use of search filters",
    "primary_affinity_share": "how focused they are on one category",
    "contacts_7d": "how many messages they received this week",
    "contacts_total": "how many messages they have received overall",
    "tenure_days": "how long they have been a customer",
    "month_sin": "the time of year",
    "month_cos": "the time of year",
    "low_stock": "current stock levels",
}

_RULE_PHRASES: dict[str, str] = {
    "discount_ceiling": "the maximum discount allowed",
    "margin_floor": "the minimum margin after discount",
    "inventory_scarcity_gate": "low stock in their favourite category",
    "frequency_cap": "the weekly contact limit",
    "fatigue_penalty": "the cost of messaging a recently contacted customer",
}


@dataclass(frozen=True)
class ExplanationInput:
    action_label: str
    action_type: str
    is_restraint: bool
    uplift: float | None
    uplift_interval: tuple[float, float] | None
    expected_profit_cents: float | None
    runner_up_label: str | None
    runner_up_uplift: float | None
    runner_up_profit_cents: float | None
    filtered_rules: dict[str, int]
    penalty_rules: list[str]
    attributions: list[tuple[str, float]]
    attributions_for_runner_up: bool
    confidence: float | None
    low_confidence_fallback: bool
    min_confidence: float | None
    policy_note: str | None
    needs_human_review: bool = False


def _points(value: float) -> str:
    return f"{value * 100:+.1f} percentage points"


def _money(cents: float) -> str:
    return f"€{cents / 100:+.2f}"


def _drivers(attributions: list[tuple[str, float]]) -> tuple[list[str], list[str]]:
    pro: list[str] = []
    con: list[str] = []
    for feature, weight in attributions:
        if feature.startswith("action:"):
            continue
        phrase = FEATURE_PHRASES.get(feature)
        if phrase is None and feature.startswith("primary_is_"):
            phrase = "their favourite category"
        if phrase is None:
            continue
        target = pro if weight > 0 else con
        if phrase not in pro and phrase not in con:
            target.append(phrase)
    return pro, con


def _join(items: list[str]) -> str:
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]


def render_explanation(data: ExplanationInput) -> str:
    """One paragraph a marketing manager can read without edits."""
    sentences: list[str] = []
    if data.needs_human_review:
        sentences.append(
            "Every available option, including doing nothing, conflicts with a business "
            "rule, so this customer is sent for human review and no action is taken."
        )
    elif data.low_confidence_fallback:
        sentences.append(
            f"Recommendation: {data.action_label.rstrip('.')}. The models were not confident "
            f"enough to act (confidence {data.confidence:.0%}, below the "
            f"{data.min_confidence:.0%} threshold), so the safe default is to wait for a "
            "clearer signal."
        )
    else:
        sentences.append(f"Recommendation: {data.action_label.rstrip('.')}.")

    if data.policy_note and data.uplift is None:
        sentences.append(f"This follows a fixed rule ({data.policy_note.lower()}).")
    elif data.is_restraint and not data.needs_human_review and not data.runner_up_label:
        sentences.append(
            "Every option that would contact this customer is ruled out by business rules "
            "right now, so holding back is the only choice."
        )
    elif data.is_restraint and not data.needs_human_review and data.runner_up_label:
        if data.runner_up_profit_cents is not None and data.runner_up_uplift is not None:
            sentences.append(
                "No action is expected to add profit for this customer right now: the best "
                f"alternative, {data.runner_up_label.rstrip('.').lower()}, would change their "
                f"purchase chance by {_points(data.runner_up_uplift)} and expected profit by "
                f"{_money(data.runner_up_profit_cents)} after costs."
            )
    elif not data.is_restraint and data.uplift is not None:
        text = f"It is expected to change their purchase chance by {_points(data.uplift)}"
        if data.uplift_interval is not None:
            low, high = data.uplift_interval
            text += f" (plausible range {low * 100:+.1f} to {high * 100:+.1f})"
        if data.expected_profit_cents is not None:
            text += f", worth {_money(data.expected_profit_cents)} in expected profit after costs"
        sentences.append(text + ".")

    pro, con = _drivers(data.attributions)
    if pro or con:
        subject = "the alternative" if data.attributions_for_runner_up else "this action"
        parts = []
        if pro:
            parts.append(f"in favour of {subject}: {_join(pro)}")
        if con:
            parts.append(f"against it: {_join(con)}")
        sentences.append("Main factors " + "; ".join(parts) + ".")

    if data.filtered_rules:
        described = [
            f"{_RULE_PHRASES.get(rule, rule.replace('_', ' '))} "
            f"({count} option{'s' if count != 1 else ''})"
            for rule, count in sorted(data.filtered_rules.items())
        ]
        sentences.append("Options ruled out by business rules: " + _join(described) + ".")
    if data.penalty_rules:
        described = [_RULE_PHRASES.get(r, r.replace("_", " ")) for r in data.penalty_rules]
        sentences.append("Scores were reduced for " + _join(described) + ".")

    if data.confidence is not None and not data.low_confidence_fallback:
        sentences.append(
            f"Confidence: {data.confidence:.0%} of model resamples rank this option first."
        )
    elif data.confidence is None and not data.needs_human_review:
        sentences.append("No confidence score: this policy uses fixed rules, not a model.")
    return " ".join(sentences)
