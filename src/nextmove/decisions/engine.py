"""The decision engine (C1): observation -> candidates -> hard filter -> ranking -> explanation.

`DecisionEngine.decide_batch` runs the whole pipeline of `DECISION_ENGINE_DESIGN.md` §4 for a
batch of contexts and returns fully validated `Decision` objects. Any policy that satisfies the
`Policy` protocol can be plugged in -- the AC-10 baselines and the expected-value policy share
this exact path, so none of them can bypass constraints, explanations or the trace.

Determinism (AC-3): the engine has no randomness of its own. Given the same context, config,
model versions and policy, the decision -- including `decision_id`, a UUIDv5 of those inputs --
is byte-identical across runs; `tests/golden/test_decision_golden.py` locks this in.
"""

from __future__ import annotations

import uuid
from collections import Counter
from dataclasses import dataclass

from nextmove.config.models import ActionsConfig
from nextmove.decisions.actions import ActionProvider, Candidate, generate_candidates
from nextmove.decisions.context import DecisionContext
from nextmove.decisions.contract import (
    ActionChoice,
    Attribution,
    CandidateScore,
    Decision,
    ExpectedOutcome,
    FilteredCandidate,
    PolicyInfo,
    ReasoningTrace,
    RunnerUp,
)
from nextmove.explain.templates import ExplanationInput, render_explanation
from nextmove.policies.base import ScoredCandidate, pick
from nextmove.rules import FilterOutcome, RuleSet

__all__ = ["DecisionEngine", "EngineResult"]

_NAMESPACE = uuid.UUID("6f1c2d4e-8a8b-4c51-9a8e-6e6578746d76")


@dataclass(frozen=True)
class EngineResult:
    decision: Decision
    chosen: Candidate
    filter_outcome: FilterOutcome
    ranked: list[ScoredCandidate]


