# Simulator Assumptions

Every result derived from this simulator is labeled **"in simulation"** wherever it is
reported, per SIM-03 and `TECHNICAL_DIRECTION.md` section 2's simulator honesty rules. This
document is the assumption log those rules require: every generative assumption below states,
in one place, the assumption in plain prose, the exact parameter values as shipped, the
`config/simulator.yaml` key the value is read from, and why the assumption was made — or,
where no external validation exists, that it is a design choice made by the planner rather than
a value drawn from a study.

No public dataset contains action-response counterfactuals with business context, so decision
evaluation is impossible without a generative world that responds to actions. That is why the
simulator is the project's primary data source and, at the same time, its primary credibility
risk: readers who cannot audit the assumptions below have no way to tell a genuine signal from
an artifact of how the world was built.

## World Structure

The simulated world is fashion-core plus exactly one low-seasonality contrast category
(`config/simulator.yaml`'s `categories` list): `fashion_apparel` (1,200 SKUs, price band
1,500–24,000 cents, 45% margin, `seasonality_class: high`) and `home_basics` (400 SKUs, price
band 800–9,000 cents, 35% margin, `seasonality_class: low`). The contrast category exists so
every seasonality-dependent mechanism in this document — the monthly multiplier curve, the
low-class amplitude damping, the discount-effectiveness scarcity interaction — has a control
population that experiences a flatter demand curve, rather than every simulated customer living
inside the single high-amplitude retail calendar `fashion_apparel` represents. Without it, a
"does seasonality matter" comparison would have nothing to compare against inside the same run.

The population size (`simulator.n_customers`, 50,000 at the shipped `default` scale) and the
horizon (`simulator.horizon_days`, 548 days — eighteen months, chosen to place two winter
demand peaks inside one simulated history so a seasonal effect is observable twice, not once)
are both planner choices sized for ENG-08's laptop budget, not values drawn from a real
retailer's scale. `simulator.start_date` (`2024-01-01`) anchors the calendar so month-of-year
seasonality resolves to concrete dates; it carries no significance beyond that anchor.

## Latent Traits

Every simulated customer carries four latent traits, sampled once at world-build time
(`nextmove.simulator.traits.sample_latent_traits`), each read from `simulator.latent_traits`:

- **price_sensitivity** — `beta(alpha=2.0, beta=5.0)`, natural support `[0, 1]`. A high value
  means a larger conversion-probability response to a discount and a smaller response to a
  non-price nudge.
- **loyalty** — `beta(alpha=2.5, beta=4.0)`, natural support `[0, 1]`. A high value means a
  smaller marginal response to an acquisition-style incentive and a larger response to
  retention-style actions (`recommend`, `bundle`).
- **fatigue** (stored as `fatigue_propensity`) — `lognormal(mu=-1.2, sigma=0.6)`, mathematical
  support `(0, inf)`. A high value means repeated contact suppresses this customer's response
  probability faster, subject to the loophole documented below.
- **category_affinity** — one raw value per configured category, drawn `normal(mu=0.0,
  sigma=1.0)` (mathematical support `(-inf, inf)`), then transformed (see below). A high value
  for a category means a larger baseline conversion probability and a larger response to
  actions targeting that category.

**Bounding unbounded families.** `beta`'s support is genuinely `[0, 1]` for any valid
`alpha, beta > 0` — no truncation needed. `normal` and `lognormal` are mathematically
unbounded, which conflicts with "a value outside the configured support is impossible by
construction." This is resolved by truncating every `normal`/`lognormal` draw to a symmetric
6-sigma window (`P(|Z| > 6) ≈ 2e-9` for a standard normal, so truncation almost never actually
clips a real draw) via `numpy.clip` after sampling. This truncation width is a planner choice,
not a value from any study — chosen only to make "impossible outside the support" a provably
true, testable statement for every distribution family, including the unbounded ones.

**Category affinity transform.** The categories share one `normal(mu=0.0, sigma=1.0)`
distribution, which can and does produce negative raw values. Dividing each raw value by the
sum of all raw values is unsafe with a mean-zero distribution and as few as two categories: the
sum is negative or near-zero with non-trivial probability, which would divide by (near) zero or
flip a component's sign. A softmax is used instead: `exp(raw_i) / sum(exp(raw_j) for all j)`.
The denominator is a sum of strictly positive terms, so it is always well-defined and strictly
positive; every component is always in `(0, 1)` and the vector always sums to 1.0 (up to float
rounding), by construction, regardless of the sign or magnitude of the underlying draws. This
transform is a deliberate design choice beyond what the project's research corpus specifies —
the corpus's Assumption A3 explicitly leaves distribution family and transform choice to the
implementer. The general pattern (customers carry latent behavioral traits that modulate
response) is supported by retail-simulation literature; the exact functional forms above —
these particular distribution families, these particular parameter values, this particular
softmax transform — are not externally validated against any real dataset. They are internally
consistent and documented, not empirically calibrated.

