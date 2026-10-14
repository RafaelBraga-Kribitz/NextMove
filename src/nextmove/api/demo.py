"""Manager-facing demo pages (E4, AC-14): the UC1 walkthrough in a browser, no code needed.

    /demo                       pick a customer (and see the policy comparison)
    /demo/customers/{id}        inspect -> decision -> explanation -> options -> override form
    /demo/evaluation            overrides priced in evaluation, next to the policy comparison

Plain server-rendered HTML with escaped values; the pages call the same `DecisionService` as
the JSON API, so the demo can never show a decision the API would not make.
"""

from __future__ import annotations

from datetime import date
from html import escape
from pathlib import Path
from typing import Annotated
from urllib.parse import quote

from fastapi import FastAPI, Form, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse

from nextmove.api.service import NotFound, OverrideRejected

__all__ = ["register_demo"]

_REPORTS = Path(__file__).resolve().parents[3] / "reports"

_CSS = """
:root { --surface:#fcfcfb; --panel:#ffffff; --ink:#0b0b0b; --ink2:#52514e; --line:#e4e3df;
  --accent:#2a78d6; --good:#1b7f4b; --warn:#a05a00; }
@media (prefers-color-scheme: dark) { :root { --surface:#1a1a19; --panel:#232322;
  --ink:#f0efec; --ink2:#c3c2b7; --line:#3a3a38; --accent:#3987e5; --good:#4cb27a;
  --warn:#e0a040; } }
* { box-sizing:border-box; }
body { margin:0; background:var(--surface); color:var(--ink);
  font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif; }
header { padding:14px 24px; border-bottom:1px solid var(--line); display:flex; gap:16px;
  align-items:baseline; flex-wrap:wrap; }
header b { font-size:17px; } header a { color:var(--ink2); text-decoration:none; }
main { max-width:1040px; margin:0 auto; padding:20px 16px 48px; }
.banner { background:var(--panel); border:1px solid var(--line); border-left:4px solid var(--warn);
  padding:8px 12px; margin-bottom:18px; color:var(--ink2); font-size:13px; }
.card { background:var(--panel); border:1px solid var(--line); border-radius:8px; padding:16px 18px;
  margin-bottom:16px; }
.card h2 { margin:0 0 8px; font-size:16px; }
.rec { font-size:20px; font-weight:600; margin:4px 0 10px; }
.kpis { display:flex; gap:24px; flex-wrap:wrap; margin:8px 0 12px; }
.kpi span { display:block; color:var(--ink2); font-size:12px; }
.kpi b { font-size:18px; font-variant-numeric:tabular-nums; }
table { border-collapse:collapse; width:100%; font-size:14px; }
th, td { text-align:left; padding:6px 8px; border-bottom:1px solid var(--line);
  vertical-align:top; }
th { color:var(--ink2); font-weight:500; }
td.num, th.num { text-align:right; font-variant-numeric:tabular-nums; white-space:nowrap; }
.ok { color:var(--good); } .no { color:var(--ink2); }
form.inline { display:grid; gap:8px; grid-template-columns:1fr; max-width:520px; }
select, input, button { font:inherit; padding:7px 9px; border:1px solid var(--line);
  border-radius:6px; background:var(--surface); color:var(--ink); }
button { background:var(--accent); color:#fff; border:none; cursor:pointer; }
a { color:var(--accent); }
.grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(110px,1fr)); gap:8px; }
.muted { color:var(--ink2); font-size:13px; }
img { max-width:100%; height:auto; border:1px solid var(--line); border-radius:6px; }
.error { border-left-color:#c0392b; }
"""


def _page(title: str, body: str) -> HTMLResponse:
    html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(title)}</title><style>{_CSS}</style></head><body>
