# OPEN_DECISIONS.md

Decisions that must be ratified (as ADRs) before `/gsd:plan-phase`. Each: why it matters → options → trade-offs → recommendation. Recommendations are defaults; contrary evidence during planning may overturn them, with an ADR either way.

---

## Architecture Decisions

### OD-1 — Modular monolith or services?
- **Why it matters:** determines repo layout, testing strategy, and how much time goes to plumbing vs. product.
- **Options:** (A) modular monolith, one container; (B) 2–3 services (decision API, pipeline worker, dashboard); (C) full microservices.
- **Trade-offs:** A: fastest, honest at this scale, single failure domain; risks blurred boundaries without discipline. B: demonstrates service thinking; doubles ops surface. C: pure cost; violates production-realism principle.
- **Recommendation:** **A**, with registry interfaces designed service-ready. Boundary discipline enforced by import-linting between packages. Portfolio value comes from the interfaces, not the network hops.

### OD-2 — Where does intelligence live: decide-on-request or decide-in-batch?
- **Why it matters:** defines the API contract, latency budget, and feedback cadence.
- **Options:** (A) batch decisions materialized nightly, API reads them; (B) on-demand computation per request; (C) hybrid — batch for populations, on-demand for single-customer queries.
- **Trade-offs:** A matches the corpus's offline-heavy consensus and marketing cadence but makes the demo feel static. B is demo-friendly and simpler to reason about per-request, but recomputes constantly. C costs a little duplication.
- **Recommendation:** **C.** Batch is the operational truth (CRM feed export); the same engine invoked synchronously powers the interactive demo. One engine, two invocation modes.

### OD-3 — System boundary of the simulator: inside the product or a sibling package?
- **Why it matters:** contamination risk — if simulator internals are importable by models, results are fake.
- **Options:** (A) same repo, isolated package with lint-enforced import ban toward `models/`; (B) separate repository.
- **Trade-offs:** A: one-command reproducibility, easier CI; needs enforcement. B: hard isolation; painful versioning and setup for reviewers.
- **Recommendation:** **A** with an import-linter contract and a CI check; the isolation guarantee is itself a portfolio artifact.

## Technical Trade-offs

### OD-4 — Synthetic-only, or synthetic + public-dataset validation track?
- **Why it matters:** credibility. Reviewers discount purely synthetic results; but public datasets lack counterfactuals and business context.
- **Options:** (A) simulator only; (B) simulator + a public clickstream (e.g., an e-commerce events dataset) run through ingestion/features/segmentation to prove pipeline generality; (C) chase a real partner dataset.
- **Trade-offs:** A: cleanest scope, weakest credibility. B: modest extra work; segmentation/feature results on real behavior + decision results in simulation is an honest split. C: unrealistic timeline.
- **Recommendation:** **B.** Decisions evaluated in simulation (labeled as such); data engineering validated on real-shaped public data.

### OD-5 — Accuracy vs. explainability: is a non-attributable model ever admissible?
- **Options:** (A) hard rule: decision path requires attributions; (B) allow black-box if it wins by a large margin, with surrogate explanations.
- **Trade-offs:** A is principled and matches the corpus's XAI mandate; B chases marginal accuracy at the cost of the product's core promise, and surrogate explanations risk unfaithfulness.
- **Recommendation:** **A.** Black-box challengers may appear in the comparison study only; the finding "we declined X% accuracy for faithful explanations" is itself a strong result.

### OD-6 — Uplift approximation in MVP: response-model delta or ship uplift learners early?
- **Why it matters:** the whole utility function rests on `E[uplift]`.
- **Options:** (A) MVP approximates uplift as P(convert|action) − P(convert|none) from response models; quantify the approximation error against simulator ground truth; uplift learners as stretch. (B) T-/X-learners in MVP.
- **Trade-offs:** A is simpler and turns the approximation into a measured, documented finding; B is more correct but front-loads statistical delicacy and slows the loop.
- **Recommendation:** **A**, with the approximation-error analysis promoted to a headline evaluation section.

### OD-7 — Artifact versioning: DVC or content-hashed store + MLflow artifacts?
- **Trade-offs:** DVC: standard, recognizable, some workflow friction. Hash-store: lighter, custom, less legible to reviewers.
- **Recommendation:** **DVC** for data/artifacts + MLflow for runs/models — recognizability wins for a portfolio.

### OD-8 — 3WD thresholds: static MVP or dynamic from the start?
- **Trade-offs:** static (fixed MDE + ±2%-class indifference margin) is corpus-sanctioned and shippable; dynamic (traffic/seasonality-aware) is the flagged research novelty but multiplies tuning surface.
- **Recommendation:** static in MVP with the threshold interface designed for dynamism; dynamic thresholds as the first post-MVP experiment (it's the highest-novelty cheap win).

### OD-9 — Automation vs. human control: what may the system change without review?
- **Options:** spectrum from "everything auto after 3WD Accept" to "everything queued for approval."
- **Recommendation:** tiered autonomy `[Decision-ready]`: content/ranking micro-changes auto-apply on 3WD Accept; policy/model promotions and segment redefinitions always require human sign-off; anything touching price/discount ceilings is human-only. Tiers live in config.

### OD-10 — Flexibility vs. simplicity in the action space
- **Why it matters:** a huge parameterized action space makes ranking and evaluation intractable; a tiny one makes the demo trivial.
- **Recommendation:** MVP fixes ~8 action archetypes (none, wait, recommend, bundle, discount-tier×2, email-now, email-delayed) with small parameter grids; the ActionProvider registry is the escape hatch. Revisit only after policy evaluation works.

## Alternative Architectures (comparison to perform during planning)

### Architecture A — "Pipeline product" (recommended default)
Batch DAG + decision engine + thin API, per ARCHITECTURAL_DIRECTION.md.
- Complexity: low-medium · Scalability: adequate (mid-market scale by design) · Maintainability: high · Portfolio value: high (decision-science depth visible, ops honest).

### Architecture B — "Streaming decisioning"
Event bus (Kafka/Redpanda), online feature computation, real-time bandit serving.
- Complexity: high · Scalability: high (unneeded) · Maintainability: low solo · Portfolio value: superficially flashy, substantively thin — the corpus itself says heavy compute belongs offline. **Rejected unless a phase goal specifically targets streaming skills.**

### Architecture C — "Notebook + library"
Research library with notebook-driven analyses, no API.
- Complexity: minimal · Portfolio value: violates production-realism and the anti-pattern list. **Rejected.**

**Planning instruction:** ratify OD-1…OD-10 as ADR-001…ADR-010 in `/gsd:new-project`; any change later requires a superseding ADR.

---

## Pre-Planning Verification (final quality gate, self-assessed)

- Real product? Yes — buyer, users, workflow, and value function defined; scoped to mid-market e-commerce.
- Implementable by an engineer without rediscovering vision? Yes — contracts, pipeline stages, registries, and acceptance criteria are specified.
- Decisions justified? Every major choice carries evidence tags or an OD entry with trade-offs.
- Trade-offs explicit? Seven contradictions resolved in RESEARCH_SYNTHESIS §3; ten open decisions with recommendations here.
- Architecture coherent? One value function, one contract (Decision), one loop (decide → observe → adjudicate → adapt).
- Differentiated? Restraint-as-action, 3WD gateway, MCDA-constrained segmentation, decision-grade explanations — none of which appear together in existing tools or typical portfolios.