## Seasonality

Twelve monthly multipliers (`simulator.seasonality.monthly_multipliers`):
`[0.85, 0.80, 0.85, 0.90, 0.95, 1.00, 0.95, 0.95, 1.05, 1.15, 1.45, 1.90]`, indexed
January–December, with `peak_month: 12` — a December winter peak nearly 2.24x the January
trough, chosen to give the `default` profile's 548-day horizon two distinguishable peaks.

`high`-seasonality-class categories (`fashion_apparel`) read this curve directly
(`World.seasonal_multiplier_for_class`). `low`-seasonality-class categories (`home_basics`)
read a damped version, pulled toward 1.0 by `simulator.seasonality.low_class_amplitude_factor`
(shipped at `0.15`): `damped = 1.0 + (raw - 1.0) * 0.15`. This is what makes the contrast
category genuinely flatter — a smaller peak-to-trough ratio — rather than merely relabeled with
the same curve under a different name.

## Inventory

Every SKU starts at `simulator.inventory.initial_stock_per_sku` (250 units) and is flagged
low-stock at or below `simulator.inventory.low_stock_threshold` (20 units). Restocking is a
per-SKU-per-day Bernoulli trial at `simulator.inventory.restock_probability_per_day` (0.01),
replenishing a small batch — `1%` of `initial_stock_per_sku`, at least 1 unit — rather than
topping a SKU back up to full stock on every trigger.

Both the restock probability and the restock batch size are Rule 1 calibration fixes made
during execution (plan 01-08 Task 3), not values from any external source: the originally
planned `0.08` probability combined with a full-stock-topup restock made D-05's UC1 scarcity
scenario ("winter-jacket cart abandoner with low stock") structurally unreachable regardless of
demand concentration, proven empirically against a real `demo`-profile run where a SKU
receiving 40%+ of its category's order volume still never dropped below roughly 100 of its 250
initial units. A single high-probability, full-topup restock erases days of accumulated organic
demand in one step; a small, low-probability batch lets sustained demand outpace replenishment,
which is what real restock cadences do. This is a deliberate calibration choice made to make a
required scenario reachable, documented here rather than left as an unexplained tuning.

SKU-level demand within a category is not uniform. `nextmove.simulator.tick._zipf_weights`
biases browse/cart/order selection toward a small number of "popular" SKUs per category using a
`1/(rank+1)^3.0` power-law weighting (`_POPULARITY_EXPONENT = 3.0`, a module constant, not a
config key). This is also a Rule 1 calibration fix: uniform SKU selection spread demand across
hundreds of SKUs so evenly that no SKU's stock ever approached the low-stock threshold at any
tested scale. The exponent `3.0` is steep — steeper than the classic Zipf exponent of `1.0` —
because the catalog's per-category SKU counts (hundreds) are large relative to total order
volume; a gentler exponent left the top-ranked SKU well above `low_stock_threshold` even
combined with the restock changes above. Real retail demand curves this skewed are not
unrealistic, and D-05 requires that scarcity genuinely *occurs*, not that its curve is gentle.

## Campaigns

One campaign per (category, channel) pair is generated at world-build time
(`simulator.campaigns.channels`: `[email, push]`), each active for the full horizon
(`start_tick=0`, `end_tick=horizon_days`) with a per-campaign discount drawn uniformly between
`simulator.campaigns.discount_bps_min` (500) and `discount_bps_max` (3000) basis points. Whether
an individual customer is actually exposed on a given eligible day is a separate organic-
behavior decision: a Bernoulli trial at `simulator.campaigns.send_probability_per_eligible_day`
(0.15) per (customer, campaign, day), gated by `simulator.campaigns.frequency_cap_per_week` (3)
— a rolling 7-day exposure count per (customer, campaign) pair, trimmed on every read. Audience
selection is category-matched: a customer is only eligible for a campaign whose category equals
that customer's single highest-affinity category (see Organic Behaviour below).

## Organic Behaviour

Every active customer (signed up at or before the current tick, `signup_tick` drawn uniformly
over `[0, horizon_days)`) is evaluated once per simulated day for session occurrence. Session
probability is `simulator.engagement.base_session_probability` (0.12) scaled by that day's
seasonal multiplier and, if the customer received a delivered action that same tick, by that
action's `response_multiplier` (see Action Response below) — a same-day effect (D-08), not a
next-day one, because the delivery's boost is computed before organic generation runs within
the same tick.

