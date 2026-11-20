from app.engines.market_indicators import ema, macd, rsi, sma
from app.engines.market_prediction import StockPredictionEngine
from app.services.market_data import DemoMarketDataProvider


def test_sma_ema_rsi_known_values() -> None:
    assert sma([1, 2, 3, 4, 5], 3) == [None, None, 2.0, 3.0, 4.0]
    assert ema([1, 2, 3], 2)[:3] == [1.0, 1.6667, 2.5556]
    rising = list(range(1, 31))
    rsi_values = rsi(rising, 14)
    assert rsi_values[14] == 100.0
    assert all(value is None for value in rsi_values[:14])
    macd_values = macd(rising)
    assert len(macd_values["macd"]) == 30
    assert macd_values["macd"][-1] is not None


def test_prediction_is_chronological_and_bounded() -> None:
    bars = DemoMarketDataProvider().get_history("TCS.NS", days=220)
    result = StockPredictionEngine().predict("TCS.NS", bars, horizon_days=1, model="linear_regression")
    assert result.predicted_direction in ("up", "down", "flat")
    assert result.lower_bound <= result.predicted_price <= result.upper_bound
    assert result.evaluation.sample_size > 0
    assert result.evaluation.mae >= 0
    assert result.evaluation.rmse >= 0
    splits = [step["split_index"] for step in result.evaluation.backtest]
    assert splits == sorted(splits)
    assert all(splits[i] < splits[i + 1] for i in range(len(splits) - 1))
    assert result.feature_count == 9


def test_prediction_rejects_short_history_and_bad_horizon() -> None:
    bars = DemoMarketDataProvider().get_history("INFY.NS", days=40)
    try:
        StockPredictionEngine().predict("INFY.NS", bars, horizon_days=1)
    except ValueError as error:
        assert "at least 80" in str(error)
    else:
        raise AssertionError("short history should be rejected")
    try:
        StockPredictionEngine().predict("INFY.NS", bars, horizon_days=7)
    except ValueError as error:
        assert "horizon_days" in str(error)
    else:
        raise AssertionError("unsupported horizon should be rejected")


import httpx
import respx

from app.services.market_data import (
    DemoMarketDataProvider,
    MarketDataService,
    YahooChartProvider,
)


@respx.mock
def test_yahoo_chart_provider_parses_daily_bars():
    payload = {
        "chart": {
            "result": [
                {
                    "meta": {"currency": "INR", "exchangeName": "NSI"},
                    "timestamp": [1763000000, 1763086400],
                    "indicators": {
                        "quote": [
                            {
                                "open": [2100.0, 2110.5],
                                "high": [2125.0, 2130.0],
                                "low": [2095.0, 2105.0],
                                "close": [2118.4, 2120.94],
                                "volume": [1200000, 1300000],
                            }
                        ]
                    },
                }
            ],
            "error": None,
        }
    }
    respx.get(url__startswith="https://query1.finance.yahoo.com/v8/finance/chart/TCS.NS").mock(
        return_value=httpx.Response(200, json=payload)
    )

    bars = YahooChartProvider().get_history("TCS.NS", days=30)

    assert [bar.close for bar in bars] == [2118.4, 2120.94]
    assert bars[0].date < bars[-1].date
    assert all(bar.close > 0 for bar in bars)


class _FailingProvider:
    name = "broken"
    data_status = "DEMO"

    def get_history(self, symbol: str, days: int = 400):
        raise ValueError("provider unavailable")


@respx.mock
def test_market_data_service_falls_through_to_demo_when_live_providers_fail():
    respx.get(url__startswith="https://query1.finance.yahoo.com").mock(
        side_effect=httpx.ConnectError("blocked")
    )
    service = MarketDataService(
        YahooChartProvider(), _FailingProvider(), DemoMarketDataProvider()
    )

    bars, source, status = service.fetch("TEST.NS", 60)

    assert len(bars) == 60
    assert source == "demo"
    assert status == "DEMO"

