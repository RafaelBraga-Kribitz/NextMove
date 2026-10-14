"""The `evaluate` pipeline stage (D1-D4): policy replay, three-axis report, uplift error,
3WD verdicts, overrides, and the published report files.

Steps:

1. **Model selection on validation.** Both expected-value policies (logistic, gbm) are replayed
   over the validation window; the family with the higher realized profit becomes "the ML
   policy" (TD-13: decision value first). The test window is never used for selection.
2. **Test replay.** Every policy -- the four baselines, both expected-value policies and a
   hindsight oracle (upper bound, not deployable) -- is replayed over the test window on the
   same customers, days and random draws (ADR-012).
3. **Intervals.** Customer-level bootstrap (`evaluation.bootstrap_resamples`) for totals and
   paired differences.
4. **Gateway.** The ML policy's promotion over rules-only and over do-nothing is adjudicated by
   the 3WD gateway (`nextmove.evaluate.gateway`).
5. **Reports.** Tables under `data/evaluation/`, published files under
   `reports/<profile>/evaluation/`.

Every number written here is a statement about the simulated world only (ADR-004); the report
says so in its first line, and every file carries the run id.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable
from pathlib import Path

import numpy as np
import pandas as pd

from nextmove.config.loader import ResolvedConfig
from nextmove.decisions.actions import build_providers
from nextmove.decisions.assembly import ContextStore
from nextmove.decisions.engine import DecisionEngine
from nextmove.evaluate.gateway import Estimate, Readout, adjudicate
from nextmove.evaluate.overrides import evaluate_overrides, read_overrides
from nextmove.evaluate.report import write_reports
from nextmove.evaluate.rollout import Choice, RolloutSpec, rollout
from nextmove.evaluate.world import OutcomeOracle
from nextmove.models.features import context_feature_names
from nextmove.models.train import FAMILIES, load_model
from nextmove.policies.baselines import baseline_policies
from nextmove.policies.expected_value import ExpectedValuePolicy
from nextmove.rules import RuleSet
from nextmove.storage import (
    Stage,
    Zone,
    content_hash,
    read_frame,
    resolve_table_path,
    write_frame,
)

__all__ = ["POLICY_LABELS", "bootstrap_interval", "run_evaluation"]

REPO_ROOT = Path(__file__).resolve().parents[3]

POLICY_LABELS = {
    "do_nothing": "Do nothing",
    "always_discount": "Always discount",
    "top_seller": "Top-seller recommendation",
    "rules_only": "Rules-only playbook",
    "expected_value_logistic": "Decision engine (logistic)",
    "expected_value_gbm": "Decision engine (GBM)",
    "oracle_upper_bound": "Hindsight oracle (upper bound, not deployable)",
}


def _engine_chooser(engine: DecisionEngine, keep_text: bool) -> Callable:
    def choose(day, contexts, outcomes):
        results = engine.decide_batch(contexts)
        choices = []
        for result in results:
            d = result.decision
            extra: dict[str, object] = {
                "decision_id": d.decision_id,
                "confidence": d.confidence if d.confidence is not None else float("nan"),
                "uplift_estimate": (
                    d.expected_outcome.estimate
                    if d.expected_outcome.estimate is not None
                    else float("nan")
                ),
                "expected_profit_estimate_cents": (
                    d.expected_outcome.expected_profit_cents
                    if d.expected_outcome.expected_profit_cents is not None
                    else float("nan")
                ),
                "needs_human_review": d.needs_human_review,
                "runner_up": d.reasoning_trace.runner_up.action
                if d.reasoning_trace.runner_up
                else "",
                "reasoning": d.reasoning if keep_text else "",
            }
            choices.append(Choice(result.chosen, extra))
        return choices

    return choose


def _oracle_chooser(oracle: OutcomeOracle) -> Callable:
    def choose(day, contexts, outcomes):
        choices = []
        for context, outcome in zip(contexts, outcomes, strict=True):
            prior = len(context.contact_days_ago)
            value, margin = float(context.order_value_cents), float(context.margin_rate)
            best, best_profit = None, -np.inf
            for candidate in outcome.survivors:
                p = oracle.p_convert(
                    context.customer_id, day, candidate.archetype, candidate.params, prior
                )
                profit = (
                    p * value * (margin - candidate.discount_bps / 10_000) - candidate.cost_cents
                )
                if profit > best_profit + 1e-12:
                    best, best_profit = candidate, profit
            choices.append(Choice(best, {"decision_id": "", "reasoning": ""}))
        return choices

    return choose


def bootstrap_interval(
    per_customer: np.ndarray, weights: np.ndarray, level: float
) -> tuple[float, float]:
    """Percentile interval of the total over customer bootstrap resamples. `weights` is the
    (resamples x customers) multinomial count matrix shared by every metric, so paired
    differences use identical resamples."""
    totals = weights @ per_customer
    alpha = (1 - level) / 2
    return float(np.quantile(totals, alpha)), float(np.quantile(totals, 1 - alpha))


def _per_customer(frame: pd.DataFrame, column: str, customers: list[str]) -> np.ndarray:
    sums = frame.groupby("customer_id")[column].sum()
    return sums.reindex(customers, fill_value=0.0).to_numpy(dtype=float)


def _summaries(
    logs: dict[str, pd.DataFrame], customers: list[str], weights: np.ndarray, level: float
) -> pd.DataFrame:
    rows = []
    base = logs["do_nothing"]
    rules = logs["rules_only"]
    for name, log in logs.items():
        log = log.assign(
            discount_given=(log["discount_bps"] > 0).astype(float),
            discount_cost_cents=np.where(
                log["converted"], log["order_value_cents"] * log["discount_bps"] / 10_000, 0.0
            ),
            wasted_cost_cents=np.where(
                log["converted"] & log["would_buy_anyway"],
                log["order_value_cents"] * log["discount_bps"] / 10_000,
                0.0,
            ),
        )
        profit = _per_customer(log, "profit_cents", customers)
        expected = _per_customer(log, "expected_profit_cents", customers)
        lo, hi = bootstrap_interval(profit, weights, level)
        elo, ehi = bootstrap_interval(expected, weights, level)
        diff_base = expected - _per_customer(base, "expected_profit_cents", customers)
        diff_rules = expected - _per_customer(rules, "expected_profit_cents", customers)
        dblo, dbhi = bootstrap_interval(diff_base, weights, level)
        drlo, drhi = bootstrap_interval(diff_rules, weights, level)
        redeemed = log[(log["discount_bps"] > 0) & log["converted"]]
        anyway = log[log["would_buy_anyway"]]
        rows.append(
            {
                "policy": name,
                "label": POLICY_LABELS.get(name, name),
                "decisions": int(len(log)),
                "contact_rate": float(log["contact"].mean()),
                "discount_rate": float(log["discount_given"].mean()),
                "restraint_rate": float(log["archetype"].isin(["none", "wait"]).mean()),
                "conversions": int(log["converted"].sum()),
                "conversion_rate": float(log["converted"].mean()),
                "profit_eur": float(profit.sum() / 100),
                "profit_ci_low_eur": lo / 100,
                "profit_ci_high_eur": hi / 100,
                "expected_profit_eur": float(expected.sum() / 100),
                "expected_profit_ci_low_eur": elo / 100,
                "expected_profit_ci_high_eur": ehi / 100,
                "vs_do_nothing_eur": float(diff_base.sum() / 100),
                "vs_do_nothing_ci_low_eur": dblo / 100,
                "vs_do_nothing_ci_high_eur": dbhi / 100,
                "vs_rules_only_eur": float(diff_rules.sum() / 100),
                "vs_rules_only_ci_low_eur": drlo / 100,
                "vs_rules_only_ci_high_eur": drhi / 100,
                "discount_cost_eur": float(log["discount_cost_cents"].sum() / 100),
                "wasted_discount_cost_eur": float(log["wasted_cost_cents"].sum() / 100),
                "wasted_discount_share": (
                    float(redeemed["would_buy_anyway"].mean()) if len(redeemed) else 0.0
                ),
                "no_incentive_rate_would_buy_anyway": (
                    float((anyway["discount_bps"] == 0).mean()) if len(anyway) else 0.0
                ),
                "mean_regret_cents": float(log["regret_cents"].mean()),
                "share_hindsight_optimal": float((log["regret_cents"] <= 1e-9).mean()),
            }
        )
    return pd.DataFrame(rows)


def _readout(
    name: str,
    candidate: pd.DataFrame,
    control: pd.DataFrame,
    customers: list[str],
    weights: np.ndarray,
    level: float,
    days_running: int,
) -> Readout:
    """Per-decision profit and conversion-rate differences with paired bootstrap CIs."""
    n = len(candidate)
    diff_profit = _per_customer(candidate, "profit_cents", customers) - _per_customer(
        control, "profit_cents", customers
    )
    conv = candidate.assign(c=candidate["converted"].astype(float))
    conv_control = control.assign(c=control["converted"].astype(float))
    diff_conv = _per_customer(conv, "c", customers) - _per_customer(conv_control, "c", customers)
    plo, phi = bootstrap_interval(diff_profit, weights, level)
    clo, chi = bootstrap_interval(diff_conv, weights, level)
    return Readout(
        name=name,
        change_type="policy_promotion",
        primary=Estimate(diff_profit.sum() / n, plo / n, phi / n),
        guardrails={"conversion_rate": Estimate(diff_conv.sum() / n, clo / n, chi / n)},
        days_running=days_running,
    )


def _uplift_error(
    resolved: ResolvedConfig, root: Path | None, oracle: OutcomeOracle
) -> pd.DataFrame:
    """ADR-006 headline: predicted uplift (response-model delta) vs simulator ground truth on
    the out-of-time slice of the randomized experiment."""
    config = resolved.config
    log = read_frame("experiment_log", Zone.EXPERIMENT, root)
    test = log[(log["split"] == "test") & ~log["archetype"].isin(["none", "wait"])].reset_index(
        drop=True
    )
    names = context_feature_names([c.name for c in config.simulator.categories])
    truth = np.array(
        [
            oracle.uplift(
                str(row.customer_id),
                int(row.day),
                str(row.archetype),
                {"discount_bps": int(row.discount_bps)},
                int(row.prior_contacts),
            )
            for row in test.itertuples()
        ]
    )
    rows = []
    for family in FAMILIES:
        model = load_model(family, root)
        x = test[names].to_numpy(dtype=float)
        depth = (test["discount_bps"] / 10_000).to_numpy(dtype=float)
        pred = model.predict(x, test["archetype"].to_numpy(), depth) - model.predict(
            x, np.array(["none"] * len(x)), np.zeros(len(x))
        )
        groups = [("all", np.ones(len(test), dtype=bool))]
        groups += [
            (a, (test["archetype"] == a).to_numpy()) for a in sorted(test["archetype"].unique())
        ]
        for group, mask in groups:
            if mask.sum() < 2:
                continue
            t, p = truth[mask], pred[mask]
            rank_t = pd.Series(t).rank().to_numpy()
            rank_p = pd.Series(p).rank().to_numpy()
            rows.append(
                {
                    "family": family,
                    "archetype": group,
                    "rows": int(mask.sum()),
                    "mean_true_uplift": float(t.mean()),
                    "mean_predicted_uplift": float(p.mean()),
                    "bias": float((p - t).mean()),
                    "mae": float(np.abs(p - t).mean()),
                    "rmse": float(np.sqrt(((p - t) ** 2).mean())),
                    "spearman": float(np.corrcoef(rank_t, rank_p)[0, 1])
                    if np.std(rank_t) > 0 and np.std(rank_p) > 0
                    else float("nan"),
                    "sign_agreement": float((np.sign(p) == np.sign(t)).mean()),
                }
            )
    return pd.DataFrame(rows)


def _run_id(resolved: ResolvedConfig, root: Path | None, versions: dict[str, str]) -> str:
    digest = hashlib.sha256()
    digest.update(resolved.config_hash.encode())
    digest.update(content_hash(resolve_table_path("feature_grid", Zone.FEATURES, root)).encode())
    digest.update(json.dumps(versions, sort_keys=True).encode())
    return f"{resolved.profile}-{digest.hexdigest()[:10]}"


def run_evaluation(
    resolved: ResolvedConfig, root: Path | None = None, reports_dir: Path | None = None
) -> dict:
    config = resolved.config
    evaluation = config.evaluation
    train_end, validation_end, horizon = evaluation.windows(config.simulator.horizon_days)
    validation_days = list(range(train_end, validation_end, evaluation.replay_every_days))
    test_days = list(range(validation_end, horizon, evaluation.replay_every_days))
    store = ContextStore(
        resolved, root, days=validation_days + test_days, business_reference_cutoff=train_end
    )
    oracle = OutcomeOracle(resolved, root)
    rules = RuleSet.from_config(config.constraints)
    providers = build_providers(config.actions, ["catalog"])
    ev_config = config.policies.expected_value
    models = {family: load_model(family, root) for family in FAMILIES}

    def engine(policy, min_confidence=None) -> DecisionEngine:
        return DecisionEngine(
            policy, rules, providers, config.actions, resolved.config_hash, min_confidence
        )

    def ev_policy(family: str) -> ExpectedValuePolicy:
        return ExpectedValuePolicy(
            models[family], ev_config, store.categories, config.models.attribution_top_k
        )

    def replay(chooser, days, hindsight=True) -> pd.DataFrame:
        return rollout(
            store,
            oracle,
            rules,
            providers,
            config.actions,
            chooser,
            RolloutSpec(days=days, outcome_seed=evaluation.seeds.outcomes, hindsight=hindsight),
        )

    # 1. model-family selection on the validation window
    selection = {}
    for family in FAMILIES:
        log = replay(
            _engine_chooser(engine(ev_policy(family), ev_config.min_confidence), False),
            validation_days,
            hindsight=False,
        )
        selection[family] = float(log["profit_cents"].sum())
    selected = (
        max(FAMILIES, key=lambda f: (selection[f], f == "logistic"))
        if ev_config.family == "auto"
        else ev_config.family
    )

    # 2. test replay of every policy
    logs: dict[str, pd.DataFrame] = {}
    for policy in baseline_policies(config.policies.baselines):
        logs[policy.name] = replay(_engine_chooser(engine(policy), False), test_days)
    for family in FAMILIES:
        name = f"expected_value_{family}"
        logs[name] = replay(
            _engine_chooser(
                engine(ev_policy(family), ev_config.min_confidence), family == selected
            ),
            test_days,
        )
    logs["oracle_upper_bound"] = replay(_oracle_chooser(oracle), test_days)
    ml_name = f"expected_value_{selected}"

    customers = sorted(
        set().union(*(set(log["customer_id"]) for log in logs.values())),
        key=lambda c: (len(c), c),
    )
    rng = np.random.Generator(np.random.PCG64(evaluation.seeds.bootstrap))
    weights = rng.multinomial(
        len(customers),
        np.full(len(customers), 1 / len(customers)),
        size=evaluation.bootstrap_resamples,
    ).astype(float)
    summary = _summaries(logs, customers, weights, evaluation.ci_level)
    summary["is_ml_policy"] = summary["policy"] == ml_name

    days_running = int(test_days[-1] - test_days[0] + evaluation.replay_every_days)
    verdicts = []
    for control in ("rules_only", "do_nothing"):
        readout = _readout(
            f"{ml_name} vs {control}",
            logs[ml_name],
            logs[control],
            customers,
            weights,
            evaluation.ci_level,
            days_running,
        )
        verdict = adjudicate(readout, config.experiments, config.autonomy)
        verdicts.append(
            {
                "comparison": readout.name,
                "control": control,
                "primary_metric": config.experiments.primary_metric,
                "point": readout.primary.point,
                "ci_low": readout.primary.ci_low,
                "ci_high": readout.primary.ci_high,
                "conversion_rate_diff": readout.guardrails["conversion_rate"].point,
                "conversion_rate_ci_low": readout.guardrails["conversion_rate"].ci_low,
                "conversion_rate_ci_high": readout.guardrails["conversion_rate"].ci_high,
                "days_running": readout.days_running,
                "verdict": verdict.verdict,
                "case": verdict.case,
                "autonomy": verdict.autonomy,
                "reason": verdict.reason,
            }
        )
    verdict_frame = pd.DataFrame(verdicts)

    uplift = _uplift_error(resolved, root, oracle)
    overrides = evaluate_overrides(read_overrides(root), store, oracle)
    versions = {family: models[family].version for family in FAMILIES}
    run_id = _run_id(resolved, root, versions)

    # system axis: single-decision latency on this machine (reported, not published as exact)
    sample_day = test_days[0]
    rows = store.day_rows(sample_day)
    sample = [
        store.context(c, sample_day, row=rows[c])
        for c in store.eligible_customers(sample_day, rows)[:50]
    ]
    ml_engine = engine(ev_policy(selected), ev_config.min_confidence)
    timings = []
    for context in sample:
        start = time.perf_counter()
        ml_engine.decide(context)
        timings.append((time.perf_counter() - start) * 1000)

    decisions = pd.concat(
        [log.assign(policy=name) for name, log in logs.items()], ignore_index=True
    )
    decisions = _typed(decisions)
    inputs = (
        resolve_table_path("feature_grid", Zone.FEATURES, root),
        resolve_table_path("experiment_log", Zone.EXPERIMENT, root),
    )

    def save(frame: pd.DataFrame, name: str, key: tuple[str, ...]) -> Path:
        return write_frame(
            frame,
            name,
            Zone.EVALUATION,
            key,
            resolved,
            Stage.EVALUATE,
            inputs,
            extra_metadata={"run_id": run_id},
            root=root,
        )

    save(decisions, "replay_decisions", ("policy", "day", "customer_id"))
    save(summary, "policy_summary", ("policy",))
    save(uplift, "uplift_error", ("family", "archetype"))
    save(verdict_frame, "gateway_verdicts", ("control",))
    save(overrides, "override_outcomes", ("override_id",))

    context = {
        "run_id": run_id,
        "profile": resolved.profile,
        "config_hash": resolved.config_hash,
        "model_versions": versions,
        "selected_family": selected,
        "ml_policy": ml_name,
        "validation_profit_eur": {k: v / 100 for k, v in selection.items()},
        "windows": {
            "train": [config.evaluation.warmup_days, train_end],
            "validation": [train_end, validation_end],
            "test": [validation_end, horizon],
        },
        "test_days": len(test_days),
        "customers": len(customers),
        "latency_ms": {
            "p50": float(np.percentile(timings, 50)) if timings else float("nan"),
            "p95": float(np.percentile(timings, 95)) if timings else float("nan"),
        },
        "start_date": config.simulator.start_date.isoformat(),
    }
    out_dir = reports_dir or (REPO_ROOT / "reports" / resolved.profile / "evaluation")
    write_reports(out_dir, context, summary, verdict_frame, uplift, logs, overrides, resolved, root)
    context["reports_dir"] = str(out_dir)
    return context


def _typed(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    for column in (
        "day",
        "discount_bps",
        "n_survivors",
        "n_filtered",
        "recent_contacts_7d",
        "prior_contacts",
    ):
        frame[column] = frame[column].astype("int64")
    for column in ("contact", "converted", "would_buy_anyway"):
        frame[column] = frame[column].astype(bool)
    frame["needs_human_review"] = (
        frame["needs_human_review"].astype("boolean").fillna(False).astype(bool)
    )
    for column in ("decision_id", "runner_up", "reasoning"):
        frame[column] = frame[column].fillna("").astype(str)
    for column in ("confidence", "uplift_estimate", "expected_profit_estimate_cents"):
        frame[column] = frame[column].astype(float)
    return frame
