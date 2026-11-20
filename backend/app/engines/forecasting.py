from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np


@dataclass
class ForecastPoint:
    period_index: int
    value: float


@dataclass
class ForecastResult:
    method: str
    slope: float
    r_squared: float
    history: list[ForecastPoint]
    forecast: list[ForecastPoint]


class ForecastingEngine:
    def __init__(self, min_history_points: int = 3) -> None:
        if min_history_points < 2:
            raise ValueError("min_history_points must be at least 2")
        self.min_history_points = min_history_points

    @staticmethod
    def _clean(series: list[float]) -> list[float]:
        try:
            values = [float(value) for value in series]
        except (TypeError, ValueError) as error:
            raise ValueError("series must contain numeric values") from error
        if not all(math.isfinite(value) for value in values):
            raise ValueError("series must contain only finite values")
        return values

    def moving_average(self, series: list[float], window: int = 3) -> list[float]:
        values = self._clean(series)
        if window < 1:
            raise ValueError("window must be at least 1")
        if window > len(values):
            raise ValueError("window cannot exceed the number of observations")
        return [round(sum(values[index - window:index]) / window, 4) for index in range(window, len(values) + 1)]

    def forecast_linear(self, series: list[float], periods_ahead: int = 3) -> ForecastResult:
        values = self._clean(series)
        if len(values) < self.min_history_points:
            raise ValueError(f"At least {self.min_history_points} observations are required")
        if periods_ahead < 1:
            raise ValueError("periods_ahead must be at least 1")

        x = np.arange(len(values), dtype=float)
        y = np.array(values, dtype=float)
        slope, intercept = np.polyfit(x, y, 1)
        fitted = slope * x + intercept
        residuals = y - fitted
        total_variance = float(np.sum((y - np.mean(y)) ** 2))
        residual_variance = float(np.sum(residuals ** 2))
        r_squared = 1.0 if total_variance == 0 else max(0.0, 1 - residual_variance / total_variance)

        history = [ForecastPoint(period_index=index, value=value) for index, value in enumerate(values)]
        forecast = [
            ForecastPoint(
                period_index=len(values) + offset,
                value=round(float(slope * (len(values) + offset) + intercept), 4),
            )
            for offset in range(periods_ahead)
        ]
        return ForecastResult(
            method="linear_regression",
            slope=round(float(slope), 6),
            r_squared=round(float(r_squared), 6),
            history=history,
            forecast=forecast,
        )


def forecast_series(metric: str, values: list[float], periods_ahead: int = 3, method: str = "auto") -> dict:
    clean = [float(value) for value in values if value is not None and math.isfinite(float(value))]
    if len(clean) < 3:
        raise ValueError("At least three numeric observations are required for forecasting")
    if periods_ahead < 1 or periods_ahead > 24:
        raise ValueError("periods_ahead must be between 1 and 24")
    if method not in ("auto", "linear", "average"):
        raise ValueError("method must be one of auto, linear, average")

    x = np.arange(len(clean), dtype=float)
    y = np.array(clean, dtype=float)
    slope, intercept = np.polyfit(x, y, 1)
    linear_fit = slope * x + intercept
    residuals = y - linear_fit
    linear_error = float(np.std(residuals)) if len(residuals) > 1 else 0.0
    mean = float(np.mean(y))
    average_error = float(np.std(y - mean)) if len(y) > 1 else 0.0
    total_change = abs(float(y[-1] - y[0]))
    average_magnitude = max(abs(mean), 1.0)

    chosen = method
    if method == "auto":
        chosen = "linear" if abs(slope) * len(clean) > average_magnitude * 0.15 else "average"
    fitted = linear_fit if chosen == "linear" else np.full(len(clean), mean)
    error = linear_error if chosen == "linear" else average_error
    margin = max(1.96 * error, abs(mean) * 0.001)

    history = [
        {"step": int(index), "actual": round(clean[index], 4), "fitted": round(float(fitted[index]), 4)}
        for index in range(len(clean))
    ]
    forecast = []
    for step in range(1, periods_ahead + 1):
        index = len(clean) + step - 1
        point = float(slope * index + intercept) if chosen == "linear" else mean
        forecast.append(
            {
                "step": step,
                "value": round(point, 4),
                "lower": round(max(0.0, point - margin), 4),
                "upper": round(point + margin, 4),
            }
        )

    assumptions = [
        f"Method selected: {chosen}.",
        f"Based on {len(clean)} historical observations of {metric}.",
        f"95% interval uses historical residual dispersion of {error:.4f}.",
        "No structural breaks or external events are modelled.",
    ]
    if chosen == "linear":
        assumptions.append(f"Observed trend is {slope:.4f} per period over a total change of {total_change:.4f}.")
    else:
        assumptions.append("Trend was not strong enough to justify extrapolation; historical mean was used.")
    return {
        "metric": metric,
        "method": chosen,
        "history": history,
        "forecast": forecast,
        "assumptions": assumptions,
        "uncertainty": [
            {"step": point["step"], "margin": round(margin, 4), "lower": point["lower"], "upper": point["upper"]}
            for point in forecast
        ],
    }
