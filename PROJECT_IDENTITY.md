# PROJECT_IDENTITY.md

---

## Elevator Pitch (≤3 sentences)

NextMove is an opinionated, headless behavioral decision engine for e-commerce that turns raw customer events and business context into explainable next-best-actions — including the action of doing nothing. Instead of predicting clicks, it optimizes decisions: which intervention, for whom, when, through which channel, under real constraints like inventory, margin, and message fatigue. Every decision ships with expected impact, confidence, and a reason a marketing manager can read — and every change to the system must survive a three-way (accept/reject/delay) experimentation gateway before it ships.

## One-Sentence Value Proposition

**NextMove tells an e-commerce team what to do next for each customer — and proves, before rollout, that the advice is worth taking.**

---

## Differentiation

### Why this is different from recommendation engines

Recommendation engines answer *"which item?"* over a single action type (show product), optimized for engagement, blind to margin, inventory, incentive cost, and timing, and incapable of recommending restraint. NextMove treats "recommend a product" as just one candidate in an action space that includes discounts, bundles, timing, channel choice, waiting, and doing nothing — ranked by expected *incremental constrained profit*, not click probability. A recommender can be plugged into NextMove as one `ActionProvider`; the reverse is impossible.

### Why this is different from CDPs

A Customer Data Platform unifies identities and audiences; it is a data product that ends where judgment begins — humans still decide what to do with the segments. NextMove assumes the data problem is roughly solved (canonical events in, one schema) and owns exactly the layer CDPs delegate: constrained decision-making with quantified expected outcomes and built-in experimental verification. No identity resolution, no connector marketplace, no audience UI — and no pretense of them.

### Why this is different from marketing automation

Marketing automation executes hand-written if-then journeys: static rules, no learning, no uplift estimation, and evaluation limited to open/click dashboards. NextMove inverts each property: rules are guardrails around learned policies rather than the policy itself; targeting aims at incremental effect rather than raw response; timing and channel are decision variables rather than journey constants; and every policy change is adjudicated by a statistical gateway that is allowed to say "we don't know yet." Automation tools are downstream *executors* of NextMove's decisions, not competitors to it.

### The one-line contrast

- Recommender: *"People like you bought this."*
- CDP: *"Here is everything we know about them."*
- Marketing automation: *"On day 3, send email B."*
- **NextMove:** *"Don't discount this customer — show the premium bundle in 6 hours by email; expected uplift +3.8%, confidence 82%, and here's why."*
