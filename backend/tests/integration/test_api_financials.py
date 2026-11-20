import pytest


def test_budget_variance_endpoint(client, auth_headers):
    resp = client.post(
        "/api/v1/financials/budget-variance",
        headers=auth_headers,
        json={
            "period": "2026-Q3",
            "budget": {"marketing": 10000, "payroll": 50000},
            "actual": {"marketing": 13000, "payroll": 49000},
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "marketing" in body["breaches"]
    assert body["period"] == "2026-Q3"


def test_budget_variance_requires_auth(client):
    resp = client.post(
        "/api/v1/financials/budget-variance",
        json={"period": "2026-Q3", "budget": {}, "actual": {}},
    )
    assert resp.status_code == 401


def test_ratios_endpoint(client, auth_headers):
    resp = client.post(
        "/api/v1/financials/ratios",
        headers=auth_headers,
        json={
            "balance_sheet": {
                "cash": 50000,
                "accounts_receivable": 20000,
                "inventory": 10000,
                "other_current_assets": 5000,
                "total_current_assets": 85000,
                "total_assets": 250000,
                "total_current_liabilities": 40000,
                "total_liabilities": 90000,
                "total_equity": 160000,
            },
            "income_statement": {
                "revenue": 300000,
                "cogs": 120000,
                "operating_expenses": 90000,
                "net_income": 60000,
            },
        },
    )
    assert resp.status_code == 200
    ratios = {r["name"]: r["value"] for r in resp.json()["ratios"]}
    assert ratios["current_ratio"] == pytest.approx(85000 / 40000, rel=1e-3)


def test_capital_structure_endpoint(client, auth_headers):
    resp = client.post(
        "/api/v1/financials/capital-structure",
        headers=auth_headers,
        json={
            "market_value_equity": 600000,
            "market_value_debt": 400000,
            "cost_of_equity_pct": 15.0,
            "cost_of_debt_pct": 8.0,
            "tax_rate_pct": 25.0,
        },
    )
    assert resp.status_code == 200
    assert resp.json()["wacc_pct"] == pytest.approx(11.4)


def test_capital_structure_zero_capital_returns_422(client, auth_headers):
    resp = client.post(
        "/api/v1/financials/capital-structure",
        headers=auth_headers,
        json={
            "market_value_equity": 0,
            "market_value_debt": 0,
            "cost_of_equity_pct": 10.0,
            "cost_of_debt_pct": 5.0,
            "tax_rate_pct": 25.0,
        },
    )
    assert resp.status_code == 422


def test_risk_endpoint(client, auth_headers):
    resp = client.post(
        "/api/v1/financials/risk",
        headers=auth_headers,
        json={"current_ratio": 0.5, "cash_runway_months": 0.5},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["overall_level"] in ("moderate", "high", "critical")
    assert len(body["flags"]) >= 2


def test_forecast_endpoint(client, auth_headers):
    resp = client.post(
        "/api/v1/financials/forecast",
        headers=auth_headers,
        json={"series": [100, 200, 300, 400], "periods_ahead": 2},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["forecast"][0]["value"] == pytest.approx(500, rel=1e-2)


def test_forecast_too_few_points_returns_422(client, auth_headers):
    resp = client.post(
        "/api/v1/financials/forecast",
        headers=auth_headers,
        json={"series": [100], "periods_ahead": 1},
    )
    assert resp.status_code == 422
