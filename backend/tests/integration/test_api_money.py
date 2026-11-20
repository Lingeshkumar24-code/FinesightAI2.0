from fastapi.testclient import TestClient


def test_money_transactions_import_budget_and_variance(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    created = client.post(
        "/api/v1/money/transactions",
        json={"date": "2026-11-01", "amount": -450, "vendor": "Google Ads", "description": "campaign", "source": "manual"},
        headers=auth_headers,
    )
    assert created.status_code == 200, created.text
    assert created.json()["category"] == "Marketing"
    assert created.json()["amount"] == -450

    csv_data = (
        b"date,amount,vendor,description,category\n"
        b"2026-11-02,-120,Office Depot,stationery,\n"
        b"2026-11-03,5000,Client A,invoice,Income\n"
    )
    imported = client.post(
        "/api/v1/money/transactions/import",
        files={"file": ("transactions.csv", csv_data, "text/csv")},
        headers=auth_headers,
    )
    assert imported.status_code == 200, imported.text
    assert imported.json()["imported"] == 2
    assert "Supplies" in imported.json()["categories"] or "Operations" in imported.json()["categories"]

    listed = client.get("/api/v1/money/transactions?limit=10", headers=auth_headers)
    assert listed.status_code == 200
    assert len(listed.json()) >= 3

    period = "PHASE3-2026-11"
    budget = client.post(
        "/api/v1/money/budgets",
        json={"period": period, "category": "Marketing", "budgeted_amount": 500, "scope": "category"},
        headers=auth_headers,
    )
    assert budget.status_code == 200, budget.text
    variance = client.get(f"/api/v1/money/variance/{period}", headers=auth_headers)
    assert variance.status_code == 200, variance.text
    assert variance.json()["items"][0]["actual"] >= 450
    assert variance.json()["revenue_context"]["revenue"] == 0


def test_money_cashflow_capital_loan_forecast_and_scenarios(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    cashflow = client.post(
        "/api/v1/money/cashflow",
        json={
            "period": "PHASE3-CF",
            "opening_cash": 10000,
            "operating_inflow": 8000,
            "operating_outflow": 12000,
            "investing_inflow": 0,
            "investing_outflow": 1000,
            "financing_inflow": 0,
            "financing_outflow": 0,
        },
        headers=auth_headers,
    )
    assert cashflow.status_code == 200, cashflow.text
    assert cashflow.json()["closing_cash"] == 5000

    analysis = client.get("/api/v1/money/cashflow/analysis", headers=auth_headers)
    assert analysis.status_code == 200
    assert any(row["period"] == "PHASE3-CF" for row in analysis.json()["records"])

    capital = client.post(
        "/api/v1/money/capital",
        json={
            "period": "PHASE3-CAP",
            "shareholders_equity": 100000,
            "total_debt": 50000,
            "total_assets": 180000,
            "ebit": 30000,
            "interest_expense": 5000,
            "cost_of_equity_pct": 12,
            "cost_of_debt_pct": 8,
            "tax_rate_pct": 25,
        },
        headers=auth_headers,
    )
    assert capital.status_code == 200, capital.text
    assert capital.json()["metrics"]["debt_to_equity"] == 0.5

    working = client.get("/api/v1/money/working-capital", headers=auth_headers)
    assert working.status_code == 200, working.text
    assert working.json()["period"] == "2026-Q3"

    quote = client.post(
        "/api/v1/money/loans/quote",
        json={"name": "Growth Loan", "principal": 100000, "annual_rate_pct": 10, "tenure_months": 12},
        headers=auth_headers,
    )
    assert quote.status_code == 200, quote.text
    assert len(quote.json()["schedule"]) == 12

    loan = client.post(
        "/api/v1/money/loans",
        json={"name": "Growth Loan", "principal": 100000, "annual_rate_pct": 10, "tenure_months": 12},
        headers=auth_headers,
    )
    assert loan.status_code == 200, loan.text
    saved_quote = client.get(f"/api/v1/money/loans/{loan.json()['id']}/quote", headers=auth_headers)
    assert saved_quote.status_code == 200

    forecast = client.post(
        "/api/v1/money/forecast",
        json={"metric": "revenue", "series": [100, 110, 120, 130], "periods_ahead": 2, "method": "linear", "store": True},
        headers=auth_headers,
    )
    assert forecast.status_code == 200, forecast.text
    assert forecast.json()["forecast"][0]["value"] == 140
    forecasts = client.get("/api/v1/money/forecasts", headers=auth_headers)
    assert forecasts.status_code == 200
    assert any(item["metric"] == "revenue" for item in forecasts.json())

    scenario = client.post(
        "/api/v1/money/scenarios",
        json={"name": "Hiring Plan", "payload": {"hire": 2}, "result": {"runway": 8}},
        headers=auth_headers,
    )
    assert scenario.status_code == 200, scenario.text
    assert scenario.json()["payload"] == {"hire": 2}
    scenarios = client.get("/api/v1/money/scenarios", headers=auth_headers)
    assert scenarios.status_code == 200
    assert any(item["name"] == "Hiring Plan" for item in scenarios.json())
