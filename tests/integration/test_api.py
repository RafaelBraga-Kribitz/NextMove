"""E1 / AC-1 and AC-14: the HTTP API and the demo walkthrough on the tiny pipeline."""

import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from nextmove.api.app import create_app
from nextmove.decisions.contract import Decision

OPENAPI = Path(__file__).resolve().parents[2] / "docs" / "api" / "openapi.json"


@pytest.fixture(scope="module")
def client(tiny_pipeline: Path, tmp_path_factory: pytest.TempPathFactory) -> TestClient:
    root = tmp_path_factory.mktemp("api") / "data"
    shutil.copytree(tiny_pipeline, root)
    return TestClient(create_app("tiny", root))


def _customer(client: TestClient) -> tuple[str, str]:
    svc = client.app.state.service()
    as_of = svc.default_as_of()
    return svc.sample_customers(as_of, 5)[0], as_of.isoformat()


def test_ac1_post_decision_returns_schema_valid_decision(client: TestClient) -> None:
    customer, as_of = _customer(client)
    response = client.post("/v1/decisions", json={"customer_id": customer, "as_of": as_of})
    assert response.status_code == 200
    decision = Decision.model_validate(response.json())
    assert {"none", "wait"} <= set(decision.reasoning_trace.candidates_considered)
    assert decision.reasoning


def test_every_eligible_customer_gets_a_valid_decision(client: TestClient) -> None:
    svc = client.app.state.service()
    as_of = svc.default_as_of()
    for customer in svc.sample_customers(as_of, 1000):
        response = client.post("/v1/decisions", json={"customer_id": customer})
        assert response.status_code == 200
        Decision.model_validate(response.json())


def test_unknown_customer_is_404(client: TestClient) -> None:
    response = client.post("/v1/decisions", json={"customer_id": "no-such-customer"})
    assert response.status_code == 404


def test_customer_view(client: TestClient) -> None:
    customer, as_of = _customer(client)
    body = client.get(f"/v1/customers/{customer}", params={"as_of": as_of}).json()
    assert body["customer_id"] == customer
    assert body["decision"]["customer_id"] == customer
    assert any(f["name"] == "contacts_total" for f in body["features"])


def test_override_rules_and_loop(client: TestClient) -> None:
    customer, as_of = _customer(client)
    decision = client.post("/v1/decisions", json={"customer_id": customer, "as_of": as_of}).json()
    options = client.get(f"/v1/customers/{customer}/options", params={"as_of": as_of}).json()
    blocked = [o for o in options if not o["allowed"]]
    allowed = [
        o
        for o in options
        if o["allowed"] and o["candidate_id"] != decision["action"]["candidate_id"]
    ]
    base = {
        "decision_id": decision["decision_id"],
        "customer_id": customer,
        "as_of": as_of,
        "reason": "test override",
        "operator": "tester",
    }
    if blocked:
        rejected = client.post(
            "/v1/overrides", json={**base, "override_candidate": blocked[0]["candidate_id"]}
        )
        assert rejected.status_code == 422
        assert blocked[0]["rule"] in rejected.json()["detail"]
    stale = client.post(
        "/v1/overrides",
        json={**base, "decision_id": "stale", "override_candidate": allowed[0]["candidate_id"]},
    )
    assert stale.status_code == 422
    created = client.post(
        "/v1/overrides", json={**base, "override_candidate": allowed[0]["candidate_id"]}
    )
    assert created.status_code == 201
    evaluation = client.get("/v1/evaluation/overrides").json()
    assert evaluation["count"] >= 1
    assert created.json()["override_id"] in {o["override_id"] for o in evaluation["overrides"]}


def test_ac14_demo_walkthrough(client: TestClient) -> None:
    customer, as_of = _customer(client)
    home = client.get("/demo")
    assert home.status_code == 200 and "Simulated retailer" in home.text
    page = client.get(f"/demo/customers/{customer}", params={"as_of": as_of})
    assert page.status_code == 200 and "Recommendation" in page.text
    decision = client.post("/v1/decisions", json={"customer_id": customer, "as_of": as_of}).json()
    options = client.get(f"/v1/customers/{customer}/options", params={"as_of": as_of}).json()
    target = next(
        o["candidate_id"]
        for o in options
        if o["allowed"] and o["candidate_id"] != decision["action"]["candidate_id"]
    )
    posted = client.post(
        f"/demo/customers/{customer}/override",
        data={
            "as_of": as_of,
            "decision_id": decision["decision_id"],
            "override_candidate": target,
            "reason": "walkthrough",
            "operator": "Claudia",
        },
        follow_redirects=True,
    )
    assert posted.status_code == 200
    assert "walkthrough" in posted.text and "Operator overrides" in posted.text


def test_openapi_export_is_current(client: TestClient) -> None:
    """Regenerate with `just openapi`."""
    schema = json.dumps(client.app.openapi(), indent=2, sort_keys=True) + "\n"
    assert OPENAPI.read_text(encoding="utf-8") == schema
    paths = json.loads(schema)["paths"]
    assert {"/v1/decisions", "/v1/customers/{customer_id}", "/v1/overrides"} <= set(paths)
