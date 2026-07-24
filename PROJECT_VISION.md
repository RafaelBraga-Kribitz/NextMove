# PROJECT_VISION.md

**Project:** NextMove — Behavioral Decision Engine for E-commerce Personalization
**Status:** Foundation document for GSD planning (`/gsd:new-project`)
**Evidence tags used throughout:** `[Evidence]` supported by the project corpus · `[Assumption]` reasonable, unproven · `[Decision]` deliberate project choice · `[Open]` unresolved, see OPEN_DECISIONS.md

---

## 1. Project Identity

**Name:** NextMove *(working codename — `[Decision]`, replaceable without consequence; the subtitle "Behavioral Decision Engine for E-commerce Personalization" is the durable identity)*

**Elevator pitch:**
NextMove is an opinionated, headless behavioral decision engine for e-commerce. It ingests raw customer events and business context (inventory, margin, campaigns, seasonality) and answers one question continuously: *"What should the company do next for this customer?"* — outputting a recommended action, its expected impact, its confidence, and a human-readable explanation of why this action beat the alternatives.

---

## 2. Why This Project Exists

### The real-world problem

`[Evidence]` Digital commerce platforms overwhelmingly serve static, one-size-fits-all experiences and campaign logic that ignore the heterogeneous needs, cognitive limits, and shifting intent of customers. The consequences documented across the corpus are cognitive overload, decision paralysis, and cart abandonment (research synthesis, §"The Recurring Business Problem"; Wasilewski & Ramsey 2025, IEEE Access).

`[Evidence]` Where personalization *does* exist, it is typically a narrow recommender ("people also bought…") disconnected from business reality. It optimizes prediction (will this customer click?) rather than decisions (what action maximizes value given margin, inventory, campaign calendar, and long-term trust?). The corpus repeatedly shows that mathematically "optimal" ML outputs are commercially unviable: clustering that produces segments too small to serve (Wasilewski et al., Egyptian Informatics Journal; Pawełek-Lubera et al., Applied Soft Computing), bandits that reward-hack short-term clicks while destroying lifetime value (Kristiana et al. 2025; synthesis §"Misalignment of Short-Term Metrics"), and binary A/B tests that force premature ship/kill calls on inconclusive data (Wasilewski & Sobecki 2026, three-way decision model).

`[Evidence]` A third failure mode is trust destruction. Deep, opaque personalization triggers the personalization–privacy paradox: relevance is welcomed, but perceived surveillance causes psychological reactance and churn (Aydin 2026, *Sustainability*; Alotaibi's TAM study showing semi-adaptive interfaces beat fully adaptive ones on every acceptance dimension; O'Sullivan 2025 on hyperpersonalization).

### Why current solutions are insufficient

- **Recommendation engines** answer "which item?" — never "should we discount?", "should we wait?", "should we do nothing?" The action space is wrong.
- **Marketing automation / journey builders** execute hand-written if-then rules with no learning, no uplift estimation, and no principled evaluation.
- **CDPs** unify data but delegate decisions to humans or to the two tools above.
- **Academic adaptive-UI research** (the anchor corpus) has produced strong components — MCDA-constrained segmentation, three-way decision experimentation, semi-adaptive control, TWN+bandit nudging — but no one has assembled them into a coherent, explainable *decision* system. `[Evidence]` The synthesis explicitly identifies this integration gap as the opportunity.

### Why this matters now

`[Evidence]` Two forces converged in the 2024–2026 literature: (1) the failure of pure-ML personalization is now empirically documented (privacy backlash, reward hacking, segment unviability), and (2) the required components (gradient boosting, bandits, SHAP, MCDA, sequential testing) are individually mature and cheap to operate. `[Assumption]` Mid-market e-commerce (the underserved segment identified in the MSME systematic review, Solehatin et al. 2026) cannot afford Amazon-scale infrastructure but can afford an opinionated decision layer on top of the data it already collects.

### Market, technical, and business context

- **Market:** `[Assumption]` The buyer-shaped hole is between "spreadsheet + gut feel" and "enterprise personalization suite." Mid-market retailers have event data (GA4, shop platforms) but no decision intelligence.
- **Technical:** `[Evidence]` The corpus converges on an offline-heavy / online-light split (heavy computation batch, serving from cached decisions) — which means production realism is achievable by a single engineer without distributed systems.
- **Business:** `[Evidence]` The anchor paper demonstrates the value ceiling: on a real platform (438,261 sessions for segmentation, 99,193 for testing), cluster-tailored UI changes produced +27.56% CR and +68.09% AOV in one cluster. The economic upside of behavior-conditioned decisions is real, not hypothetical.

### Why this is a Marketing Data Science problem

The system's core loop — segment customers under business constraints, predict responses, choose interventions, measure uplift, avoid over-discounting, protect LTV — is precisely the daily work of a marketing DS / decision science team. ML is one component; the product is the decision.

---

## 3. Portfolio Positioning

### What this signals to employers

The project answers the hiring manager's real question — *"Could I put this person on our personalization/CRM/growth stack next Monday?"* — by demonstrating, in one artifact:

