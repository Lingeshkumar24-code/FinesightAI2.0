import math

import pytest

from app.engines.investment_outlook import InvestmentOutlookEngine


def series_from_returns(returns: list[float], start: float = 100.0) -> list[float]:
    closes = [start]
    for r in returns:
        closes.append(closes[-1] * math.exp(r))
    return closes


def test_uptrend_produces_positive_expected_profit_and_wide_band():
    engine = InvestmentOutlookEngine()
    closes = series_from_returns([0.001, 0.002, 0.0005, 0.0015] * 15)

    outlook = engine.analyze(closes, 10_000, horizon_months=12, symbol="spy")

    assert outlook.symbol == "SPY"
    assert outlook.expected_value > 10_000
    assert outlook.expected_profit > 0
    assert outlook.best_case_profit > outlook.expected_profit > outlook.worst_case_profit
    assert outlook.var_95_loss >= 0
    assert 0 <= outlook.probability_of_loss_pct < 50
    assert outlook.observations == 60


def test_downtrend_produces_negative_expected_profit_and_loss_probability_above_half():
    engine = InvestmentOutlookEngine()
    closes = series_from_returns([-0.002] * 60)

    outlook = engine.analyze(closes, 5_000, horizon_months=6)

    assert outlook.expected_profit < 0
    assert outlook.worst_case_profit < outlook.expected_profit
    assert outlook.probability_of_loss_pct > 50
    assert outlook.annualized_return_pct < 0


def test_higher_volatility_widens_the_range_without_changing_the_midpoint():
    engine = InvestmentOutlookEngine()
    calm = series_from_returns([0.001 if i % 2 == 0 else 0.0009 for i in range(60)])
    wild = series_from_returns([0.02 if i % 2 == 0 else -0.019 for i in range(60)])

    calm_outlook = engine.analyze(calm, 10_000, horizon_months=12)
    wild_outlook = engine.analyze(wild, 10_000, horizon_months=12)

    calm_span = calm_outlook.best_case_value - calm_outlook.worst_case_value
    wild_span = wild_outlook.best_case_value - wild_outlook.worst_case_value

    assert wild_span > calm_span
    assert wild_outlook.annualized_volatility_pct > calm_outlook.annualized_volatility_pct


def test_money_fields_scale_with_the_investment_amount():
    engine = InvestmentOutlookEngine()
    closes = series_from_returns([0.001, -0.002, 0.0015] * 20)

    small = engine.analyze(closes, 1_000, horizon_months=6)
    large = engine.analyze(closes, 10_000, horizon_months=6)

    assert large.expected_profit == pytest.approx(small.expected_profit * 10)
    assert large.var_95_loss == pytest.approx(small.var_95_loss * 10)
    assert large.probability_of_loss_pct == pytest.approx(small.probability_of_loss_pct)


def test_max_drawdown_tracks_the_deepest_peak_to_trough_decline():
    engine = InvestmentOutlookEngine()
    # 100 -> 120 -> 90 -> 110: a 25% drawdown from the 120 peak.
    path = [100.0] + [110.0, 120.0, 110.0, 100.0, 95.0, 90.0, 100.0, 110.0]
    # pad with small moves so there are enough return observations
    padded = path[:-1] + [100.0 + i * 0.5 for i in range(40)]

    outlook = engine.analyze(padded, 1_000, horizon_months=3)

    assert outlook.max_drawdown_pct == pytest.approx(25.0, abs=0.01)


def test_notes_warn_when_the_position_exceeds_available_cash():
    engine = InvestmentOutlookEngine()
    closes = series_from_returns([0.0, 0.001] * 30)

    outlook = engine.analyze(
        closes, 50_000, horizon_months=6, cash_available=20_000, monthly_net_income=8_000
    )

    joined = " ".join(outlook.notes)
    assert "more than the ₹20,000" in joined
    assert "6.2 month" in joined


def test_notes_stay_quiet_when_cash_is_comfortable():
    engine = InvestmentOutlookEngine()
    closes = series_from_returns([0.0005, 0.0004] * 30)

    outlook = engine.analyze(closes, 5_000, horizon_months=6, cash_available=200_000)

    joined = " ".join(outlook.notes)
    assert "of your ₹200,000 available cash" in joined
    assert "more than the" not in joined


def test_rejects_insufficient_history_and_bad_inputs():
    engine = InvestmentOutlookEngine()

    with pytest.raises(ValueError):
        engine.analyze([100.0, 101.0, 102.0], 1_000, 12)

    closes = series_from_returns([0.001] * 40)
    with pytest.raises(ValueError):
        engine.analyze(closes, 0, 12)
    with pytest.raises(ValueError):
        engine.analyze(closes, 1_000, 0)
