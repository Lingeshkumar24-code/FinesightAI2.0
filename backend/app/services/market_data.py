from __future__ import annotations

import asyncio
import hashlib
import math
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.extensions import StockInstrument, StockPrice

DEFAULT_SYMBOLS = [
    "RELIANCE.NS",
    "TCS.NS",
    "INFY.NS",
    "HDFCBANK.NS",
    "ICICIBANK.NS",
    "SBIN.NS",
]

SYMBOL_NAMES = {
    "RELIANCE.NS": "Reliance Industries Limited",
    "TCS.NS": "Tata Consultancy Services Limited",
    "INFY.NS": "Infosys Limited",
    "HDFCBANK.NS": "HDFC Bank Limited",
    "ICICIBANK.NS": "ICICI Bank Limited",
    "SBIN.NS": "State Bank of India",
}


@dataclass
class PriceBar:
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: float


class MarketDataProvider(ABC):
    name: str = "base"
    data_status: str = "UNKNOWN"

    @abstractmethod
    def get_history(self, symbol: str, days: int = 400) -> list[PriceBar]:
        raise NotImplementedError


def normalize_symbol(symbol: str) -> str:
    cleaned = symbol.strip().upper()
    if not cleaned:
        raise ValueError("Symbol cannot be empty")
    if cleaned.endswith(".NS") or cleaned.endswith(".BO"):
        return cleaned
    return f"{cleaned}.NS"


def exchange_for_symbol(symbol: str) -> str:
    return "BSE" if symbol.upper().endswith(".BO") else "NSE"


class YFinanceProvider(MarketDataProvider):
    name = "yfinance"
    data_status = "DELAYED"

    def __init__(self, timeout: int = 20) -> None:
        self.timeout = timeout

    def get_history(self, symbol: str, days: int = 400) -> list[PriceBar]:
        import yfinance as yf

        start = (date.today() - timedelta(days=days)).isoformat()
        ticker = yf.Ticker(symbol)
        frame = ticker.history(start=start, auto_adjust=False, timeout=self.timeout)
        if frame is None or frame.empty:
            raise ValueError(f"No historical data returned for {symbol}")
        bars: list[PriceBar] = []
        for index, row in frame.iterrows():
            close = float(row["Close"])
            if not math.isfinite(close) or close <= 0:
                continue
            bars.append(
                PriceBar(
                    date=index.date().isoformat() if hasattr(index, "date") else str(index)[:10],
                    open=float(row["Open"]) if math.isfinite(float(row["Open"])) else close,
                    high=float(row["High"]) if math.isfinite(float(row["High"])) else close,
                    low=float(row["Low"]) if math.isfinite(float(row["Low"])) else close,
                    close=close,
                    volume=float(row["Volume"]) if math.isfinite(float(row["Volume"])) else 0.0,
                )
            )
        return clean_bars(bars)