- **Marketing Data Science:** CLV, propensity, uplift framing, discount economics, channel/timing decisions.
- **Decision Intelligence:** explicit action spaces, constraint filtering, expected-value ranking, regret, three-way (accept/reject/delay) experimentation.
- **Machine Learning:** honest baseline → GBM → (optional) neural comparison, calibration, off-policy evaluation of a bandit.
- **Data & Software Engineering:** event schemas, feature pipelines, a typed decision API, adapters, tests.
- **MLOps:** experiment tracking, versioned artifacts, reproducible runs, model cards.
- **Product thinking:** personas, explanations written for a marketing manager, human-in-the-loop overrides.

### Why it is differentiated

`[Decision]` The ML is deliberately one box in a nine-stage pipeline (see ARCHITECTURAL_DIRECTION.md), mirroring how real companies work. Most portfolios ship the model; this ships the decision system around the model. The memorable artifacts are:

1. A decision output that says **"Do NOT discount — show the premium bundle, wait 6 hours, then email"** with expected uplift, confidence, and reasoning. Restraint (recommending *no* incentive) is a signal no generic recommender produces.
2. A **three-way experimentation gateway** (Accept / Reject / Delay) instead of naive A/B — directly implementing a 2026 research result almost nobody has in a portfolio.
3. **Business-constrained segmentation** — MCDA wrappers that reject mathematically pretty but economically useless clusters.

### Why a hiring manager remembers it

Because it argues *against* the naive thing they see every week ("we built a recommender") and demonstrates the mature thing they wish they had ("we built a system that decides when a discount destroys margin"). `[Assumption]` This contrarian, decision-quality framing also extends the author's existing portfolio narrative (decision reconstruction, capital-allocation TCO) into a coherent identity: *systems that support high-quality decisions under uncertainty*.

---

## 4. Business Problem

### Stakeholders and current workflow

| Stakeholder | Current workflow | Pain |
|---|---|---|
| Marketing / CRM manager | Segments in a spreadsheet or CDP UI; blasts campaigns on calendar triggers; discounts by intuition | Over-discounting, poor timing, no per-customer reasoning, cannot defend choices to finance |
| E-commerce product manager | Ships UI/merchandising changes via binary A/B tests | Inconclusive tests forced to ship/kill decisions; metric conflicts (CR up, AOV down) unresolvable |
| Growth team | Optimizes short-term conversion | Reward-hacked metrics; churn and adaptation fatigue invisible until too late |
| Data scientist | Builds propensity models that ship as CSV scores | Models never connect to actions or constraints; "so what?" gap |
| Merchandising | Manages inventory and margin separately from marketing | Marketing promotes what merchandising can't fulfill; discounts erode margin on scarce stock |

### Pain points and economic impact

- `[Evidence]` **Over-discounting:** incentives applied to customers who would have converted anyway (uplift-blind targeting) directly transfers margin to no effect. The corpus's low-price-sensitivity / high-LTV scenario is the canonical case.
- `[Evidence]` **Premature experiment decisions:** binary A/B forces rollout or rejection of changes with marginal or conflicting effects; the 3WD literature exists precisely because this measurably destroys revenue.
- `[Evidence]` **Unviable segmentation:** context-free clustering produces micro-segments the marketing team cannot operationally serve; every unserved segment is wasted analysis cost.
- `[Evidence]` **Trust erosion:** intrusive personalization increases short-term engagement and long-term churn simultaneously (privacy-paradox literature).

### Economic frame

`[Decision]` The system's value function is **incremental profit under constraints**, not conversion: `expected_uplift × margin − incentive_cost − operational_cost`, subject to inventory, campaign, frequency-cap, and trust constraints. Every design choice in the remaining documents flows from this.

---

## 5. Non-Goals

`[Decision]` This project explicitly will **not** attempt:

1. **Amazon-scale recommendation infrastructure.** No distributed serving, no vector databases at scale, no sub-10ms SLAs. The offline-heavy/online-light split from the corpus makes this unnecessary.
2. **A production CDP replacement.** No identity resolution across devices, no consent-management platform, no connector marketplace. One canonical event schema + a small set of adapters.
3. **A generic, domain-agnostic AI/ML framework.** The synthesis is explicit: agnostic platforms take years and signal nothing. NextMove is opinionated for e-commerce behavioral decisioning (the Stripe/dbt/Airflow analogy).
4. **An autonomous marketing agent.** No action is executed without a human-approvable surface; fully adaptive "black box" control is empirically invalidated in the corpus (Category 3 exclusions) and excluded by design.
5. **Real-time in-session UI mutation at scale.** Real-time adaptation is a stretch goal simulated offline; the MVP decides at batch/near-line cadence.
6. **Live LLM-generated UI (GenUI) in the core path.** `[Evidence]` The corpus classifies GenUI as bleeding-edge with hallucination/legal risk; it is at most an optional, guarded plugin (pre-generated + validated content), never a core dependency.
7. **A front-end product.** The engine is headless; the dashboard is a thin demo client, not the deliverable.
8. **Deep-learning maximalism.** Neural models appear only where the comparison teaches something (see TECHNICAL_DIRECTION.md); no transformer worship.
9. **Real personal data.** The project runs on a synthetic-but-realistic e-commerce simulator (see Data Philosophy); no scraping, no PII, no GDPR exposure.
10. **Multi-tenant SaaS concerns.** Auth, billing, tenancy: out of scope.