<header><b>NextMove</b><a href="/demo">Customers</a><a href="/demo/evaluation">Evaluation</a>
<a href="/docs">API</a></header><main>
<div class="banner">Simulated retailer. Every customer, number and outcome on these pages comes
from the seeded NextMove simulator (ADR-004); none describes real people or revenue.</div>
{body}</main></body></html>"""
    return HTMLResponse(html)


def _eur(cents: float | None) -> str:
    if cents is None:
        return "—"
    value = round(cents / 100, 2)
    if value == 0:
        return "€0.00"
    return f"−€{abs(value):,.2f}" if value < 0 else f"+€{value:,.2f}"


def _eur_whole(value: float) -> str:
    rounded = round(value)
    if rounded == 0:
        return "€0"
    return f"−€{abs(rounded):,}" if rounded < 0 else f"€{rounded:,}"


def register_demo(app: FastAPI, service) -> None:
    @app.get("/demo", response_class=HTMLResponse, include_in_schema=False)
    def home() -> HTMLResponse:
        svc = service()
        as_of = svc.default_as_of()
        customers = svc.sample_customers(as_of, limit=40)
        links = "".join(
            f'<a class="card" href="/demo/customers/{escape(c)}?as_of={as_of.isoformat()}">'
            f"Customer {escape(c)}</a>"
            for c in customers
        )
        image = ""
        if (_REPORTS / svc.resolved.profile / "evaluation" / "policy_comparison.png").is_file():
            image = (
                '<div class="card"><h2>How the policies compare (test window)</h2>'
                '<img alt="Policy comparison chart" src="/demo/reports/policy_comparison.png">'
                "</div>"
            )
        body = (
            f"<h1>Decision cards</h1><p>Pick a customer to see what the engine recommends on "
            f"{as_of.isoformat()} (first day of the held-out test window), why, and which "
            f"options the business rules removed. You can override the decision; the override "
            f'is then priced on the <a href="/demo/evaluation">evaluation page</a>.</p>'
            f'<div class="grid">{links}</div>{image}'
        )
        return _page("NextMove demo", body)

    @app.get("/demo/reports/{name}", include_in_schema=False)
    def report_file(name: str) -> FileResponse:
        svc = service()
        base = (_REPORTS / svc.resolved.profile / "evaluation").resolve()
        path = (base / name).resolve()
        if path.parent != base or not path.is_file() or path.suffix not in {".png", ".md", ".csv"}:
            raise HTTPException(status_code=404)
        return FileResponse(path)

    @app.get("/demo/customers/{customer_id}", response_class=HTMLResponse, include_in_schema=False)
    def customer(customer_id: str, as_of: date | None = None, error: str | None = None):
        svc = service()
        as_of = as_of or svc.default_as_of()
        try:
            view = svc.customer(customer_id, as_of)
            options = svc.candidates(customer_id, as_of)
        except NotFound as exc:
            return _page("Not found", f'<div class="card error">{escape(str(exc))}</div>')
        d = view["decision"]
        outcome = d["expected_outcome"]
        estimate = outcome["estimate"]
        conf = d["confidence"]
        kpis = [
            (
                "Expected change in purchase chance",
                "—" if estimate is None else f"{estimate * 100:+.2f} pp",
            ),
            ("Expected profit vs. doing nothing", _eur(outcome.get("expected_profit_cents"))),
            ("Confidence", "—" if conf is None else f"{conf:.0%}"),
            ("Segment", view["segment"] or "—"),
            ("Messages in last 7 days", str(view["contacts_last_7_days"])),
        ]
        kpi_html = "".join(
            f'<div class="kpi"><span>{escape(k)}</span><b>{escape(v)}</b></div>' for k, v in kpis
        )
        rows = "".join(
            f"<tr><td>{escape(o['candidate_id'])}</td>"
            + (
                '<td class="ok">allowed</td><td></td>'
                if o["allowed"]
                else f'<td class="no">ruled out</td><td>{escape(o["rule"] or "")}: '
                f"{escape(o['detail'] or '')}</td>"
            )
            + "</tr>"
            for o in options
        )
        allowed = [
            o["candidate_id"]
            for o in options
            if o["allowed"] and o["candidate_id"] != d["action"]["candidate_id"]
        ]
        choices = "".join(f'<option value="{escape(c)}">{escape(c)}</option>' for c in allowed)
        features = "".join(
            f"<tr><td>{escape(f['label'])}</td><td class='num'>"
            f"{'—' if f['value'] is None else f'{f["value"]:,.2f}'}</td></tr>"
            for f in view["features"]
            if f["name"] not in ("month",)
        )
        past = "".join(
            f"<tr><td>{escape(o['original_candidate'])} → {escape(o['override_candidate'])}</td>"
            f"<td>{escape(o['reason'])}</td><td>{escape(o['operator'])}</td></tr>"
            for o in view["overrides"]
        )
        err = f'<div class="card error">{escape(error)}</div>' if error else ""
        body = f"""{err}
<h1>Customer {escape(customer_id)}</h1>
<p class="muted">As of {escape(view["as_of"])} · favourite category
{escape(view["primary_category"].replace("_", " "))} · decision id
<code>{escape(d["decision_id"])}</code></p>
<div class="card"><h2>Recommendation</h2>
<div class="rec">{escape(d["action"]["candidate_id"])}</div>
<div class="kpis">{kpi_html}</div>
<p>{escape(d["reasoning"])}</p></div>
<div class="card"><h2>Options the engine considered</h2>
<table><tr><th>Option</th><th>Status</th><th>Rule</th></tr>{rows}</table></div>
<div class="card"><h2>Override this decision</h2>
<p class="muted">You can overrule the model, not the rules: only allowed options are listed.
Overrides are logged and priced on the evaluation page.</p>
<form class="inline" method="post" action="/demo/customers/{escape(customer_id)}/override">
<input type="hidden" name="as_of" value="{as_of.isoformat()}">
<input type="hidden" name="decision_id" value="{escape(d["decision_id"])}">
<label>Action <select name="override_candidate">{choices}</select></label>
<label>Reason <input name="reason" required minlength="3" maxlength="500"
 value="Customer asked about the new collection"></label>
