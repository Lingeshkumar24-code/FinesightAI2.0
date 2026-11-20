from __future__ import annotations

from dataclasses import dataclass

from app.services.market_data import PriceBar


def sma(values: list[float], window: int) -> list[float | None]:
    if window < 1:
        raise ValueError("window must be >= 1")
    result: list[float | None] = []
    running = 0.0
    for index, value in enumerate(values):
        running += value
        if index >= window:
            running -= values[index - window]
        result.append(round(running / window, 4) if index >= window - 1 else None)
    return result


def ema(values: list[float], span: int) -> list[float | None]:
    if span < 1:
        raise ValueError("span must be >= 1")
    alpha = 2.0 / (span + 1)
    result: list[float | None] = []
    previous: float | None = None
    for value in values:
        previous = value if previous is None else (value * alpha) + (previous * (1 - alpha))
        result.append(round(previous, 4))
    return result


def rsi(values: list[float], period: int = 14) -> list[float | None]:
    if period < 1 or len(values) <= period:
        return [None] * len(values)
    gains = [max(0.0, values[i] - values[i - 1]) for i in range(1, len(values))]
    losses = [max(0.0, values[i - 1] - values[i]) for i in range(1, len(values))]
    result: list[float | None] = [None] * len(values)
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for index in range(period, len(values)):
        if index > period:
            avg_gain = ((avg_gain * (period - 1)) + gains[index - 1]) / period
            avg_loss = ((avg_loss * (period - 1)) + losses[index - 1]) / period
        if avg_loss == 0:
            result[index] = 100.0
        else:
            rs = avg_gain / avg_loss
            result[index] = round(100 - (100 / (1 + rs)), 2)
    return result


def macd(values: list[float], fast: int = 12, slow: int = 26, signal: int = 9) -> dict[str, list[float | None]]:
    fast_line = ema(values, fast)
    slow_line = ema(values, slow)
    macd_line = [
        round(f - s, 4) if f is not None and s is not None else None
        for f, s in zip(fast_line, slow_line)
    ]
    valid = [value for value in macd_line if value is not None]
    signal_values = ema(valid, signal) if valid else []
    signal_line: list[float | None] = [None] * (len(macd_line) - len(signal_values)) + signal_values
    histogram = [
        round(m - s, 4) if m is not None and s is not None else None
        for m, s in zip(macd_line, signal_line)
    ]
    return {"macd": macd_line, "signal": signal_line, "histogram": histogram}


@dataclass
class IndicatorSeries:
    indicator: str
    description: str
    values: list[dict]


class TechnicalAnalysisEngine:
    DESCRIPTIONS = {
        "sma_20": "20-period simple moving average: average close price over the last 20 sessions; a common trend reference.",
        "sma_50": "50-period simple moving average: a longer-term trend reference; compared with SMA20 for crossovers.",
        "ema_20": "20-period exponential moving average: weights recent prices more heavily, so it reacts faster than SMA.",
        "rsi_14": "14-period Relative Strength Index: momentum oscillator from 0 to 100; above 70 is often called overbought, below 30 oversold.",
        "macd": "MACD (12,26,9): difference between fast and slow EMAs; the signal line and histogram help identify momentum shifts.",
        "macd_signal": "MACD signal line: 9-period EMA of the MACD line; crossovers can indicate momentum changes.",
        "macd_histogram": "MACD histogram: MACD minus its signal line; positive bars indicate strengthening upward momentum.",
        "crossover": "Moving-average crossover: SMA20 crossing above SMA50 is treated as bullish, crossing below as bearish.",
        "volume": "Volume analysis: compares session volume with the 20-session average to highlight unusual participation.",
    }

    def analyze(self, bars: list[PriceBar]) -> list[IndicatorSeries]:
        closes = [bar.close for bar in bars]
        dates = [bar.date for bar in bars]
        sma20 = sma(closes, 20)
        sma50 = sma(closes, 50)
        ema20 = ema(closes, 20)
        rsi14 = rsi(closes, 14)
        macd_data = macd(closes)
        volumes = [bar.volume for bar in bars]
        avg_volume = sma(volumes, 20)

        def series(name: str, values: list[float | None]) -> list[dict]:
            return [
                {"date": dates[i], "value": values[i]}
                for i in range(len(dates))
                if values[i] is not None
            ]

        crossover: list[dict] = []
        for i in range(1, len(closes)):
            if sma20[i] is None or sma50[i] is None or sma20[i - 1] is None or sma50[i - 1] is None:
                continue
            previous = sma20[i - 1] - sma50[i - 1]
            current = sma20[i] - sma50[i]
            if previous <= 0 < current:
                crossover.append({"date": dates[i], "value": 1, "signal": "bullish_cross"})
            elif previous >= 0 > current:
                crossover.append({"date": dates[i], "value": -1, "signal": "bearish_cross"})

        volume_series = []
        for i, volume in enumerate(volumes):
            average = avg_volume[i]
            if average and average > 0:
                ratio = round(volume / average, 2)
                volume_series.append(
                    {
                        "date": dates[i],
                        "value": round(volume, 2),
                        "ratio": ratio,
                        "signal": "above_average" if ratio >= 1.5 else "below_average" if ratio <= 0.6 else "normal",
                    }
                )

        return [
            IndicatorSeries("sma_20", self.DESCRIPTIONS["sma_20"], series("sma_20", sma20)),
            IndicatorSeries("sma_50", self.DESCRIPTIONS["sma_50"], series("sma_50", sma50)),
            IndicatorSeries("ema_20", self.DESCRIPTIONS["ema_20"], series("ema_20", ema20)),
            IndicatorSeries("rsi_14", self.DESCRIPTIONS["rsi_14"], series("rsi_14", rsi14)),
            IndicatorSeries("macd", self.DESCRIPTIONS["macd"], series("macd", macd_data["macd"])),
            IndicatorSeries("macd_signal", self.DESCRIPTIONS["macd"], series("macd_signal", macd_data["signal"])),
            IndicatorSeries("macd_histogram", self.DESCRIPTIONS["macd"], series("macd_histogram", macd_data["histogram"])),
            IndicatorSeries("crossover", self.DESCRIPTIONS["crossover"], crossover),
            IndicatorSeries("volume", self.DESCRIPTIONS["volume"], volume_series),
        ]
