from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from app.engines.market_indicators import ema, rsi, sma
from app.services.market_data import PriceBar

SUPPORTED_MODELS = ("linear_regression", "random_forest", "xgboost")
SUPPORTED_HORIZONS = (1, 5, 30)


@dataclass
class Evaluation:
    mae: float
    rmse: float
    directional_accuracy: float
    sample_size: int
    backtest: list[dict] = field(default_factory=list)


@dataclass
class PredictionResult:
    symbol: str
    model: str
    horizon_days: int
    predicted_price: float
    predicted_direction: str
    lower_bound: float
    upper_bound: float
    last_actual_price: float
    target_date: str
    evaluation: Evaluation
    feature_count: int
    data_source: str


def _build_features(bars: list[PriceBar]) -> tuple[np.ndarray, np.ndarray]:
    closes = np.array([bar.close for bar in bars], dtype=float)
    volumes = np.array([bar.volume for bar in bars], dtype=float)
    n = len(closes)
    sma5 = np.array([v if v is not None else np.nan for v in sma(closes.tolist(), 5)])
    sma20 = np.array([v if v is not None else np.nan for v in sma(closes.tolist(), 20)])
    ema10 = np.array([v if v is not None else np.nan for v in ema(closes.tolist(), 10)])
    rsi14 = np.array([v if v is not None else np.nan for v in rsi(closes.tolist(), 14)])
    volume20 = np.array([v if v is not None else np.nan for v in sma(volumes.tolist(), 20)])

    features: list[list[float]] = []
    for i in range(n):
        if i < 20:
            continue
        ret = np.array([
            closes[i] / closes[i - 1] - 1,
            closes[i] / closes[i - 2] - 1,
            closes[i] / closes[i - 3] - 1,
            closes[i] / closes[i - 5] - 1,
        ])
        row = [
            *ret.tolist(),
            closes[i] / sma5[i] - 1 if sma5[i] else 0.0,
            closes[i] / sma20[i] - 1 if sma20[i] else 0.0,
            closes[i] / ema10[i] - 1 if ema10[i] else 0.0,
            (rsi14[i] - 50) / 50 if np.isfinite(rsi14[i]) else 0.0,
            volumes[i] / volume20[i] - 1 if volume20[i] and volume20[i] > 0 else 0.0,
        ]
        features.append(row)
    return np.array(features, dtype=float), closes


def _make_model(model: str):
    if model == "linear_regression":
        from sklearn.linear_model import LinearRegression

        return LinearRegression()
    if model == "random_forest":
        from sklearn.ensemble import RandomForestRegressor

        return RandomForestRegressor(n_estimators=120, max_depth=6, random_state=42, n_jobs=1)
    if model == "xgboost":
        try:
            from xgboost import XGBRegressor
        except ImportError as error:
            raise ValueError("xgboost is not installed; use linear_regression or random_forest") from error
        return XGBRegressor(n_estimators=120, max_depth=4, learning_rate=0.05, random_state=42, verbosity=0)
    raise ValueError(f"Unsupported model: {model}")


def _metrics(actual: np.ndarray, predicted: np.ndarray) -> tuple[float, float, float]:
    if len(actual) == 0:
        return 0.0, 0.0, 0.0
    errors = actual - predicted
    mae = float(np.mean(np.abs(errors)))
    rmse = float(np.sqrt(np.mean(errors ** 2)))
    actual_sign = np.sign(actual)
    predicted_sign = np.sign(predicted)
    direction = float(np.mean(actual_sign == predicted_sign) * 100) if np.any(actual_sign != 0) else 0.0
    return round(mae, 6), round(rmse, 6), round(direction, 2)


