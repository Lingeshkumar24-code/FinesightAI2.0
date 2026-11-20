import pytest

from app.engines.forecasting import ForecastingEngine


@pytest.fixture
def engine() -> ForecastingEngine:
    return ForecastingEngine(min_history_points=3)


def test_perfect_linear_series_has_r_squared_of_one(engine: ForecastingEngine):
    series = [100.0, 200.0, 300.0, 400.0, 500.0]
    result = engine.forecast_linear(series, periods_ahead=2)
    assert result.r_squared == pytest.approx(1.0, abs=1e-6)
    assert result.slope == pytest.approx(100.0, rel=1e-3)


def test_forecast_continues_the_trend(engine: ForecastingEngine):
    series = [10.0, 20.0, 30.0, 40.0]
    result = engine.forecast_linear(series, periods_ahead=2)
    assert result.forecast[0].value == pytest.approx(50.0, rel=1e-2)
    assert result.forecast[1].value == pytest.approx(60.0, rel=1e-2)


def test_too_few_points_raises(engine: ForecastingEngine):
    with pytest.raises(ValueError):
        engine.forecast_linear([10.0, 20.0], periods_ahead=1)


def test_invalid_periods_ahead_raises(engine: ForecastingEngine):
    with pytest.raises(ValueError):
        engine.forecast_linear([10.0, 20.0, 30.0], periods_ahead=0)


def test_moving_average_smooths_series(engine: ForecastingEngine):
    series = [10.0, 20.0, 30.0, 40.0, 50.0]
    smoothed = engine.moving_average(series, window=3)
    assert smoothed == [20.0, 30.0, 40.0]


def test_moving_average_window_too_large_raises(engine: ForecastingEngine):
    with pytest.raises(ValueError):
        engine.moving_average([1.0, 2.0], window=5)


def test_flat_series_has_zero_slope(engine: ForecastingEngine):
    series = [50.0, 50.0, 50.0, 50.0]
    result = engine.forecast_linear(series, periods_ahead=1)
    assert result.slope == pytest.approx(0.0, abs=1e-6)