class YahooChartProvider(MarketDataProvider):
    """Yahoo Finance chart JSON, fetched directly.

    yfinance's own request path is regularly rate-limited (HTTP 429) from
    shared/cloud IPs while the public chart endpoint still answers with a
    normal browser user-agent. This provider speaks that endpoint
    directly so NSE quotes stay real instead of silently degrading to
    demo prices.
    """

    name = "yahoo"
    data_status = "DELAYED"
    BASE_URL = "https://query1.finance.yahoo.com/v8/finance/chart"
    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    )

    def __init__(self, timeout: float = 20.0) -> None:
        self.timeout = timeout

    def get_history(self, symbol: str, days: int = 400) -> list[PriceBar]:
        import httpx

        end = int(datetime.now(timezone.utc).timestamp())
        start = end - max(days, 40) * 86_400
        response = httpx.get(
            f"{self.BASE_URL}/{symbol}",
            params={
                "period1": start,
                "period2": end,
                "interval": "1d",
                "events": "div,splits",
            },
            headers={"User-Agent": self.USER_AGENT, "Accept": "application/json"},
            timeout=self.timeout,
            follow_redirects=True,
        )
        response.raise_for_status()
        payload = response.json()
        results = ((payload.get("chart") or {}).get("result") or [])
        if not results:
            error = (payload.get("chart") or {}).get("error") or {}
            raise ValueError(
                error.get("description") or f"No historical data returned for {symbol}"
            )
        result = results[0]
        timestamps = result.get("timestamp") or []
        quote = ((result.get("indicators") or {}).get("quote") or [{}])[0]
        opens = quote.get("open") or []
        highs = quote.get("high") or []
        lows = quote.get("low") or []
        closes = quote.get("close") or []
        volumes = quote.get("volume") or []

        bars: list[PriceBar] = []
        for index, stamp in enumerate(timestamps):
            close = self._pick(closes, index)
            if close is None or not math.isfinite(close) or close <= 0:
                continue
            bars.append(
                PriceBar(
                    date=datetime.fromtimestamp(stamp, timezone.utc).date().isoformat(),
                    open=self._pick(opens, index) or close,
                    high=self._pick(highs, index) or close,
                    low=self._pick(lows, index) or close,
                    close=close,
                    volume=self._pick(volumes, index) or 0.0,
                )
            )
        if not bars:
            raise ValueError(f"No historical data returned for {symbol}")
        return clean_bars(bars)

    @staticmethod
    def _pick(values: list, index: int) -> float | None:
        if index >= len(values) or values[index] is None:
            return None
        try:
            return float(values[index])
        except (TypeError, ValueError):
            return None


class DemoMarketDataProvider(MarketDataProvider):
    name = "demo"
    data_status = "DEMO"

    def get_history(self, symbol: str, days: int = 400) -> list[PriceBar]:
        seed = int(hashlib.sha256(symbol.encode()).hexdigest()[:8], 16)
        rng = random.Random(seed)
        count = min(max(days, 40), 400)
        start = date.today() - timedelta(days=count)
        price = 480.0 + (seed % 1900)
        bars: list[PriceBar] = []
        current = start
        while len(bars) < count:
            if current.weekday() < 5:
                drift = math.sin(len(bars) / 17.0) * 0.0018 + 0.00035
                shock = rng.gauss(0, 0.011)
                open_price = price
                price = max(1.0, price * (1 + drift + shock))
                high = max(open_price, price) * (1 + abs(rng.gauss(0, 0.004)))
                low = min(open_price, price) * (1 - abs(rng.gauss(0, 0.004)))
                volume = 1_200_000 + rng.randint(0, 2_400_000)
                bars.append(
                    PriceBar(
                        date=current.isoformat(),
                        open=round(open_price, 2),
                        high=round(high, 2),
                        low=round(low, 2),
                        close=round(price, 2),
                        volume=float(volume),
                    )
                )
            current += timedelta(days=1)
        return bars


def clean_bars(bars: list[PriceBar]) -> list[PriceBar]:
    unique: dict[str, PriceBar] = {}
    for bar in bars:
        if bar.date and math.isfinite(bar.close) and bar.close > 0:
            unique[bar.date] = bar
    return [unique[key] for key in sorted(unique)]