class StockPredictionEngine:
    MIN_BARS = {
        1: 80,
        5: 90,
        30: 120,
    }

    def predict(
        self,
        symbol: str,
        bars: list[PriceBar],
        horizon_days: int = 1,
        model: str = "linear_regression",
        data_source: str = "yfinance",
    ) -> PredictionResult:
        if horizon_days not in SUPPORTED_HORIZONS:
            raise ValueError(f"horizon_days must be one of {SUPPORTED_HORIZONS}")
        if model not in SUPPORTED_MODELS:
            raise ValueError(f"model must be one of {SUPPORTED_MODELS}")
        minimum = self.MIN_BARS[horizon_days]
        if len(bars) < minimum:
            raise ValueError(f"Need at least {minimum} historical bars for a {horizon_days}-day horizon, got {len(bars)}")

        features, closes = _build_features(bars)
        targets = np.array(
            [
                closes[i + horizon_days] / closes[i] - 1 if i + horizon_days < len(closes) else np.nan
                for i in range(len(features))
            ],
            dtype=float,
        )
        valid = np.isfinite(features).all(axis=1) & np.isfinite(targets)
        features = features[valid]
        targets = targets[valid]
        if len(features) < 30:
            raise ValueError("Not enough clean features to train a model")

        train_end = int(len(features) * 0.7)
        if train_end < 20 or train_end >= len(features) - 5:
            raise ValueError("Time-series split leaves insufficient train or test data")

        x_train, y_train = features[:train_end], targets[:train_end]
        x_test, y_test = features[train_end:], targets[train_end:]

        estimator = _make_model(model)
        estimator.fit(x_train, y_train)
        test_prediction = estimator.predict(x_test)
        mae, rmse, direction = _metrics(y_test, test_prediction)

        backtest = self._walk_forward(features, targets, model)
        all_backtest_errors = [step["absolute_error"] for step in backtest]
        residual_std = float(np.std(test_prediction - y_test)) if len(y_test) else 0.0
        if residual_std == 0 and all_backtest_errors:
            residual_std = float(np.mean(all_backtest_errors))

        latest_features = features[-1].reshape(1, -1)
        predicted_return = float(estimator.predict(latest_features)[0])
        predicted_return = float(np.clip(predicted_return, -0.45, 0.45))
        last_close = float(closes[-1])
        predicted_price = round(last_close * (1 + predicted_return), 2)
        margin = round(1.96 * residual_std * last_close, 2)
        margin = min(margin, last_close * 0.4)
        predicted_direction = "up" if predicted_return > 0.002 else "down" if predicted_return < -0.002 else "flat"
        target_date = bars[-1].date

        return PredictionResult(
            symbol=symbol,
            model=model,
            horizon_days=horizon_days,
            predicted_price=predicted_price,
            predicted_direction=predicted_direction,
            lower_bound=round(max(0.0, predicted_price - margin), 2),
            upper_bound=round(predicted_price + margin, 2),
            last_actual_price=round(last_close, 2),
            target_date=target_date,
            evaluation=Evaluation(
                mae=mae,
                rmse=rmse,
                directional_accuracy=direction,
                sample_size=len(y_test),
                backtest=backtest,
            ),
            feature_count=features.shape[1],
            data_source=data_source,
        )

    def _walk_forward(self, features: np.ndarray, targets: np.ndarray, model: str, max_steps: int = 20) -> list[dict]:
        n = len(features)
        start = max(20, int(n * 0.5))
        if start >= n - 1:
            return []
        indices = np.linspace(start, n - 1, num=min(max_steps, n - start), dtype=int)
        results: list[dict] = []
        for index in indices:
            estimator = _make_model(model)
            estimator.fit(features[:index], targets[:index])
            predicted = float(estimator.predict(features[index].reshape(1, -1))[0])
            actual = float(targets[index])
            results.append(
                {
                    "split_index": int(index),
                    "predicted_return": round(predicted, 6),
                    "actual_return": round(actual, 6),
                    "absolute_error": round(abs(predicted - actual), 6),
                    "direction_correct": bool(np.sign(predicted) == np.sign(actual)),
                }
            )
        return results
