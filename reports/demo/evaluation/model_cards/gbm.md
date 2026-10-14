# Model card: response model `gbm`

> **Simulated data only.** Every number in this file comes from the seeded NextMove simulator (ADR-004); none describes real customers, revenue or production use.

- **Run:** `demo-f8fb25c032` · **model version:** `gbm-175a0d71539f` · **config hash:** `7c4d3f8e1510`
- **Decision-path status:** selected for the decision path (highest validation-window replay profit)

## Intended use

Predict the probability that a customer buys at their next visit given one action from the catalog (or none), so the decision engine can rank actions by expected incremental profit (uplift = P(buy | action) − P(buy | none), ADR-006). Not intended for any use outside the simulated NextMove world.

## Data

Randomized A/B/n experiment log (ADR-012): each eligible simulated customer received a uniformly random action among those allowed by the hard constraints. Temporal splits only: train days [14, 367], validation [367, 411], test [411, 548].

## Model

LightGBM gradient-boosted trees on context features, the action archetype (categorical) and discount depth; bootstrap ensemble of 8 members resampled by customer; Platt calibration on the validation window. Seeded and single-threaded.

Features: `has_ordered`, `rfm_recency_days`, `rfm_frequency_count`, `rfm_monetary_cents`, `session_visits_count`, `session_depth_mean_views`, `price_sensitivity_proxy`, `message_fatigue_count`, `cart_state_units`, `abandonment_history_count`, `dwell_long_count`, `dwell_medium_count`, `scroll_count`, `filter_apply_count`, `primary_affinity_share`, `contacts_7d`, `contacts_total`, `tenure_days`, `month_sin`, `month_cos`, `low_stock`, `primary_is_fashion_apparel`, `primary_is_home_basics`. Customers who never ordered get `has_ordered = 0` and a capped recency (explicit, not silent imputation).

## Metrics (prediction axis)

| Split | Rows | Purchase rate | Mean predicted | Brier | Brier skill | ROC AUC | ECE |
|---|---:|---:|---:|---:|---:|---:|---:|
| train | 241,287 | 0.0428 | 0.0366 | 0.04078 | +0.0047 | 0.653 | 0.0138 |
| validation | 61,092 | 0.0347 | 0.0347 | 0.03349 | +0.0008 | 0.526 | 0.0036 |
| test | 236,552 | 0.0361 | 0.0330 | 0.03481 | +0.0007 | 0.528 | 0.0046 |

**Calibration gate (AC-5):** test-window ECE must be ≤ 0.01; the train stage fails otherwise. This model passed.

## Uplift approximation error (ADR-006)

On 20,990 out-of-time experiment rows with an active action: mean true uplift -2.44 pp, mean predicted -0.85 pp, MAE 1.64 pp, rank correlation 0.65, sign agreement 96%.

## Attributions

Per-decision attributions explain the uplift logit for the chosen (or best alternative) action: exact TreeSHAP values (`pred_contrib`) differenced against `none`. Global view, mean |attribution| for `recommend` over 300 test rows:

| Feature | Mean abs. attribution (logit) |
|---|---:|
| `action:recommend` | 0.4596 |
| `contacts_total` | 0.0655 |
| `tenure_days` | 0.0553 |
| `month_sin` | 0.0426 |
| `month_cos` | 0.0230 |
| `scroll_count` | 0.0088 |
| `session_depth_mean_views` | 0.0080 |
| `primary_is_fashion_apparel` | 0.0072 |

## Limitations

- Trained and evaluated on simulated data only; the simulator's documented response function is the ground truth (`docs/SIMULATOR_ASSUMPTIONS.md`).
- Observable features carry little signal about the latent traits that drive purchases (low AUC); the model is useful mainly for the *direction* of action effects.
- Uplift is a difference of two predictions, not a dedicated uplift learner (DEBT-001).
- Calibration is checked on aggregate and per action; it can still drift outside the evaluated season.
