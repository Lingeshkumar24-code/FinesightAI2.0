import pytest

from app.engines.forecasting import ForecastingEngine, forecast_series
from app.engines.loan import loan_quote
from app.engines.money_management import (
    analyze_budget_variance,
    analyze_capital_structure,
    analyze_cashflow,
    analyze_working_capital,
    categorize_transaction,
)


def test_categorization_rules() -> None:
    assert categorize_transaction("Google Ads", "monthly campaign", -500)[0] == "Marketing"
    assert categorize_transaction("ACME Corp", "invoice payment", 1200)[0] == "Income"
    assert categorize_transaction("", "", -100)[0] == "Operations"


def test_budget_variance_and_cashflow() -> None:
    variance = analyze_budget_variance(
        [{"category": "Marketing", "budgeted_amount": 1000}],
        [{"category": "Marketing", "amount": 1200}],
    )
    assert variance["items"][0]["severity"] == "breach"
    assert variance["items"][0]["variance_abs"] == -200
    assert "above budget" in variance["narrative"]

    cashflow = analyze_cashflow([
        {"period": "2026-Q1", "opening_cash": 10000, "operating_inflow": 8000, "operating_outflow": 12000},
        {"period": "2026-Q2", "opening_cash": 6000, "operating_inflow": 8000, "operating_outflow": 12000},
    ])
    assert cashflow["latest"]["closing_cash"] == 2000
    assert cashflow["average_monthly_burn"] == 4000
    assert cashflow["runway_months"] == 0.5


def test_capital_structure_and_working_capital() -> None:
    analysis = analyze_capital_structure([
        {
            "period": "2026-Q3",
            "shareholders_equity": 100000,
            "total_debt": 50000,
            "total_assets": 180000,
            "ebit": 30000,
            "interest_expense": 5000,
            "cost_of_equity_pct": 12,
            "cost_of_debt_pct": 8,
            "tax_rate_pct": 25,
        }
    ])
    metrics = analysis["metrics"]
    assert metrics["debt_to_equity"] == 0.5
    assert metrics["interest_coverage"] == 6
    assert metrics["after_tax_cost_of_debt_pct"] == 6
    assert 9 <= metrics["wacc_pct"] <= 11

    working = analyze_working_capital(
        {
            "period": "2026-Q3",
            "total_current_assets": 120000,
            "total_current_liabilities": 60000,
            "inventory": 20000,
            "accounts_receivable": 30000,
        },
        [],
    )
    assert working["working_capital"] == 60000
    assert working["current_ratio"] == 2
    assert working["quick_ratio"] == pytest.approx(1.6667, rel=1e-3)


def test_loan_amortization_and_forecasting() -> None:
    quote = loan_quote(120000, 12, 12)
    assert quote["monthly_emi"] > 10000
    assert quote["schedule"][-1]["closing_balance"] == 0
    assert sum(row["principal"] for row in quote["schedule"]) == pytest.approx(120000, abs=1)

    engine = ForecastingEngine(min_history_points=3)
    assert engine.moving_average([10, 20, 30, 40], 2) == [15, 25, 35]
    linear = engine.forecast_linear([10, 20, 30, 40], periods_ahead=2)
    assert linear.forecast[0].value == 50
    assert linear.r_squared == pytest.approx(1.0)

    series = forecast_series("revenue", [100, 110, 120, 130], 2, "linear")
    assert series["forecast"][0]["value"] == 140
    assert series["forecast"][0]["lower"] < series["forecast"][0]["upper"]
    assert len(series["assumptions"]) >= 4