class MarketDataService:
    def __init__(
        self,
        primary: MarketDataProvider,
        fallback: MarketDataProvider | None = None,
        last_resort: MarketDataProvider | None = None,
    ) -> None:
        self.primary = primary
        self.fallback = fallback or DemoMarketDataProvider()
        # Demo prices keep the UI usable when every live provider is down,
        # and the response is labelled DEMO so they are never mistaken for
        # exchange quotes.
        self.last_resort = last_resort or DemoMarketDataProvider()

    # Rows written by the demo provider are synthetic. They are never used
    # as a cache (otherwise the page would be frozen on invented prices),
    # and stale primary rows are refetched so "cached" still means recent.
    DEMO_SOURCES = {"demo"}
    MAX_CACHE_AGE_DAYS = 7

    def fetch(self, symbol: str, days: int) -> tuple[list[PriceBar], str, str]:
        """Walk primary → fallback → demo until one provider answers."""
        last_error: Exception | None = None
        for provider in (self.primary, self.fallback, self.last_resort):
            try:
                bars = provider.get_history(symbol, days=days)
            except Exception as exc:  # noqa: BLE001 - provider-specific errors
                last_error = exc
                continue
            if bars:
                return bars, provider.name, provider.data_status
        raise ValueError(f"No market data available for {symbol}: {last_error}")

    async def history(
        self,
        symbol: str,
        session: AsyncSession | None = None,
        days: int = 400,
        refresh: bool = False,
    ) -> tuple[list[PriceBar], str, str]:
        normalized = normalize_symbol(symbol)
        cached: list[PriceBar] = []
        if session is not None and not refresh:
            rows = (await session.execute(
                select(StockPrice)
                .where(StockPrice.symbol == normalized)
                .where(StockPrice.source.notin_(self.DEMO_SOURCES))
                .order_by(StockPrice.trade_date.desc())
                .limit(days)
            )).scalars().all()
            cached = [
                PriceBar(
                    date=row.trade_date,
                    open=row.open,
                    high=row.high,
                    low=row.low,
                    close=row.close,
                    volume=row.volume,
                )
                for row in reversed(rows)
            ]
            if cached:
                try:
                    latest = date.fromisoformat(cached[-1].date)
                except ValueError:
                    cached = []
                else:
                    if (date.today() - latest).days > self.MAX_CACHE_AGE_DAYS:
                        cached = []

        if cached:
            return cached, "cached", "CACHED"

        bars, source, status = await asyncio.to_thread(self.fetch, normalized, days)

        if session is not None and bars and source not in self.DEMO_SOURCES:
            existing_dates = {
                row[0]
                for row in (await session.execute(
                    select(StockPrice.trade_date).where(StockPrice.symbol == normalized)
                )).all()
            }
            for bar in bars:
                if bar.date not in existing_dates:
                    session.add(
                        StockPrice(
                            symbol=normalized,
                            trade_date=bar.date,
                            open=bar.open,
                            high=bar.high,
                            low=bar.low,
                            close=bar.close,
                            volume=bar.volume,
                            source=source,
                        )
                    )
            await session.merge(
                StockInstrument(
                    symbol=normalized,
                    name=SYMBOL_NAMES.get(normalized, normalized.replace(".NS", "")),
                    exchange=exchange_for_symbol(normalized),
                    currency="INR",
                    source=source,
                    updated_at=datetime.now(timezone.utc),
                )
            )
            await session.commit()

        return bars, source, status


def quote_from_bars(symbol: str, bars: list[PriceBar], source: str, status: str) -> dict:
    if not bars:
        return {
            "symbol": symbol,
            "name": SYMBOL_NAMES.get(symbol, symbol),
            "exchange": exchange_for_symbol(symbol),
            "currency": "INR",
            "source": source,
            "data_status": status,
            "as_of": "",
            "latest_price": None,
            "daily_change": None,
            "daily_change_pct": None,
            "volume": None,
            "trend": "insufficient_data",
        }
    latest = bars[-1]
    previous = bars[-2] if len(bars) > 1 else latest
    change = round(latest.close - previous.close, 2)
    change_pct = round((change / previous.close) * 100, 2) if previous.close else 0.0
    window = bars[-20:] if len(bars) >= 20 else bars
    trend = "insufficient_data"
    if len(window) >= 5:
        slope = window[-1].close - window[0].close
        trend = "uptrend" if slope > 0 else "downtrend" if slope < 0 else "sideways"
    return {
        "symbol": symbol,
        "name": SYMBOL_NAMES.get(symbol, symbol),
        "exchange": exchange_for_symbol(symbol),
        "currency": "INR",
        "source": source,
        "data_status": status,
        "as_of": latest.date,
        "latest_price": latest.close,
        "daily_change": change,
        "daily_change_pct": change_pct,
        "volume": latest.volume,
        "trend": trend,
    }
