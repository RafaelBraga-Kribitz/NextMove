# Model card: response model `logistic`

> **Simulated data only.** Every number in this file comes from the seeded NextMove simulator (ADR-004); none describes real customers, revenue or production use.

- **Run:** `demo-f8fb25c032` · **model version:** `logistic-490a615c10dd` · **config hash:** `7c4d3f8e1510`
- **Decision-path status:** challenger, comparison study only

## Intended use

Predict the probability that a customer buys at their next visit given one action from the catalog (or none), so the decision engine can rank actions by expected incremental profit (uplift = P(buy | action) − P(buy | none), ADR-006). Not intended for any use outside the simulated NextMove world.

## Data

Randomized A/B/n experiment log (ADR-012): each eligible simulated customer received a uniformly random action among those allowed by the hard constraints. Temporal splits only: train days [14, 367], validation [367, 411], test [411, 548].

## Model

Logistic regression on standardized context features, action indicators and action × feature interactions; bootstrap ensemble of 8 members resampled by customer; Platt calibration on the validation window. Seeded and single-threaded.

Features: `has_ordered`, `rfm_recency_days`, `rfm_frequency_count`, `rfm_monetary_cents`, `session_visits_count`, `session_depth_mean_views`, `price_sensitivity_proxy`, `message_fatigue_count`, `cart_state_units`, `abandonment_history_count`, `dwell_long_count`, `dwell_medium_count`, `scroll_count`, `filter_apply_count`, `primary_affinity_share`, `contacts_7d`, `contacts_total`, `tenure_days`, `month_sin`, `month_cos`, `low_stock`, `primary_is_fashion_apparel`, `primary_is_home_basics`. Customers who never ordered get `has_ordered = 0` and a capped recency (explicit, not silent imputation).

## Metrics (prediction axis)

| Split | Rows | Purchase rate | Mean predicted | Brier | Brier skill | ROC AUC | ECE |
|---|---:|---:|---:|---:|---:|---:|---:|
| train | 241,287 | 0.0428 | 0.0332 | 0.04102 | -0.0011 | 0.566 | 0.0102 |
| validation | 61,092 | 0.0347 | 0.0347 | 0.03351 | +0.0002 | 0.499 | 0.0049 |
| test | 236,552 | 0.0361 | 0.0326 | 0.03482 | +0.0003 | 0.513 | 0.0055 |

**Calibration gate (AC-5):** test-window ECE must be ≤ 0.01; the train stage fails otherwise. This model passed.

## Uplift approximation error (ADR-006)

On 20,990 out-of-time experiment rows with an active action: mean true uplift -2.44 pp, mean predicted -0.75 pp, MAE 1.72 pp, rank correlation 0.74, sign agreement 88%.

## Attributions

Per-decision attributions explain the uplift logit for the chosen (or best alternative) action: exact coefficient contributions. Global view, mean |attribution| for `recommend` over 300 test rows:

| Feature | Mean abs. attribution (logit) |
|---|---:|
| `action:recommend` | 0.4468 |
| `contacts_total` | 0.3656 |
| `tenure_days` | 0.3278 |
| `low_stock` | 0.2872 |
| `session_visits_count` | 0.1202 |
| `month_cos` | 0.1133 |
| `contacts_7d` | 0.1085 |
| `has_ordered` | 0.1079 |

## Limitations

- Trained and evaluated on simulated data only; the simulator's documented response function is the ground truth (`docs/SIMULATOR_ASSUMPTIONS.md`).
- Observable features carry little signal about the latent traits that drive purchases (low AUC); the model is useful mainly for the *direction* of action effects.
- Uplift is a difference of two predictions, not a dedicated uplift learner (DEBT-001).
- Calibration is checked on aggregate and per action; it can still drift outside the evaluated season.