class DecisionEngine:
    def __init__(
        self,
        policy,
        rules: RuleSet,
        providers: list[ActionProvider],
        actions: ActionsConfig,
        config_hash: str,
        min_confidence: float | None = None,
    ) -> None:
        self.policy = policy
        self.rules = rules
        self.providers = providers
        self.actions = actions
        self.config_hash = config_hash
        self.min_confidence = min_confidence
        self._labels = {a.name: a.description for a in actions.catalog}

    def _label(self, candidate: Candidate) -> str:
        label = self._labels.get(candidate.archetype, candidate.archetype.replace("_", " "))
        if candidate.discount_bps:
            label = f"{label.rstrip('.')} ({candidate.discount_bps / 100:g}% off)."
        return label

    def decide(self, context: DecisionContext) -> Decision:
        return self.decide_batch([context])[0].decision

    def decide_batch(self, contexts: list[DecisionContext]) -> list[EngineResult]:
        candidate_lists = [generate_candidates(c, self.providers, self.actions) for c in contexts]
        outcomes = [
            self.rules.apply(cands, c) for cands, c in zip(candidate_lists, contexts, strict=True)
        ]
        prepare = getattr(self.policy, "prepare", None)
        if prepare is not None:
            union = {cand.id: cand for cands in candidate_lists for cand in cands}
            prepare(contexts, list(union.values()))
        return [
            self._decide_one(context, candidates, outcome)
            for context, candidates, outcome in zip(
                contexts, candidate_lists, outcomes, strict=True
            )
        ]

    def _decide_one(
        self, context: DecisionContext, candidates: list[Candidate], outcome: FilterOutcome
    ) -> EngineResult:
        considered = [c.id for c in candidates]
        by_id = {c.id: c for c in candidates}
        filtered = [
            FilteredCandidate(action=r.candidate_id, rule=r.rule, detail=r.detail)
            for r in outcome.filtered
        ]
        if not outcome.survivors:
            return self._human_review(context, considered, filtered, outcome, by_id)

        ranked = pick(
            self.policy.score(context, outcome.survivors, outcome.penalties_cents),
            outcome.survivors,
        )
        best = ranked[0]
        fallback = False
        if (
            self.min_confidence is not None
            and best.win_rate is not None
            and best.win_rate < self.min_confidence
            and best.candidate.archetype != "none"
        ):
            restraint = next((s for s in ranked if s.candidate.archetype == "none"), None)
            if restraint is not None:
                best, fallback = restraint, True
        others = [s for s in ranked if s.candidate.id != best.candidate.id]
        runner = others[0] if others else None
        # For a restraint choice the reader wants the best option that would actually do
        # something; the trace still records the true runner-up.
        active = [s for s in others if s.candidate.archetype not in ("none", "wait")]
        restraint_chosen = best.candidate.archetype in ("none", "wait")
        if restraint_chosen:
            alternative = active[0] if active else None
        else:
            alternative = runner

        scores = {
            s.candidate.id: CandidateScore(
                score=round(s.score, 6),
                uplift=round(s.uplift, 8) if s.uplift is not None else 0.0,
                value_cents=round(s.value_cents, 4),
                cost_cents=round(s.cost_cents, 4),
                risk_penalty_cents=round(s.risk_penalty_cents, 4),
            )
            for s in ranked
        }
        explain = getattr(self.policy, "explain", None)
        attributions: list[tuple[str, float]] = []
        for_runner = False
        if explain is not None:
            if restraint_chosen and alternative is not None:
                attributions, for_runner = explain(context, alternative.candidate), True
            else:
                attributions = explain(context, best.candidate)

        unavailable: dict[str, str] = {}
        if best.uplift is None:
            unavailable["expected_outcome.estimate"] = (
                f"policy {self.policy.name} is rule-based and has no response model"
            )
            unavailable["expected_outcome.interval"] = unavailable["expected_outcome.estimate"]
        if best.win_rate is None:
            unavailable["confidence"] = (
                f"policy {self.policy.name} is rule-based; confidence needs a model ensemble"
            )
        interval = (
            (round(best.uplift_interval[0], 8), round(best.uplift_interval[1], 8))
            if best.uplift_interval is not None
            else None
        )
        estimate = round(best.uplift, 8) if best.uplift is not None else None
        if estimate is not None and interval is not None:
            interval = (min(interval[0], estimate), max(interval[1], estimate))
        expected_profit = best.extra.get("expected_profit_cents")
        confidence = round(best.win_rate, 6) if best.win_rate is not None else None

        filtered_counts = Counter(r.rule for r in outcome.filtered)
        penalty_rules = sorted(
            {d.split(":", 1)[0] for d in outcome.penalty_details.get(best.candidate.id, [])}
        )
        reasoning = render_explanation(
            ExplanationInput(
                action_label=self._label(best.candidate),
                action_type=best.candidate.archetype,
                is_restraint=best.candidate.archetype in ("none", "wait"),
                uplift=best.uplift,
                uplift_interval=best.uplift_interval,
                expected_profit_cents=expected_profit,
                runner_up_label=self._label(alternative.candidate) if alternative else None,
                runner_up_uplift=alternative.uplift if alternative else None,
                runner_up_profit_cents=(
                    alternative.extra.get("expected_profit_cents") if alternative else None
                ),
                filtered_rules=dict(filtered_counts),
                penalty_rules=penalty_rules,
                attributions=attributions,
                attributions_for_runner_up=for_runner,
                confidence=best.win_rate,
                low_confidence_fallback=fallback,
                min_confidence=self.min_confidence,
                policy_note=best.note,
            )
        )
        decision = Decision(
            decision_id=self._decision_id(context),
            customer_id=context.customer_id,
            as_of=context.as_of,
            action=ActionChoice(
                type=best.candidate.archetype,
                candidate_id=best.candidate.id,
                params=dict(best.candidate.params),
            ),
            expected_outcome=ExpectedOutcome(
                estimate=estimate,
                interval=interval,
                horizon_days=self.actions.horizon_days,
                expected_profit_cents=round(expected_profit, 4)
                if expected_profit is not None
                else None,
            ),
            confidence=confidence,
            reasoning=reasoning,
            reasoning_trace=ReasoningTrace(
                candidates_considered=considered,
                filtered=filtered,
                fired_rules=list(outcome.fired_rules),
                scores=scores,
                runner_up=(
                    RunnerUp(
                        action=runner.candidate.id,
                        score_gap=round(max(best.score - runner.score, 0.0), 6),
                    )
                    if runner
                    else None
                ),
                runner_up_unavailable_reason=None
                if runner
                else "only one option survived the rules",
                model_attributions=[Attribution(feature=f, weight=w) for f, w in attributions],
            ),
            constraints_considered=list(outcome.constraints_considered),
            policy=PolicyInfo(
                name=self.policy.name,
                model_versions=dict(self.policy.model_versions),
                config_hash=self.config_hash,
            ),
            unavailable=unavailable,
        )
        return EngineResult(decision, best.candidate, outcome, ranked)

    def _human_review(self, context, considered, filtered, outcome, by_id) -> EngineResult:
        reason = "every candidate, including restraint, was excluded by a hard constraint"
        reasoning = render_explanation(
            ExplanationInput(
                action_label="Do nothing.",
                action_type="none",
                is_restraint=True,
                uplift=None,
                uplift_interval=None,
                expected_profit_cents=None,
                runner_up_label=None,
                runner_up_uplift=None,
                runner_up_profit_cents=None,
                filtered_rules=dict(Counter(r.rule for r in outcome.filtered)),
                penalty_rules=[],
                attributions=[],
                attributions_for_runner_up=False,
                confidence=None,
                low_confidence_fallback=False,
                min_confidence=None,
                policy_note=None,
                needs_human_review=True,
            )
        )
        decision = Decision(
            decision_id=self._decision_id(context),
            customer_id=context.customer_id,
            as_of=context.as_of,
            action=ActionChoice(type="none", candidate_id="none", params={}),
            expected_outcome=ExpectedOutcome(
                estimate=None, interval=None, horizon_days=self.actions.horizon_days
            ),
            confidence=None,
            reasoning=reasoning,
            reasoning_trace=ReasoningTrace(
                candidates_considered=considered,
                filtered=filtered,
                fired_rules=list(outcome.fired_rules),
                scores={},
                runner_up=None,
                runner_up_unavailable_reason="no candidate survived the rules",
            ),
            constraints_considered=list(outcome.constraints_considered),
            policy=PolicyInfo(
                name=self.policy.name,
                model_versions=dict(self.policy.model_versions),
                config_hash=self.config_hash,
            ),
            needs_human_review=True,
            review_reason=reason,
            unavailable={
                "expected_outcome.estimate": reason,
                "expected_outcome.interval": reason,
                "confidence": reason,
            },
        )
        return EngineResult(decision, by_id.get("none", next(iter(by_id.values()))), outcome, [])

    def _decision_id(self, context: DecisionContext) -> str:
        key = "|".join(
            [
                context.customer_id,
                context.as_of.isoformat(),
                self.policy.name,
                self.config_hash,
                ",".join(f"{k}={v}" for k, v in sorted(self.policy.model_versions.items())),
            ]
        )
        return str(uuid.uuid5(_NAMESPACE, key))
