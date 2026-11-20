import pytest

from app.engines.financial_statement import (
    BalanceSheet,
    FinancialStatementEngine,
    IncomeStatement,
)


@pytest.fixture
def engine() -> FinancialStatementEngine:
    return FinancialStatementEngine()


@pytest.fixture
def healthy_balance_sheet() -> BalanceSheet:
    return BalanceSheet(
        cash=50_000,
        accounts_receivable=20_000,
        inventory=10_000,
        other_current_assets=5_000,
        total_current_assets=85_000,
        total_assets=250_000,
        total_current_liabilities=40_000,
        total_liabilities=90_000,
        total_equity=160_000,
    )


@pytest.fixture
def healthy_income_statement() -> IncomeStatement:
    return IncomeStatement(
        revenue=300_000,
        cogs=120_000,
        operating_expenses=90_000,
        net_income=60_000,
    )


def _ratio(results, name):
    return next(r for r in results if r.name == name)


def test_current_ratio(engine, healthy_balance_sheet, healthy_income_statement):
    results = engine.compute(healthy_balance_sheet, healthy_income_statement)
    assert _ratio(results, "current_ratio").value == pytest.approx(85_000 / 40_000, rel=1e-3)


def test_quick_ratio_excludes_inventory(engine, healthy_balance_sheet, healthy_income_statement):
    results = engine.compute(healthy_balance_sheet, healthy_income_statement)
    expected = (85_000 - 10_000) / 40_000
    assert _ratio(results, "quick_ratio").value == pytest.approx(expected, rel=1e-3)


def test_gross_margin_pct(engine, healthy_balance_sheet, healthy_income_statement):
    results = engine.compute(healthy_balance_sheet, healthy_income_statement)
    gross_profit = 300_000 - 120_000
    expected_pct = round(gross_profit / 300_000 * 100, 2)
    assert _ratio(results, "gross_margin_pct").value == expected_pct


def test_net_margin_pct(engine, healthy_balance_sheet, healthy_income_statement):
    results = engine.compute(healthy_balance_sheet, healthy_income_statement)
    expected_pct = round(60_000 / 300_000 * 100, 2)
    assert _ratio(results, "net_margin_pct").value == expected_pct


def test_debt_to_equity(engine, healthy_balance_sheet, healthy_income_statement):
    results = engine.compute(healthy_balance_sheet, healthy_income_statement)
    assert _ratio(results, "debt_to_equity").value == pytest.approx(90_000 / 160_000, rel=1e-3)


def test_zero_revenue_does_not_raise(engine, healthy_balance_sheet):
    zero_rev_income = IncomeStatement(revenue=0, cogs=0, operating_expenses=1_000, net_income=-1_000)
    results = engine.compute(healthy_balance_sheet, zero_rev_income)
    assert _ratio(results, "gross_margin_pct").value is None
    assert _ratio(results, "net_margin_pct").value is None


def test_zero_liabilities_debt_to_equity_is_zero_not_error(engine, healthy_income_statement):
    bs = BalanceSheet(
        cash=10_000,
        accounts_receivable=0,
        inventory=0,
        other_current_assets=0,
        total_current_assets=10_000,
        total_assets=10_000,
        total_current_liabilities=0,
        total_liabilities=0,
        total_equity=10_000,
    )
    results = engine.compute(bs, healthy_income_statement)
    assert _ratio(results, "debt_to_equity").value == 0.0


def test_working_capital(engine, healthy_balance_sheet, healthy_income_statement):
    results = engine.compute(healthy_balance_sheet, healthy_income_statement)
    assert _ratio(results, "working_capital").value == 85_000 - 40_000
