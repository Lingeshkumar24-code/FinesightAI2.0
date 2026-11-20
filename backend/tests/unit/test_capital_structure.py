import pytest

from app.engines.capital_structure import CapitalStructureEngine, CapitalStructureInput


@pytest.fixture
def engine() -> CapitalStructureEngine:
    return CapitalStructureEngine()


def test_wacc_known_values(engine: CapitalStructureEngine):
    # Textbook-style example:
    # E = 600k, D = 400k -> weights 0.6 / 0.4
    # Ke = 15%, Kd = 8% pre-tax, tax = 25% -> after-tax Kd = 6%
    # WACC = 0.6*15 + 0.4*6 = 9 + 2.4 = 11.4%
    data = CapitalStructureInput(
        market_value_equity=600_000,
        market_value_debt=400_000,
        cost_of_equity_pct=15.0,
        cost_of_debt_pct=8.0,
        tax_rate_pct=25.0,
    )
    result = engine.compute(data)
    assert result.equity_weight == pytest.approx(0.6)
    assert result.debt_weight == pytest.approx(0.4)
    assert result.after_tax_cost_of_debt_pct == pytest.approx(6.0)
    assert result.wacc_pct == pytest.approx(11.4)


def test_all_equity_firm_wacc_equals_cost_of_equity(engine: CapitalStructureEngine):
    data = CapitalStructureInput(
        market_value_equity=1_000_000,
        market_value_debt=0,
        cost_of_equity_pct=12.0,
        cost_of_debt_pct=5.0,
        tax_rate_pct=21.0,
    )
    result = engine.compute(data)
    assert result.wacc_pct == pytest.approx(12.0)
    assert result.leverage_ratio == 0.0


def test_zero_total_capital_raises(engine: CapitalStructureEngine):
    data = CapitalStructureInput(
        market_value_equity=0,
        market_value_debt=0,
        cost_of_equity_pct=10.0,
        cost_of_debt_pct=5.0,
        tax_rate_pct=25.0,
    )
    with pytest.raises(ValueError):
        engine.compute(data)


def test_negative_market_value_raises(engine: CapitalStructureEngine):
    data = CapitalStructureInput(
        market_value_equity=-100,
        market_value_debt=100,
        cost_of_equity_pct=10.0,
        cost_of_debt_pct=5.0,
        tax_rate_pct=25.0,
    )
    with pytest.raises(ValueError):
        engine.compute(data)