<label>Your name <input name="operator" required maxlength="100" value="Claudia"></label>
<button type="submit">Log override</button></form>
{
            (
                '<h2 style="margin-top:16px">Earlier overrides</h2><table><tr>'
                "<th>Change</th><th>Reason</th>"
                "<th>By</th></tr>" + past + "</table>"
            )
            if past
            else ""
        }</div>
<div class="card"><h2>What the engine knows about this customer</h2>
<table>{features}</table></div>"""
        return _page(f"Customer {customer_id}", body)

    @app.post("/demo/customers/{customer_id}/override", include_in_schema=False)
    def override(
        customer_id: str,
        as_of: Annotated[date, Form()],
        decision_id: Annotated[str, Form()],
        override_candidate: Annotated[str, Form()],
        reason: Annotated[str, Form()],
        operator: Annotated[str, Form()],
    ):
        svc = service()
        try:
            svc.record_override(
                decision_id=decision_id,
                customer_id=customer_id,
                as_of=as_of,
                override_candidate=override_candidate,
                reason=reason,
                operator=operator,
            )
        except (NotFound, OverrideRejected) as exc:
            return RedirectResponse(
                f"/demo/customers/{quote(customer_id)}?as_of={as_of.isoformat()}&error="
                + quote(str(exc)[:300]),
                status_code=303,
            )
        return RedirectResponse("/demo/evaluation", status_code=303)

    @app.get("/demo/evaluation", response_class=HTMLResponse, include_in_schema=False)
    def evaluation() -> HTMLResponse:
        svc = service()
        live = svc.override_evaluation()
        rows = "".join(
            f"<tr><td>{escape(str(o['customer_id']))}</td><td>{escape(o['original_candidate'])}"
            f" → {escape(o['override_candidate'])}</td><td>{escape(o['reason'])}</td>"
            f"<td>{escape(o['operator'])}</td>"
            f"<td class='num'>{_eur(o['expected_profit_original_cents'])}</td>"
            f"<td class='num'>{_eur(o['expected_profit_override_cents'])}</td>"
            f"<td class='num'>{_eur(o['override_effect_cents'])}</td></tr>"
            for o in live["overrides"]
        )
        overrides = (
            f"<p>{live['count']} override(s); net expected-profit effect versus the engine: "
            f"<b>{_eur(live['net_effect_eur'] * 100)}</b> (simulation).</p>"
            "<table><tr><th>Customer</th><th>Change</th><th>Reason</th><th>By</th>"
            "<th class='num'>Engine choice (exp. profit)</th>"
            "<th class='num'>Override (exp. profit)</th>"
            f"<th class='num'>Effect</th></tr>{rows}</table>"
            if live["count"]
            else "<p>No overrides logged yet. Open a customer and override a decision.</p>"
        )
        policies = svc.policy_summary()
        prow = "".join(
            f"<tr><td>{escape(p['label'])}{' (ML policy)' if p['is_ml_policy'] else ''}</td>"
            f"<td class='num'>{p['restraint_rate']:.0%}</td>"
            f"<td class='num'>{p['discount_rate']:.0%}</td>"
            f"<td class='num'>{_eur_whole(p['vs_do_nothing_eur'])} "
            f"[{_eur_whole(p['vs_do_nothing_ci_low_eur'])}, "
            f"{_eur_whole(p['vs_do_nothing_ci_high_eur'])}]</td>"
            f"<td class='num'>{p['wasted_discount_share']:.0%}</td></tr>"
            for p in policies
        )
        table = (
            "<table><tr><th>Policy</th><th class='num'>Restraint</th><th class='num'>Discount</th>"
            "<th class='num'>Expected profit vs. doing nothing [95% CI]</th>"
            f"<th class='num'>Wasted-discount share</th></tr>{prow}</table>"
            if policies
            else "<p>Run <code>just reproduce</code> to produce the policy comparison.</p>"
        )
        body = (
            "<h1>Evaluation</h1>"
            f'<div class="card"><h2>Operator overrides (UC1)</h2>{overrides}</div>'
            f'<div class="card"><h2>Policy comparison, test window</h2>{table}</div>'
        )
        return _page("NextMove evaluation", body)
