"""Published report files for one evaluation run (`reports/<profile>/evaluation/`).

Every table is written as CSV with fixed float formatting so a rerun of the same seeded
profile reproduces it byte for byte (AC-11); machine-dependent measurements (latency) go to
`runtime.json`, which is excluded from that guarantee. Every file names the run id, and the
first line of every Markdown file states that the numbers come from simulation (ADR-004).
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from nextmove.config.loader import ResolvedConfig  # noqa: E402
from nextmove.models.features import context_feature_names  # noqa: E402
from nextmove.models.train import FAMILIES, load_model  # noqa: E402
from nextmove.storage import Zone, read_frame, resolve_artifact_path  # noqa: E402

__all__ = ["CAVEAT", "write_reports"]

CAVEAT = (
    "> **Simulated data only.** Every number in this file comes from the seeded NextMove "
    "simulator (ADR-004); none describes real customers, revenue or production use."
)

# Reference palette (dataviz skill): one highlight hue for the engine, neutral for the rest.
_SURFACE = "#fcfcfb"
_TEXT = "#0b0b0b"
_TEXT_2 = "#52514e"
_GRID = "#e4e3df"
_HIGHLIGHT = "#2a78d6"
_NEUTRAL = "#9a9890"
_REFERENCE = "#c9c7c0"


def _csv(frame: pd.DataFrame, path: Path) -> None:
    path.write_text(frame.to_csv(index=False, float_format="%.6f", lineterminator="\n"), "utf-8")


def _style(ax) -> None:
    ax.set_facecolor(_SURFACE)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(_GRID)
    ax.tick_params(colors=_TEXT_2, labelsize=9)
    ax.grid(axis="x", color=_GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def _policy_chart(summary: pd.DataFrame, run_id: str, path: Path) -> None:
    data = summary[summary["policy"] != "do_nothing"].copy()
    data = data.sort_values("vs_do_nothing_eur")
    fig, ax = plt.subplots(figsize=(8.6, 4.2), dpi=150)
    fig.patch.set_facecolor(_SURFACE)
    _style(ax)
    y = np.arange(len(data))
    colors = [
        _HIGHLIGHT if ml else (_REFERENCE if p == "oracle_upper_bound" else _NEUTRAL)
        for p, ml in zip(data["policy"], data["is_ml_policy"], strict=True)
    ]
    values = data["vs_do_nothing_eur"].to_numpy()
    low = values - data["vs_do_nothing_ci_low_eur"].to_numpy()
    high = data["vs_do_nothing_ci_high_eur"].to_numpy() - values
    ax.barh(y, values, height=0.55, color=colors, zorder=2)
    ax.errorbar(
        values, y, xerr=[low, high], fmt="none", ecolor=_TEXT, elinewidth=1.2, capsize=3, zorder=3
    )
    ax.axvline(0, color=_TEXT_2, linewidth=1)
    ax.set_yticks(y, data["label"], color=_TEXT)
    span = max(
        np.abs(data["vs_do_nothing_ci_low_eur"]).max(),
        np.abs(data["vs_do_nothing_ci_high_eur"]).max(),
    )
    for yi, v, hi in zip(y, values, data["vs_do_nothing_ci_high_eur"], strict=True):
        ax.text(
            max(v, hi, 0) + span * 0.03, yi, f"€{v:,.0f}", va="center", fontsize=9, color=_TEXT_2
        )
    right = max(float(data["vs_do_nothing_ci_high_eur"].max()), 0.0)
    ax.set_xlim(
        min(-span * 0.05, data["vs_do_nothing_ci_low_eur"].min() * 1.1), right + span * 0.25
    )
    ax.set_xlabel(
        "Expected profit vs. doing nothing over the test window (€, 95% CI)",
        color=_TEXT_2,
        fontsize=9,
    )
    ax.set_title(
        "Policy comparison — simulated data",
        loc="left",
        color=_TEXT,
        fontsize=12,
        fontweight="bold",
    )
    fig.text(0.01, 0.01, f"Run {run_id} · in simulation only (ADR-004)", color=_TEXT_2, fontsize=7)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(path, facecolor=_SURFACE, metadata={"Software": None})
    plt.close(fig)


def _reliability_chart(reliability: pd.DataFrame, run_id: str, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(5.2, 4.2), dpi=150)
    fig.patch.set_facecolor(_SURFACE)
    _style(ax)
    ax.grid(axis="both", color=_GRID, linewidth=0.8)
    test = reliability[reliability["split"] == "test"]
    top = float(max(test["bin_mean_predicted"].max(), test["bin_observed_rate"].max()) * 1.1)
    ax.plot([0, top], [0, top], color=_TEXT_2, linewidth=1, linestyle="--", label="Perfect")
    for family, color in (("logistic", _NEUTRAL), ("gbm", _HIGHLIGHT)):
        part = test[test["family"] == family]
        ax.plot(
            part["bin_mean_predicted"],
            part["bin_observed_rate"],
            marker="o",
            markersize=4,
            linewidth=2,
            color=color,
            label=family,
        )
    ax.set_xlabel("Mean predicted purchase probability", color=_TEXT_2, fontsize=9)
    ax.set_ylabel("Observed purchase rate", color=_TEXT_2, fontsize=9)
    ax.set_title(
        "Calibration, test window — simulated",
        loc="left",
        color=_TEXT,
        fontsize=11,
        fontweight="bold",
    )
    ax.legend(frameon=False, fontsize=8, labelcolor=_TEXT_2)
    fig.text(0.01, 0.01, f"Run {run_id}", color=_TEXT_2, fontsize=7)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(path, facecolor=_SURFACE, metadata={"Software": None})
    plt.close(fig)


def _fmt_eur(value: float) -> str:
    rounded = round(float(value))
    if rounded == 0:
        return "€0"
    return f"−€{abs(rounded):,}" if rounded < 0 else f"€{rounded:,}"


def _ci(row, key: str) -> str:
    return (
        f"{_fmt_eur(row[key + '_eur'])} [{_fmt_eur(row[key + '_ci_low_eur'])}, "
        f"{_fmt_eur(row[key + '_ci_high_eur'])}]"
    )


def _global_importance(family: str, resolved: ResolvedConfig, root: Path | None) -> pd.DataFrame:
    """Mean |uplift attribution| for `recommend` over a fixed sample of test-window rows."""
    model = load_model(family, root)
    log = read_frame("experiment_log", Zone.EXPERIMENT, root)
    names = context_feature_names([c.name for c in resolved.config.simulator.categories])
    sample = log[log["split"] == "test"].head(300)
    totals: dict[str, float] = {}
    for x in sample[names].to_numpy(dtype=float):
        for feature, weight in model.uplift_attributions(x, "recommend", 0.0):
            totals[feature] = totals.get(feature, 0.0) + abs(weight)
    frame = pd.DataFrame(
        {
            "feature": list(totals),
            "mean_abs_attribution": [v / max(len(sample), 1) for v in totals.values()],
        }
    )
    return frame.sort_values(["mean_abs_attribution", "feature"], ascending=[False, True])


def _model_card(
    family: str,
    context: dict,
    metrics: pd.DataFrame,
    uplift: pd.DataFrame,
    importance: pd.DataFrame,
    resolved: ResolvedConfig,
) -> str:
    cfg = resolved.config
    m = metrics[(metrics["family"] == family) & (metrics["archetype"] == "all")]
    selected = context["selected_family"] == family
    u = uplift[(uplift["family"] == family) & (uplift["archetype"] == "all")]
    lines = [
        f"# Model card: response model `{family}`",
        "",
        CAVEAT,
        "",
        f"- **Run:** `{context['run_id']}` · **model version:** "
        f"`{context['model_versions'][family]}` · **config hash:** `{context['config_hash'][:12]}`",
        "- **Decision-path status:** "
        + (
            "selected for the decision path (highest validation-window replay profit)"
            if selected
            else "challenger, comparison study only"
        ),
        "",
        "## Intended use",
        "",
        "Predict the probability that a customer buys at their next visit given one action "
        "from the catalog (or none), so the decision engine can rank actions by expected "
        "incremental profit (uplift = P(buy | action) − P(buy | none), ADR-006). Not intended "
        "for any use outside the simulated NextMove world.",
        "",
        "## Data",
        "",
        "Randomized A/B/n experiment log (ADR-012): each eligible simulated customer received a "
        "uniformly random action among those allowed by the hard constraints. Temporal splits "
        f"only: train days {context['windows']['train']}, validation "
        f"{context['windows']['validation']}, test {context['windows']['test']}.",
        "",
        "## Model",
        "",
        (
            "Logistic regression on standardized context features, action indicators and "
            "action × feature interactions"
            if family == "logistic"
            else "LightGBM gradient-boosted trees on context features, the action archetype "
            "(categorical) and discount depth"
        )
        + f"; bootstrap ensemble of {cfg.models.ensemble_size} members resampled by customer; "
        "Platt calibration on the validation window. Seeded and single-threaded.",
        "",
        "Features: "
        + ", ".join(
            f"`{n}`" for n in context_feature_names([c.name for c in cfg.simulator.categories])
        )
        + ". Customers who never ordered get "
        "`has_ordered = 0` and a capped recency (explicit, not silent imputation).",
        "",
        "## Metrics (prediction axis)",
        "",
        "| Split | Rows | Purchase rate | Mean predicted | Brier | Brier skill | ROC AUC | ECE |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for split in ("train", "validation", "test"):
        r = m[m["split"] == split]
        if len(r):
            r = r.iloc[0]
            lines.append(
                f"| {split} | {int(r['rows']):,} | {r['positive_rate']:.4f} | "
                f"{r['mean_predicted']:.4f} | {r['brier']:.5f} | "
                f"{r['brier_skill_vs_base_rate']:+.4f} | {r['roc_auc']:.3f} | {r['ece']:.4f} |"
            )
    lines += [
        "",
        f"**Calibration gate (AC-5):** test-window ECE must be ≤ "
        f"{cfg.models.calibration.max_ece}; the train stage fails otherwise. This model passed.",
        "",
        "## Uplift approximation error (ADR-006)",
        "",
    ]
    if len(u):
        r = u.iloc[0]
        lines.append(
            f"On {int(r['rows']):,} out-of-time experiment rows with an active action: mean true "
            f"uplift {r['mean_true_uplift'] * 100:+.2f} pp, mean predicted "
            f"{r['mean_predicted_uplift'] * 100:+.2f} pp, MAE {r['mae'] * 100:.2f} pp, rank "
            f"correlation {r['spearman']:.2f}, sign agreement {r['sign_agreement']:.0%}."
        )
    lines += [
        "",
        "## Attributions",
        "",
        "Per-decision attributions explain the uplift logit for the chosen (or best "
        "alternative) action: "
        + (
            "exact coefficient contributions"
            if family == "logistic"
            else "exact TreeSHAP values (`pred_contrib`) differenced against `none`"
        )
        + ". Global view, mean |attribution| for `recommend` over 300 test rows:",
        "",
        "| Feature | Mean abs. attribution (logit) |",
        "|---|---:|",
    ]
    for _, r in importance.head(8).iterrows():
        lines.append(f"| `{r['feature']}` | {r['mean_abs_attribution']:.4f} |")
    lines += [
        "",
        "## Limitations",
        "",
        "- Trained and evaluated on simulated data only; the simulator's documented response "
        "function is the ground truth (`docs/SIMULATOR_ASSUMPTIONS.md`).",
        "- Observable features carry little signal about the latent traits that drive "
        "purchases (low AUC); the model is useful mainly for the *direction* of action effects.",
        "- Uplift is a difference of two predictions, not a dedicated uplift learner (DEBT-001).",
        "- Calibration is checked on aggregate and per action; it can still drift outside the "
        "evaluated season.",
        "",
    ]
    return "\n".join(lines)


def write_reports(
    out_dir: Path,
    context: dict,
    summary: pd.DataFrame,
    verdicts: pd.DataFrame,
    uplift: pd.DataFrame,
    logs: dict[str, pd.DataFrame],
    overrides: pd.DataFrame,
    resolved: ResolvedConfig,
    root: Path | None,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "model_cards").mkdir(exist_ok=True)
    run_id = context["run_id"]
    published = {k: v for k, v in context.items() if k != "latency_ms"}
    (out_dir / "summary.json").write_text(json.dumps(published, indent=2, sort_keys=True) + "\n")
    (out_dir / "runtime.json").write_text(
        json.dumps({"run_id": run_id, "latency_ms": context["latency_ms"]}, indent=2) + "\n"
    )
    _csv(summary.assign(run_id=run_id), out_dir / "policy_comparison.csv")
    _csv(verdicts.assign(run_id=run_id), out_dir / "gateway_verdicts.csv")
    _csv(uplift.assign(run_id=run_id), out_dir / "uplift_error.csv")
    metrics = read_frame("model_metrics", Zone.MODELS, root)
    _csv(metrics.assign(run_id=run_id), out_dir / "model_metrics.csv")
    reliability = read_frame("reliability", Zone.MODELS, root)
    _csv(reliability.assign(run_id=run_id), out_dir / "reliability.csv")
    _csv(overrides.assign(run_id=run_id), out_dir / "override_outcomes.csv")
    _policy_chart(summary, run_id, out_dir / "policy_comparison.png")
    _reliability_chart(reliability, run_id, out_dir / "calibration.png")

    scorecard = json.loads(
        resolve_artifact_path("segmentation_scorecard.json", Zone.MODELS, root).read_text()
    )
    (out_dir / "segmentation_scorecard.json").write_text(
        json.dumps(scorecard, indent=2, sort_keys=True) + "\n"
    )
    segments = read_frame("segments", Zone.MODELS, root)
    analysis = _analysis_tables(context, logs, segments)
    for name, frame in analysis.items():
        frame = frame.reset_index() if name == "rule_shares" else frame
        _csv(frame.assign(run_id=run_id), out_dir / f"{name}.csv")

    for family in FAMILIES:
        importance = _global_importance(family, resolved, root)
        card = _model_card(family, context, metrics, uplift, importance, resolved)
        (out_dir / "model_cards" / f"{family}.md").write_text(card, "utf-8")

    (out_dir / "evaluation_report.md").write_text(
        _report(context, summary, verdicts, uplift, metrics, analysis, scorecard, overrides),
        "utf-8",
    )


def _analysis_tables(
    context: dict, logs: dict[str, pd.DataFrame], segments: pd.DataFrame
) -> dict[str, pd.DataFrame]:
    ml = logs[context["ml_policy"]]
    base = logs["do_nothing"]
    discount = logs["always_discount"]
    seg = segments.set_index("customer_id")["segment_name"]
    start = pd.Timestamp(context["start_date"])

    def tag(frame: pd.DataFrame) -> pd.DataFrame:
        frame = frame.copy()
        frame["segment"] = frame["customer_id"].map(seg).fillna("joined_after_snapshot")
        frame["month"] = (start + pd.to_timedelta(frame["day"], unit="D")).dt.strftime("%Y-%m")
        return frame

    ml, base, discount = tag(ml), tag(base), tag(discount)
    key = ["customer_id", "day"]
    merged = ml.merge(base[key + ["expected_profit_cents"]], on=key, suffixes=("", "_base"))
    merged = merged.merge(
        discount[key + ["expected_profit_cents"]].rename(
            columns={"expected_profit_cents": "expected_profit_cents_discount"}
        ),
        on=key,
    )
    merged["gain_vs_nothing"] = (
        merged["expected_profit_cents"] - merged["expected_profit_cents_base"]
    )
    merged["gain_vs_discount"] = (
        merged["expected_profit_cents"] - merged["expected_profit_cents_discount"]
    )

    def group(by: str) -> pd.DataFrame:
        out = merged.groupby(by).agg(
            decisions=("customer_id", "size"),
            contact_rate=("contact", "mean"),
            ml_vs_do_nothing_eur=("gain_vs_nothing", lambda s: s.sum() / 100),
            ml_vs_always_discount_eur=("gain_vs_discount", lambda s: s.sum() / 100),
            mean_regret_cents=("regret_cents", "mean"),
        )
        return out.reset_index()

    bins = pd.cut(merged["confidence"], [0, 0.5, 0.75, 0.9, 1.0001], right=False)
    merged["confidence_bin"] = bins.astype(str)
    merged["hindsight_optimal"] = merged["regret_cents"] <= 1e-9
    confidence = (
        merged.groupby("confidence_bin")
        .agg(
            decisions=("customer_id", "size"),
            mean_confidence=("confidence", "mean"),
            share_hindsight_optimal=("hindsight_optimal", "mean"),
            mean_regret_cents=("regret_cents", "mean"),
        )
        .reset_index()
    )
    actions = (
        merged.groupby("candidate_id")
        .agg(
            decisions=("customer_id", "size"),
            mean_predicted_uplift=("uplift_estimate", "mean"),
            mean_true_uplift=("p_action", "mean"),
            mean_p_none=("p_none", "mean"),
            mean_regret_cents=("regret_cents", "mean"),
        )
        .reset_index()
    )
    actions["mean_true_uplift"] = actions["mean_true_uplift"] - actions["mean_p_none"]
    actions = actions.drop(columns=["mean_p_none"])
    fired = logs["always_discount"]["fired_rules"].fillna("")
    rule_names = sorted({r for value in fired for r in value.split(",") if r})
    rule_shares = pd.DataFrame(
        {
            "rule": rule_names,
            "share": [
                float(fired.str.split(",").apply(lambda xs, r=r: r in xs).mean())
                for r in rule_names
            ],
        }
    ).set_index("rule")
    for required in ("inventory_scarcity_gate", "frequency_cap"):
        if required not in rule_shares.index:
            rule_shares.loc[required] = 0.0
    return {
        "rule_shares": rule_shares,
        "human_review": pd.DataFrame(
            {"escalations": [int(ml["needs_human_review"].fillna(False).astype(bool).sum())]}
        ),
        "by_segment": group("segment"),
        "by_month": group("month"),
        "confidence_calibration": confidence,
        "ml_actions": actions,
    }


def _report(context, summary, verdicts, uplift, metrics, analysis, scorecard, overrides) -> str:
    s = summary.set_index("policy")
    ml = s.loc[context["ml_policy"]]
    nothing = s.loc["do_nothing"]
    disc = s.loc["always_discount"]
    rules = s.loc["rules_only"]
    oracle = s.loc["oracle_upper_bound"]
    shares = analysis["rule_shares"]
    beats_rules = ml["vs_rules_only_ci_low_eur"] > 0
    beats_nothing = ml["vs_do_nothing_ci_low_eur"] > 0
    lines = [
        "# NextMove evaluation report",
        "",
        CAVEAT,
        "",
        f"**Run** `{context['run_id']}` · profile `{context['profile']}` · config hash "
        f"`{context['config_hash'][:12]}` · models "
        + ", ".join(f"`{v}`" for v in context["model_versions"].values()),
        "",
        f"Test window: days {context['windows']['test'][0]}–{context['windows']['test'][1]} "
        f"({context['test_days']} weekly decision rounds, {context['customers']:,} simulated "
        "customers). Every policy is replayed on the same customers, days and random draws "
        "(common random numbers, ADR-012); intervals are 95% customer-bootstrap intervals.",
        "",
        "## Headline",
        "",
        f"- In simulation, the decision engine ({context['ml_policy']}) chose to do nothing or "
        f"wait in {ml['restraint_rate']:.0%} of customer-weeks and earned "
        f"{_fmt_eur(ml['expected_profit_eur'] - disc['expected_profit_eur'])} "
        "more expected profit than always discounting.",
        f"- Always-discount gave a discount in {disc['discount_rate']:.0%} of decisions (the "
        f"low-stock gate fired in {shares.loc['inventory_scarcity_gate', 'share']:.0%} "
        f"and the weekly contact cap in {shares.loc['frequency_cap', 'share']:.0%} "
        "of its decisions); "
        f"{disc['wasted_discount_share']:.0%} of its redeemed discounts went to customers who "
        f"would have bought anyway ({_fmt_eur(disc['wasted_discount_cost_eur'])} of discount "
        "spend).",
        f"- Against the rules-only playbook the engine's expected profit difference is "
        f"{_ci(ml, 'vs_rules_only')}; against doing nothing it is {_ci(ml, 'vs_do_nothing')}.",
        "- Verdict (AC-6): the learned policy "
        + ("**beats**" if beats_rules else "**does not beat**")
        + " the rule baseline with a 95% interval above zero"
        + ("." if beats_rules else "; the report states this and the baseline ships.")
        + (
            " It also beats doing nothing."
            if beats_nothing
            else " It does not beat doing nothing: in this simulated world restraint is close "
            "to optimal, so the engine's value lies in avoiding contacts that cost profit."
        ),
        f"- The hindsight oracle, which knows the simulator's true response function, is the "
        f"ceiling: {_ci(oracle, 'vs_do_nothing')} over doing nothing.",
        "",
        "## Decision axis — policy comparison (AC-10)",
        "",
        "![Policy comparison](policy_comparison.png)",
        "",
        "| Policy | Decisions | Contact rate | Discount rate | Conversions | Realized profit "
        "[95% CI] | Expected profit vs. do nothing [95% CI] | Wasted-discount share | "
        "Mean regret (¢) |",
        "|---|---:|---:|---:|---:|---|---|---:|---:|",
    ]
    for _policy, r in s.iterrows():
        lines.append(
            f"| {r['label']}{' **(ML policy)**' if r['is_ml_policy'] else ''} | "
            f"{int(r['decisions']):,} | {r['contact_rate']:.1%} | {r['discount_rate']:.1%} | "
            f"{int(r['conversions']):,} | {_ci(r, 'profit')} | {_ci(r, 'vs_do_nothing')} | "
            f"{r['wasted_discount_share']:.0%} | {r['mean_regret_cents']:.2f} |"
        )
    lines += [
        "",
        "Regret is the gap, per decision, between the hindsight-best allowed action and the "
        "chosen one, in expected profit. *Wasted-discount share*: redeemed discounts whose "
        "customer would have bought without one (same random draw, lower probability).",
        "",
        f"No-incentive rate for would-buy-anyway customers: engine "
        f"{ml['no_incentive_rate_would_buy_anyway']:.0%}, rules-only "
        f"{rules['no_incentive_rate_would_buy_anyway']:.0%}, always-discount "
        f"{disc['no_incentive_rate_would_buy_anyway']:.0%}, do-nothing "
        f"{nothing['no_incentive_rate_would_buy_anyway']:.0%}.",
        "",
        "## 3WD gateway verdicts (AC-8)",
        "",
        "| Comparison | Profit / decision (¢) [95% CI] | Conversion-rate diff [95% CI] | Verdict | "
        "Autonomy | Reason |",
        "|---|---|---|---|---|---|",
    ]
    for _, v in verdicts.iterrows():
        lines.append(
            f"| {v['comparison']} | {v['point']:+.3f} [{v['ci_low']:+.3f}, {v['ci_high']:+.3f}] | "
            f"{v['conversion_rate_diff']:+.4f} [{v['conversion_rate_ci_low']:+.4f}, "
            f"{v['conversion_rate_ci_high']:+.4f}] | **{v['verdict']}** | {v['autonomy']} | "
            f"{v['reason']} |"
        )
    test = metrics[(metrics["split"] == "test") & (metrics["archetype"] == "all")]
    lines += [
        "",
        "Policy promotion is a Tier 2 change (ADR-009): even an Accept needs human sign-off.",
        "",
        "## Prediction axis (AC-5)",
        "",
        "![Calibration](calibration.png)",
        "",
        "| Family | Test rows | Brier | Brier skill | ROC AUC | ECE |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for _, r in test.iterrows():
        lines.append(
            f"| {r['family']} | {int(r['rows']):,} | {r['brier']:.5f} | "
            f"{r['brier_skill_vs_base_rate']:+.4f} | {r['roc_auc']:.3f} | {r['ece']:.4f} |"
        )
    lines += [
        "",
        f"Selected for the decision path: **{context['selected_family']}** (higher realized "
        "profit on the validation-window replay: "
        + ", ".join(f"{k} {_fmt_eur(v)}" for k, v in context["validation_profit_eur"].items())
        + "). Model cards: [logistic](model_cards/logistic.md), [gbm](model_cards/gbm.md).",
        "",
        "## Uplift approximation error (ADR-006)",
        "",
        "Predicted uplift (difference of two response-model predictions) against the "
        "simulator's ground-truth uplift, on out-of-time randomized-experiment rows:",
        "",
        "| Family | Action | Rows | True uplift (pp) | Predicted (pp) | Bias (pp) | MAE (pp) | "
        "Rank corr. | Sign agreement |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for _, r in uplift.iterrows():
        lines.append(
            f"| {r['family']} | {r['archetype']} | {int(r['rows']):,} | "
            f"{r['mean_true_uplift'] * 100:+.2f} | {r['mean_predicted_uplift'] * 100:+.2f} | "
            f"{r['bias'] * 100:+.2f} | {r['mae'] * 100:.2f} | {r['spearman']:.2f} | "
            f"{r['sign_agreement']:.0%} |"
        )
    conf = analysis["confidence_calibration"]
    lines += [
        "",
        "## Decision quality and confidence",
        "",
        f"The engine picked the hindsight-optimal allowed action in "
        f"{ml['share_hindsight_optimal']:.0%} of decisions (rules-only "
        f"{rules['share_hindsight_optimal']:.0%}, do-nothing "
        f"{nothing['share_hindsight_optimal']:.0%}). Confidence vs. correctness:",
        "",
        "| Confidence bin | Decisions | Mean confidence | Hindsight-optimal share "
        "| Mean regret (¢) |",
        "|---|---:|---:|---:|---:|",
    ]
    for _, r in conf.iterrows():
        lines.append(
            f"| {r['confidence_bin']} | {int(r['decisions']):,} | {r['mean_confidence']:.2f} | "
            f"{r['share_hindsight_optimal']:.0%} | {r['mean_regret_cents']:.2f} |"
        )
    seg = analysis["by_segment"]
    month = analysis["by_month"]
    worst_month = month.sort_values("ml_vs_do_nothing_eur").iloc[0] if len(month) else None
    lines += [
        "",
        "## Segments (AC-7) and the customer view",
        "",
        f"Segmentation chosen by TOPSIS: **{scorecard['chosen']}** among "
        f"{len(scorecard.get('candidates', {}))} candidates (scorecard: "
        "[segmentation_scorecard.json](segmentation_scorecard.json)).",
        "",
        "| Segment | Decisions | Engine contact rate | Engine vs. do nothing | Engine vs. always "
        "discount | Mean regret (¢) |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for _, r in seg.iterrows():
        lines.append(
            f"| {r['segment']} | {int(r['decisions']):,} | {r['contact_rate']:.1%} | "
            f"{_fmt_eur(r['ml_vs_do_nothing_eur'])} | {_fmt_eur(r['ml_vs_always_discount_eur'])} "
            f"| {r['mean_regret_cents']:.2f} |"
        )
    lines += [
        "",
        "## System axis",
        "",
        f"- Decisions replayed: {int(s['decisions'].sum()):,} across "
        f"{len(s)} policies; every one passed the `Decision` contract validation.",
        "- Hard-constraint violations: 0 by construction (policies rank survivors only) and "
        "by test (AC-2, 10,000 randomized contexts through the engine).",
        f"- Human-review escalations in the engine replay: "
        f"{int(analysis['human_review']['escalations'].iloc[0])}.",
        "- Single-decision latency on the build machine: see `runtime.json` "
        "(machine-dependent, excluded from the reproducibility guarantee).",
        "",
        "## Failure analysis",
        "",
        "- **Restraint dominates this world.** The existing campaign calendar already "
        "contacts simulated customers about twice a week, and the simulator's fatigue counter "
        "never decays, so most extra contact lowers purchase probability. The hindsight "
        f"oracle itself does nothing in {oracle['restraint_rate']:.0%} of decisions. Any policy "
        "that contacts often (top-seller, always-discount) loses money here.",
        "- **Weak observable signal.** Observable features explain little of the latent "
        "traits that drive purchases (test ROC AUC close to 0.5), so the models mainly learn "
        "the average direction of each action's effect, not who responds.",
        "- **Uplift is a difference of two noisy predictions** (DEBT-001); see the error table "
        "above for its size per action.",
    ]
    if worst_month is not None:
        lines.append(
            f"- **Worst month for the engine vs. doing nothing:** {worst_month['month']} "
            f"({_fmt_eur(worst_month['ml_vs_do_nothing_eur'])})."
        )
    lines += [
        "- **Open-loop replay** (DEBT-005): replayed actions change contact history and fatigue "
        "but not later browsing or stock.",
        "",
        "## Operator overrides (UC1, D4)",
        "",
    ]
    if len(overrides):
        lines.append(
            f"{len(overrides)} logged override(s); net expected-profit effect versus the "
            f"engine's choice: {overrides['override_effect_cents'].sum() / 100:+.2f} €."
        )
    else:
        lines.append("No overrides were logged for this run (overrides come from the demo/API).")
    lines += [
        "",
        "## Limitations",
        "",
        "- All results are in simulation; no claim transfers to real customers without "
        "re-validation on real data.",
        "- The outcome is one purchase response at the next visit (ADR-012); longer-run "
        "effects (habit, churn) are not modeled.",
        "- MCDA weights are hand-set (DEBT-004); 3WD thresholds are static (DEBT-002).",
        "",
    ]
    return "\n".join(lines)
