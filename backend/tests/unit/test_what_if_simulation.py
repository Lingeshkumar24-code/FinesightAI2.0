import pytest

from app.engines.what_if_simulation import SimulationLevers, WhatIfSimulationEngine


@pytest.fixture
def engine() -> WhatIfSimulationEngine:
    return WhatIfSimulationEngine()


def test_flat_scenario_keeps_cash_flat_when_breakeven(engine: WhatIfSimulationEngine):
    result = engine.simulate(
        starting_revenue=10_000,
        starting_costs=10_000,
        starting_cash=5_000,
        levers=SimulationLevers(),
        periods=3,
    )
    assert result.periods[-1].cash_balance == pytest.approx(5_000)
    assert result.breakeven_period == 0


def test_revenue_growth_increases_cash_over_time(engine: WhatIfSimulationEngine):
    result = engine.simulate(
        starting_revenue=10_000,
        starting_costs=8_000,
        starting_cash=1_000,
        levers=SimulationLevers(monthly_revenue_growth_pct=5.0),
        periods=6,
    )
    balances = [p.cash_balance for p in result.periods]
    assert balances == sorted(balances)  # monotonically increasing


def test_new_fixed_cost_can_push_business_underwater():
    engine = WhatIfSimulationEngine()
    result = engine.simulate(
        starting_revenue=10_000,
        starting_costs=9_500,
        starting_cash=2_000,
        levers=SimulationLevers(new_monthly_fixed_cost=3_000),
        periods=1,
    )
    assert result.periods[0].net_income < 0
    assert result.breakeven_period is None


def test_one_time_cost_only_applied_in_first_period():
    engine = WhatIfSimulationEngine()
    result = engine.simulate(
        starting_revenue=10_000,
        starting_costs=5_000,
        starting_cash=0,
        levers=SimulationLevers(one_time_cost_change=2_000),
        periods=2,
    )
    assert result.periods[0].costs == 7_000
    assert result.periods[1].costs == 5_000


def test_price_increase_raises_revenue_from_period_zero():
    engine = WhatIfSimulationEngine()
    result = engine.simulate(
        starting_revenue=10_000,
        starting_costs=5_000,
        starting_cash=0,
        levers=SimulationLevers(price_change_pct=10.0),
        periods=1,
    )
    assert result.periods[0].revenue == pytest.approx(11_000)


def test_invalid_periods_raises(engine: WhatIfSimulationEngine):
    with pytest.raises(ValueError):
        engine.simulate(
            starting_revenue=1,
            starting_costs=1,
            starting_cash=1,
            levers=SimulationLevers(),
            periods=0,
        )