A session that occurs draws between `simulator.engagement.min_views_per_session` (1) and
`max_views_per_session` (6) product views, each view drawn from the customer's single
highest-affinity category via the popularity-weighted SKU selection described under Inventory.
Category selection uses that customer's single highest-affinity category, tie-broken
alphabetically (`_primary_category`) — Phase 1 does not model within-session category
switching. Each viewed SKU may add to cart at
`simulator.engagement.add_to_cart_given_view_rate` (0.33, also a Rule 1 calibration fix for the
same UC1-scarcity reason as the inventory parameters above — the originally planned 0.18
combined with uniform SKU selection left demand too dilute for scarcity to ever occur). A
non-empty cart converts to an order at `base_conversion_probability` (see Action Response), or
abandons otherwise; a failed inventory reservation on an intended purchase is recorded as an
abandonment rather than an order, regardless of whether the customer's own conversion roll
would have succeeded.

## Micro-Conversion Events

Alongside every product view, two independent micro-events may fire
(`simulator.micro_events`): a scroll event at `scroll_rate` (0.55) carrying a random scroll
depth percentage, and a filter-apply event at `filter_rate` (0.22) carrying a cosmetic
facet/value pair that carries no weight or score. A dwell event is emitted unconditionally
(not gated by a rate) for every product view, classified into one of three dwell classes by a
drawn dwell duration compared against `dwell_short_seconds_max` (8.0 seconds) and
`dwell_medium_seconds_max` (45.0 seconds): `short` at or below the first boundary, `medium`
strictly above the first boundary and at or below the second, `long` strictly above the second.
The two boundaries are non-overlapping by construction — each drawn duration is compared
against exactly one of the two thresholds in a fixed order, so no duration is ambiguous between
classes.

**Phase 1 emits raw micro-events only.** Scroll, filter-apply and dwell events are recorded as
observed behavior with no attached importance, score, or weight, and this simulator derives no
micro-action-to-conversion weight from them (D-06). Deriving such a weight — learning how much a
scroll or a long dwell actually predicts conversion — is Phase 4 work, not Phase 1's.

## Action Response

`nextmove.simulator.response.response_multiplier` is the documented, closed-form
action-response function every delivered action's effect flows through — never a hidden or
random effect. For `action is NONE` it returns exactly `1.0`. For every other archetype:

```
response_multiplier(traits, action, params, context, config) =
    archetype_base[action]                        (simulator.response.archetype_base_multiplier)
    * (1 + price_sensitivity_weight
           * price_sensitivity
           * discount_bps / 10000)                 [discount_low, discount_high only]
    * scarcity_factor(context)                      [discount_low, discount_high only]
    * (1 + loyalty_weight * loyalty)                [recommend, bundle only]
    * (1 + category_affinity_weight
           * category_affinity[context.category])
    * context.seasonal_multiplier
    * fatigue_penalty(traits, context.fatigue_counter, config)
```

`archetype_base` (`simulator.response.archetype_base_multiplier`) supplies one base coefficient
per non-`none` archetype — `wait: 1.02, recommend: 1.10, bundle: 1.15, discount_low: 1.20,
discount_high: 1.35, email_now: 1.08, email_delayed: 1.05` — so no business number here is a
code literal (ENG-03). The price-sensitivity term applies only to `discount_low`/
`discount_high` and scales with both the customer's `price_sensitivity` and the discount's own
magnitude (`discount_bps`), weighted by `simulator.response.price_sensitivity_weight` (0.30).
`scarcity_factor` damps that same pair to `min(1.0, inventory_units / low_stock_threshold)` once
the targeted category's minimum SKU inventory has fallen to or below
`inventory.low_stock_threshold` — the mechanism behind UC1's "low inventory suppresses the
discount" narrative. The loyalty term applies only to `recommend`/`bundle`
(`simulator.response.loyalty_weight`, 0.25). The category-affinity term
(`simulator.response.category_affinity_weight`, 0.20), the seasonal multiplier, and the fatigue
penalty apply to every non-`none` archetype.

`base_conversion_probability` is `simulator.response.base_conversion_rate` (0.035) scaled by
the customer's affinity for the targeted category (using the same `category_affinity_weight`)
and the seasonal multiplier, clamped to `[0, 1]`. `ground_truth_uplift` is
`P(convert|action) − P(convert|none)`, computed from these two functions — never simulated by
running extra ticks — which is what makes the counterfactual computable for any
`(customer, action)` pair without running the simulation (MODEL-06).

## The Fatigue Loophole

