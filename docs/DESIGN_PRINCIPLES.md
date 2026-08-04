# DESIGN_PRINCIPLES.md

Each principle: meaning → why it matters here → implementation consequence.

---

## 1. Opinionated Over Generic

- **Meaning:** NextMove solves e-commerce behavioral decisioning. It is not a framework for "any ML decision problem."
- **Why:** the synthesis is blunt — generic frameworks read as "Okay…" to reviewers and take platform-years to matter; Stripe/dbt/Airflow won by owning one domain. Specificity is also what makes constraints, actions, and explanations meaningful.
- **Consequence:** the action catalog, utility function, and constraint vocabulary are e-commerce-native (discount, bundle, timing, channel, inventory, margin). Extensibility exists, but the defaults are the product. Feature requests that generalize the domain are rejected by policy.

## 2. Headless Architecture

- **Meaning:** the intelligence layer (decisions, explanations, experiments) is fully separated from any presentation; the contract is the typed API/JSON.
- **Why:** every company has a different stack; the corpus's extensibility guidance (agnostic JSON payloads bindable to any frontend) matches how such systems are actually adopted.
- **Consequence:** the dashboard is a disposable demo client with zero privileged access; anything the dashboard shows must be obtainable from the public API; adapters (in/out) are the growth path.

## 3. Event-Driven

- **Meaning:** the system's memory is an append-only event log; state (features, segments, decisions, outcomes) is derived, and delivered actions/overrides are themselves events.
- **Why:** it makes the closed loop honest (decisions become observable causes of later events), enables replay/backtesting, and mirrors the telemetry-first designs across the corpus — without requiring streaming infrastructure.
- **Consequence:** no component mutates history; "what did the system know at time t" is always answerable; the simulator and real adapters produce the identical event shape. Events improve the system specifically at: feedback capture, experiment attribution, and reproducible replay. Where events do *not* help (synchronous single-decision requests), we don't force them.

## 4. Explainable By Default

- **Meaning:** every important output — decision, segment, experiment verdict — ships with reasoning; explanation is produced by the same pipeline, not written after the fact.
- **Why:** the corpus's strongest consensus: opacity destroys trust (privacy paradox, black-box rejection), and explanation is the mediating buffer. It is also the portfolio's seniority signal.
- **Consequence:** the `Decision` schema makes `reasoning` and `reasoning_trace` required fields; models without usable attributions are inadmissible in the decision path; an explanation style guide enforces relevance-framing over surveillance-framing; explanation quality has its own review rubric.

## 5. Human-In-The-Loop

- **Meaning:** the system proposes; humans can approve, override, and bound it. Semi-adaptive, never autonomous.
- **Why:** fully autonomous adaptation is empirically rejected (Alotaibi; corpus Category 3); overrides are also the highest-quality feedback signal available.
- **Consequence:** override endpoint + `needs_human_review` queue in MVP; 3WD Delay escalates to humans after its budget; constraint config is the human steering wheel; overrides are logged as high-weight labeled events and reported in evaluation.

## 6. Offline-First Experimentation

- **Meaning:** every policy, model, and variant is evaluated in reproducible offline simulation/replay before any (simulated) rollout; local development runs the entire world on a laptop.
- **Why:** the corpus's offline-heavy consensus; single-developer feasibility; and scientific honesty — the simulator provides counterfactual ground truth that live traffic never can.
- **Consequence:** the simulator is a first-class, tested component; `make reproduce` is the primary developer loop; nothing requires cloud resources; online-style evaluation (3WD gating) runs *inside* the simulation clock.

## 7. Reproducibility

- **Meaning:** deterministic pipelines, versioned artifacts, documented experiments; identical inputs ⇒ identical outputs.
- **Why:** it is the difference between an experiment and an anecdote — and the most frequently violated norm in ML portfolios.
- **Consequence:** seeds everywhere (including exploration); content-hashed lineage on derived tables; MLflow run IDs cited in reports; golden-file tests on decision objects; CI runs a miniature end-to-end reproduction.

## 8. Production Realism

- **Meaning:** the system resembles something a mid-market company could actually operate: one container, boring storage, declarative config, tests, runbooks — and honest omissions.
- **Why:** the hiring-manager question ("could they join our team Monday?") is answered by operational judgment, not by Kubernetes cosplay. The corpus's deployment notes (pre-compute + cache, fail-safes, dead zones) define what realism means at this scale.
- **Consequence:** no distributed systems without a load-bearing reason (see anti-pattern: architecture astronautics); every shortcut is documented as debt (QUALITY_BAR.md); failure modes from the corpus (delay loops, reward hacking, segment collapse) have explicit fail-safes and tests.
