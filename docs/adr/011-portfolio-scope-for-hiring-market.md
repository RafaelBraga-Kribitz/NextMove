# ADR 011: Portfolio Scope for the Hiring Market (Thin Vertical Slice)

## Status

Accepted — 2026-10-14. Narrows the delivery scope of `docs/PRODUCT_CHARTER.md` and
`docs/QUALITY_BAR.md` for the first finished release. It does not relax any acceptance criterion
(AC-1..AC-14), anti-pattern, or locked architectural decision; it changes *which* charter items
are built now and adds an analytics/reporting layer the charter did not name.

These adjustments are derived from the author's portfolio rules and a study of Data Analyst /
Data Scientist job ads in Austria (Graz and Vienna). They are recorded as proposals ratified by
this ADR, not as instructions quoted from elsewhere.

## Context

After Phase 1 the repository had a reproducible simulated world, an ingest pipeline with data
quality gates, and point-in-time features, but eight packages (`models/`, `segmentation/`,
`rules/`, `decisions/`, `policies/`, `explain/`, `evaluate/`, `api/`) were empty stubs. The
charter describes a much larger product (UC1-UC4, bandits, dynamic 3WD thresholds, uplift
learners, public-dataset validation). Finishing all of it would take far longer than finishing a
smaller slice, and a half-finished large project is weaker evidence of skill than a finished
small one.

The target roles list SQL, Python, Power BI, ETL and data quality far more often than deep ML.
They also reward customer/CRM and e-commerce analytics (segmentation, churn, CLV, retention,
A/B testing) and honest communication of results. The original design is ML- and API-heavy and
has no SQL mart or BI surface, which hides the analytics skills reviewers look for first.

The author's self-assessment names three weak spots: tabular ML tuning, causal/experimental
practice, and honest forecasting. A portfolio project can turn these into strengths only by
measuring them openly (baselines with intervals, calibration, ground-truth error analysis,
negative results), not by avoiding them.

## Decision

1. **Finish a thin vertical slice, not the whole charter.** In scope: UC1 end to end (inspect
   customer -> decision -> explanation -> override -> override visible in evaluation), the
   policy comparison (AC-10), the static 3WD gateway on fixtures (AC-8, AC-9), the headless API,
   and a report. Moved to the "Later" section of `docs/MILESTONES.md`: dynamic 3WD thresholds,
   uplift learners (T-/X-learner), public-dataset validation (OD-4 v2 track), neural networks,
   and contextual bandits beyond one simple epsilon-greedy comparator. The three-tier autonomy
   config (ADR-009) stays; only what UC1 needs is implemented.
2. **SQL-first analytics layer.** A documented DuckDB SQL mart (star schema: `fct_decisions`,
   `fct_outcomes`, `dim_customer`, `dim_action`, `dim_date`) is built from pipeline outputs with
   CTEs, explicit joins and explicit column lists, plus SQL tests (row counts, uniqueness,
   referential integrity, non-null keys) and a data-quality report built from the existing
   ingest gates.
3. **Power BI is the reporting surface.** Because a `.pbix` cannot be generated here, the
   repository ships a Power BI build kit under `reporting/powerbi/`: mart exports, a data-model
   diagram, a DAX measures file, a theme JSON and a one-page layout spec. The `.pbix` itself is
   built by the human author.
4. **Customer-analytics angle.** Segmentation with viability constraints and an MCDA scorecard
   (AC-7), fatigue risk, a simple CLV estimate, a retention cohort view, and the "wasted
   discount" finding (share of discounts given to would-buy-anyway customers, versus the
   restraint policy) are headline results. Every such number is labelled as simulated and traces
   to a run ID.
5. **Weak spots measured openly.** Gradient boosting versus a rule/logistic baseline with
   confidence intervals; calibration gates; the uplift-approximation-error analysis against
   simulator ground truth (ADR-006) as a headline section; a failure-analysis section. Temporal
   splits and a holdout only; negative results are published.
6. **Visibility.** The repository should be private until the Definition of Done is met. This is
   a human action and is not performed by automation.

## Consequences

The finished release demonstrates SQL, Python, data quality/ETL, BI hand-off and experimentation
practice in one coherent story, at the cost of leaving several charter goals (UC2-UC4 depth,
bandits, dynamic thresholds, true uplift learners) explicitly unbuilt. Those are listed in
`docs/MILESTONES.md` under "Later" so the gap is visible rather than implied.

The decision engine still emits the full `Decision` contract, and all acceptance criteria still
apply, so narrowing scope does not lower the bar for the parts that ship. The Power BI kit adds a
human step before the BI report exists; the static HTML report generated from the mart is the
fallback surface anyone can open without Power BI.

Adding a SQL mart introduces a second representation of the decision log. To prevent drift, the
mart is built only from pipeline outputs by checked-in SQL files and is covered by SQL tests in
CI, and every figure in the report is computed from the mart or from the evaluation tables with
a run ID attached.

## Alternatives Considered

- **Finish the whole charter before publishing anything** was rejected: it delays any finished
  evidence by months and risks shipping nothing complete.
- **Drop the decision engine and ship only an analytics dashboard** was rejected: the engine,
  constraint guarantees and honest policy comparison are what make the project distinctive; the
  mart and BI kit sit on top of it rather than replacing it.
- **Use Tableau or a hosted BI tool** was rejected: the target ads name Power BI, and hosted
  tools would add a cloud dependency to a local-first project.
