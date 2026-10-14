# Demo script (UC1, about 5 minutes)

Audience: a CRM / marketing manager. Everything shown is simulated (ADR-004) — say so first.

1. **Start** — `just reproduce` (once, ~20 min) then `just serve`; open
   `http://127.0.0.1:8000/demo`.
2. **Context (30 s)** — "This is a simulated fashion retailer that already sends about two
   campaign messages a week. The engine answers one question per customer per week: what
   should we do next, including nothing?" Point at the policy chart on the start page:
   always-discount and the rules playbook lose money versus doing nothing; the engine stays
   at the hindsight ceiling.
3. **Inspect a customer (1 min)** — click a customer card. Read the recommendation and the
   one-paragraph reason. Show the KPIs: expected change in purchase chance, expected profit,
   confidence, segment, messages this week.
4. **Constraints (1 min)** — scroll to *Options the engine considered*: which options the
   rules removed and why (weekly contact cap, low stock, discount ceiling, margin floor).
   "The model can only choose among what the rules allow."
5. **Override (1 min)** — pick an allowed action, give a reason, *Log override*. Try a blocked
   option via the API to show the 422 ("overrides may overrule the model, not the rules").
6. **Override visible in evaluation (1 min)** — the evaluation page lists the override with
   the engine's expected profit, the override's, and the difference, next to the policy
   comparison.
7. **Close (30 s)** — Power BI: same numbers from the SQL mart (`reporting/powerbi/`). API
   docs at `/docs`.

Screenshots of steps 2, 3 and 6: `docs/assets/demo_home.png`, `docs/assets/demo_customer.png`,
`docs/assets/demo_evaluation.png`.