`fatigue_penalty(traits, fatigue_counter, config)` is a multiplicative penalty in `(0, 1]`,
decreasing as a customer's accumulated contact count (`fatigue_counter`, a running total since
signup — a monotonically non-decreasing counter, not a decayed rolling window) rises, scaled by
that customer's own `fatigue_propensity`:
`1.0 / (1.0 + fatigue_penalty_weight * fatigue_propensity * fatigue_counter)`, using
`simulator.response.fatigue_penalty_weight` (0.15).

This is D-04's deliberate, documented reward-hacking **loophole**: `simulator.loophole
.fatigue_penalty_enabled` (shipped `true`) can be set to `false`, in which case
`fatigue_penalty` returns exactly `1.0` regardless of contact count and the simulated world
stops penalizing repeated contact entirely. A policy that maximizes short-horizon profit with
the penalty disabled will contact fatigued customers relentlessly, with no in-simulation cost
for doing so. Phase 1 ships only the loophole, config-disableable and documented here rather
than left implicit; it does not exploit it. The mandated reward-hacking probe that exploits this
loophole arrives with the v2 contextual bandit, not in this phase.

## Determinism

Every stream of randomness in the simulator is seeded from four config values
(`simulator.seeds`: `world`, `organic`, `response`, `campaign`) rather than a single global
seed, so unrelated purposes (customer traits vs. organic behavior vs. campaign discounts) never
share entropy and reordering unrelated draws never changes another purpose's output. Seeds are
config values, not command-line flags (D-25, `nextmove.simulator.__main__` declares no seed
argument): a determinism claim must be auditable from the config hash alone, and a value a
caller could override per-invocation would not be. `nextmove.simulator.world` additionally
reserves three large tick sentinels (`_SIGNUP_TICK_SENTINEL`, `_CATALOG_PRICE_TICK_SENTINEL`,
`_CAMPAIGN_TICK_SENTINEL`, all above one billion) so purpose-scoped sub-streams for signup
timing, SKU pricing, and campaign discounts never collide with a real simulated tick or with
each other. These sentinels must never be renumbered once real data has been produced from
them: doing so would change every draw derived through them, breaking ENG-04's byte-identical-
rerun claim for any table produced before the renumbering.

## Known Limitations

The simulator does not model: within-session category switching (every session's browsing is
confined to the customer's single highest-affinity category); a decayed or rolling-window
fatigue mechanic (fatigue is a monotonically non-decreasing running count, never decaying);
cross-customer network effects (word of mouth, social proof); multi-item baskets beyond one
line item per order; or returns/refunds. None of these is modeled because no Phase 1
requirement currently needs them, not because they are technically infeasible to add later.

**Ground-truth uplift sampling cadence.** `data/ground_truth/ground_truth_uplift` is a
precomputed *convenience table*, sampled every `simulator.uplift_snapshot_every_ticks` ticks
(shipped default: `30`, roughly monthly) — not a per-tick materialization. At the shipped
`default` scale (50,000 customers, 548-day horizon, 7 non-`none` action types), a 30-tick
cadence yields roughly 18 snapshots and on the order of 7.2 million rows
(`50,000 × 7 × 18 ≈ 6.3M`, rounding up for the horizon's partial final interval). The per-tick
alternative — one snapshot every single day rather than every 30 — would yield on the order of
219 million rows at the same scale (`50,000 × 7 × 548 ≈ 191.8M`, and materially more once every
intermediate tick truly is included), which fails ENG-08's laptop-only guarantee: a table that
size would dominate both the wall-clock budget and the disk footprint of the entire pipeline.
This is a storage sizing decision, not a narrowing of what the simulator can answer: the
`ground_truth_uplift` *function* (`nextmove.simulator.response.ground_truth_uplift`) remains
callable for any `(customer, action, tick)` triple regardless of the table's sampling cadence —
computing it does not require running the simulation forward, only the customer's traits and
the response context at that tick. A reader who wants the uplift at an unsampled tick can call
the function directly; nothing about D-03's or MODEL-06's uplift definition is narrowed by the
table sampling less often than every tick. The cadence is a named config key
(`simulator.uplift_snapshot_every_ticks`) precisely so a reader can change it without a code
edit and see the row-count tradeoff for themselves.

**Distribution family and parameter choices are not externally validated.** As stated under
Latent Traits, the four trait families, their shipped parameters, and the softmax
category-affinity transform are planner choices consistent with the general pattern the
research corpus supports, not values fit to any real dataset. Every headline result this
simulator's data ever produces must therefore be reported "in simulation" — this is a synthetic
world with documented, auditable, but ultimately assumed generative rules, not a measurement of
real customer behavior.
