# RESEARCH_SYNTHESIS.md

**Corpus:** 18 unique sources (2 duplicates removed): the anchor framework paper (Wasilewski & Ramsey 2025, IEEE Access — adaptive e-commerce UI personalization validated on 438,261 + 99,193 real sessions), the three-way decision model (Wasilewski & Sobecki 2026, MAKE), two MCDA clustering-selection papers (Egyptian Informatics Journal; Applied Soft Computing), TWN+MAB nudge optimization for digital banking (Kristiana et al. 2025, IEEE Access), semi-adaptive acceptance study (Alotaibi, TAM, n=60), privacy–well-being trade-off (Aydin 2026, Sustainability), AI & customer loyalty (Beyari 2025), adaptive mobile-banking UI (Hasan et al., Array), MSME adaptive-UI systematic review (Solehatin et al. 2026), AI-generated content personalization (Wasilewski, Chawla & Pralat 2025), multi-view adaptive personalization thesis (Gstrein 2009), recommendation/behavior study (Wang & Shi), AI-UX personalization overview (Perelekhov 2026), GenUI practitioner transcript, hyperpersonalization UX essay (O'Sullivan 2025), user-persona design guide, plus two lower-relevance sources (sustainable design thesis; multi-user collaborative interface method) used only as background.

This document extracts engineering-usable knowledge; it does not summarize papers.

---

## 1. Distilled Principles

| # | Principle | Evidence | Design implication |
|---|---|---|---|
| 1 | **Optimize decisions, not predictions.** Prediction accuracy does not imply incremental revenue; models that predict organic behavior add nothing. | Synthesis metrics catalog ("perfect accuracy can fail to drive incremental revenue"); Kristiana et al. framing of nudge selection as bandit decision problem. | The system's contract is a *decision object*; models are internal components scored by decision value, not leaderboard metrics. |
| 2 | **Business constraints belong inside model selection, not after it.** Context-free metrics (Silhouette, Davies-Bouldin) produce economically unviable segments. | Both clustering papers; anchor paper's contextual algorithm blends statistical indices with business constraints; synthesis Category 3 explicitly deprecates purity optimization. | MCDA wrapper (TOPSIS/PROMETHEE II class) with min-cluster-size, max-clusters, resource-cost criteria is a *core* module, not an add-on. |
| 3 | **Semi-adaptive beats both extremes.** Fully adaptive UIs disorient and destroy trust; fully adaptable UIs are ignored (paradox of the active user). | Alotaibi (semi-adaptive ranked first on PEOU, PB, BA); synthesis Category 1 #1; hyperpersonalization essay ("suggestion, not enforcement"). | System proposes, human can override; overrides are captured as high-weight feedback signals. No silent, irreversible adaptation. |
| 4 | **Binary A/B testing is insufficient for multi-metric commerce decisions.** Marginal/conflicting results force premature ship/kill. | Wasilewski & Sobecki 3WD paper (pilot-validated); anchor paper's sequential micro-change testing; synthesis consensus #1. | Experiment adjudication must support Accept / Reject / **Delay** with MDE thresholds and an indifference margin ("dead zone"). |
| 5 | **Split heavy offline computation from light online serving.** Real deployments pre-compute segments/variants and serve cached results. | Anchor paper architecture; synthesis §"Offline Computation vs. Online Inference Split" and deployment notes (edge-cached variants). | Batch-first architecture; the online API reads precomputed decisions/features; no real-time training in MVP. |
| 6 | **Short-term engagement metrics are adversarial.** Optimizing clicks invites reward hacking, adaptation fatigue, and LTV destruction. | Synthesis consensus #3 and risk register; Kristiana et al. reward-function caveats; Aydin churn mechanism. | Reward/utility functions must include margin, incentive cost, and fatigue/trust penalties; report longitudinal proxies, not just CR. |
| 7 | **Explanation is a trust-load-bearing feature, not documentation.** Perceived relevance builds trust; perceived surveillance (specificity without transparency) destroys it. | Aydin (privacy paradox, brand-trust moderation); Beyari (AI ↔ loyalty); synthesis Category 1 #3 (XAI mandatory core). | Every decision ships with human-readable reasoning; explanations maximize relevance framing and avoid creepy specificity; user/manager-facing data controls. |
| 8 | **Hybridize: representation learning for slow preferences, bandits for fast context, rules for guardrails.** No single method covers the timescales. | Kristiana et al. (TWN for long-term profile → MAB for real-time nudge); synthesis "Hybridization over Purity". | Layered policy: batch models produce priors; a bandit (stretch) adapts within-session/period; deterministic rules always constrain both. |
| 9 | **Micro-conversions (PCR) are the early-warning channel.** Macro metrics (CR/AOV) are lagging and noisy per segment. | Anchor paper introduces Partial Conversion Rate; 3WD paper evaluates micro + macro jointly. | Instrument scroll/filter/dwell-style micro-events in the simulator; use empirically derived (not expert-guessed) micro-conversion weights — a flagged research gap. |
| 10 | **Cold start needs an explicit, boring answer.** New/anonymous users break clustering and bandits alike. | Synthesis Group 2 future work; TWN limitations. | Deterministic fallback: route unknowns to the best generalized variant, labeled as cold-start in the reasoning. |
| 11 | **Generative content requires a validation firewall.** Hallucinated product claims are legal liability. | Wasilewski, Chawla & Pralat; GenUI transcript; synthesis Group 4. | GenUI only as an optional plugin: pre-generated offline, validated against catalog ground truth, served statically. Never in the core decision path. |
| 12 | **Evaluate on three axes or not at all:** prediction quality, decision quality (uplift/regret/constrained profit), and system quality (latency, reproducibility, explainability). | Synthesis metrics taxonomy (business / ML / recommendation / ranking / decision-quality metric families). | The evaluation report is a first-class artifact with all three sections; a single-metric claim is an anti-pattern (see QUALITY_BAR.md). |

---

## 2. Consensus Findings

Independent research strands (e-commerce UI, digital banking, psychology, systems engineering) converge on:

1. **The binary A/B failure mode.** Bundled changes obscure causality; marginal results force premature decisions; multi-metric conflicts (CR ↑ / AOV ↓) are common. The corpus proposes formal Delay states and indifference margins. *(Anchor paper, 3WD paper, synthesis consensus #1.)*
2. **The black-box trust deficit.** Fully autonomous adaptation is empirically rejected by users across TAM studies, well-being studies, and MSME reviews. Transparency + override controls are convergent requirements, and they double as clean feedback data. *(Alotaibi; Aydin; Solehatin; O'Sullivan.)*
3. **Short-term metric misalignment.** Click-maximizing systems reward-hack; longitudinal tracking (retention, LTV, fatigue) is the repeatedly demanded fix. *(Kristiana; Aydin; synthesis consensus #3.)*
4. **Layered hybrid architectures win.** Batch representation/segmentation + online lightweight adaptation + rule guardrails appears in every applied system in the corpus. *(Anchor paper; Kristiana; Hasan.)*
5. **Personalization value is real and large when segment-conditioned.** The anchor paper's field results (+27.6% CR, +68.1% AOV in specific clusters) establish the ceiling; the same paper shows effects are heterogeneous across clusters — which is itself an argument for decision-level (not global) optimization.

---

## 3. Contradictions and Trade-offs

### T1 — Adaptive vs. adaptable interface control
- **Option A (fully adaptive):** ML controls everything. + Lowest user effort, largest cognitive-load reduction (task-time gains up to ~35% cited). − Disorientation, trust violation, empirically rejected.
- **Option B (fully adaptable):** user configures everything. + Autonomy, trust. − Paradox of the active user: nobody configures.
- **Resolution `[Decision]`:** semi-adaptive. System proposes; user/manager overrides; overrides feed back as labeled signals. This is the corpus's own resolution and Alotaibi's empirical winner.

### T2 — Single-metric vs. multi-criteria model selection
- **A (single metric):** cheap, standard, automatable. − Blind to viability and cost.
- **B (MCDA):** business-aware, ROI-guaranteeing. − Requires subjective weights (human bias enters through the criteria matrix).
- **Resolution `[Decision]`:** MCDA for offline macro-decisions (segmentation, algorithm selection) with weights exposed in config and sensitivity-checked; plain metrics acceptable for lightweight micro-optimizations. The weight-subjectivity risk is mitigated by documenting weights as ADR-tracked config, not code.

### T3 — Binary A/B vs. three-way decision
- **A (binary):** universally understood, simple. − Premature decisions, metric conflicts.
- **B (3WD):** protects revenue, formalizes "wait." − Can stall in Delay loops; needs threshold tuning; requires traffic volume.
- **Resolution `[Decision]`:** 3WD as the default gateway for policy/variant changes, with (a) a static indifference margin (±2% class) to prevent noise-chasing, and (b) a maximum-delay budget that escalates to human review — directly addressing the corpus's stall failure mode.

### T4 — Prediction-first vs. decision-first optimization
- **A:** optimize model accuracy, act on scores. − The "so what?" gap; accurate models of organic behavior create zero uplift.
- **B:** optimize expected constrained profit of actions. − Harder to evaluate; needs counterfactual reasoning (uplift/off-policy methods) that is statistically delicate.
- **Resolution `[Decision]`:** decision-first as the product contract; prediction metrics retained as internal diagnostics. Uplift estimation enters as a stretch precisely because the corpus warns against fake counterfactual certainty.

### T5 — Real-time vs. batch personalization
- **A (real-time):** responsive to intra-session intent; required for bandit nudging. − Stateful low-latency infra; exploration degrades UX; single-developer feasibility low.
- **B (batch):** matches offline-heavy consensus; reproducible; cheap. − Misses in-session shifts.
- **Resolution `[Decision]`:** batch/near-line decisions in MVP; real-time adaptation only inside the simulator (bandit stretch goal), where its dynamics can be studied honestly without infra theater.

### T6 — Bandit exploration vs. experience protection
- Unresolved in the literature: exploration is necessary for learning and inherently serves suboptimal experiences; reward hacking is the documented catastrophic mode.
- **Resolution `[Decision]`:** guardrailed exploration — rules bound the action set the bandit may explore (never explore into constraint-violating actions); reward includes fatigue/margin penalties; regret and reward reported with smoothing. Flagged as an explicit demonstration of engineering maturity.

### T7 — GenUI ambition vs. hallucination liability
- **Resolution `[Decision]`:** excluded from core; optional plugin restricted to the corpus's own "possible simplification": offline pre-generation + deterministic catalog validation + static serving.

---

## 4. Research Gaps Worth Exploiting

Ranked by (frequency in corpus × single-developer feasibility × portfolio value):

1. **An open, automated experimentation gateway with 3WD routing and indifference margins.** Named a "massive gap in the current MLOps ecosystem" in the synthesis; primarily statistical routing logic — high feasibility. *This is the project's flagship differentiator.*
2. **Business-constrained evaluation wrappers for standard algorithms** (scikit-learn-style API that ranks clustering/model candidates by MCDA including viability and cost criteria). Explicitly called out as enterprise-differentiating and feasible.
3. **Data-driven micro-conversion weights.** The corpus admits PCR weights are currently expert-guessed; deriving them empirically (probability that a micro-action leads to macro-conversion) is novel, small, and demonstrable in simulation.
4. **Decision-level explanation composition** (constraints fired + model attribution + counterfactual "why not the runner-up action") — the corpus demands XAI but offers no decision-grade (as opposed to prediction-grade) pattern.
5. **Restraint as a first-class action.** No system in the corpus models *do nothing / wait / suppress discount* explicitly; the economics literature in the synthesis implies it everywhere. Cheap to build, memorable to demo.
6. **Longitudinal fatigue/LTV proxies in simulation.** The corpus laments that validation is short-term and lab-bound; a simulator can honestly explore multi-month dynamics no 30-day field study can — provided simulator assumptions are documented (see QUALITY_BAR.md, anti-fake-metrics rule).

Gaps deliberately *not* pursued (documented so reviewers see the judgment): federated learning (infeasible solo), autonomous UI-generating RL (corpus rates feasibility low), preference-trajectory modeling (novel but orthogonal to the decision thesis).
