"""Twelve Data market-data client.

Wraps the REST endpoints FinSight uses (real-time quotes, daily bars,
ticker search and the plan-usage counter) in a small TTL cache.

The free Twelve Data plan allows 8 credits per minute and 1 credit per
symbol, so:
  * every symbol is fetched at most once per TTL window,
  * batched quote requests are capped by the caller (``MARKET_MAX_SYMBOLS``),
  * the UI refreshes on demand instead of polling.

Missing keys and upstream errors surface as :class:`MarketDataError`, which
the route layer turns into an HTTP error so the app degrades gracefully
instead of 500-ing.

This is the benchmark/lookup client used by ``/market/search`` and
``/market/outlook``. The NSE quote/history/prediction stack lives in
:mod:`app.services.market_data` (yfinance) and is unchanged.
"""
from __future__ import annotations

import asyncio
import time
from typing import Any, Awaitable, Callable, Iterable, Sequence

import httpx
import structlog

from app.models.schemas_ext import (
    MarketHistory,
    MarketPricePoint,
    MarketQuote,
    MarketSearchResult,
    MarketUsage,
)

logger = structlog.get_logger("finsight.market")

DEFAULT_BASE_URL = "https://api.twelvedata.com"

# Quote prices move constantly; bars only once a day. Both are cached far
# below the provider's rate limit on purpose: every request costs credits
# (8/minute, 800/day on the free plan).
QUOTE_TTL_SECONDS = 300.0
HISTORY_TTL_SECONDS = 1800.0
USAGE_TTL_SECONDS = 120.0
SEARCH_TTL_SECONDS = 3600.0


class MarketDataError(RuntimeError):
    """Raised when market data cannot be fetched (missing key, bad symbol, 429...)."""

    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


def _as_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_int(value: Any) -> int | None:
    number = _as_float(value)
    return None if number is None else int(number)


def normalize_quote(symbol: str, payload: dict[str, Any]) -> MarketQuote:
    """Map a Twelve Data ``/quote`` object onto our schema."""
    return MarketQuote(
        symbol=payload.get("symbol") or symbol,
        name=payload.get("name") or "",
        exchange=payload.get("exchange") or "",
        currency=payload.get("currency") or "",
        price=_as_float(payload.get("close")),
        change=_as_float(payload.get("change")),
        percent_change=_as_float(payload.get("percent_change")),
        open=_as_float(payload.get("open")),
        high=_as_float(payload.get("high")),
        low=_as_float(payload.get("low")),
        previous_close=_as_float(payload.get("previous_close")),
        volume=_as_int(payload.get("volume")),
        is_market_open=payload.get("is_market_open"),
        updated_at=payload.get("datetime") or payload.get("last_quote_at"),
    )


class TwelveDataClient:
    def __init__(
        self,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
        *,
        quote_ttl: float = QUOTE_TTL_SECONDS,
        history_ttl: float = HISTORY_TTL_SECONDS,
        usage_ttl: float = USAGE_TTL_SECONDS,
        search_ttl: float = SEARCH_TTL_SECONDS,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._quote_ttl = quote_ttl
        self._history_ttl = history_ttl
        self._usage_ttl = usage_ttl
        self._search_ttl = search_ttl
        self._transport = transport
        self._cache: dict[str, tuple[float, Any]] = {}
        # Concurrent identical requests (React StrictMode mounts, two tabs)
        # share one provider call: the free plan allows only 8 credits a
        # minute and every symbol costs one credit.
        self._inflight: dict[str, asyncio.Task[Any]] = {}

    # --- plumbing -------------------------------------------------------

    @property
    def configured(self) -> bool:
        return bool(self._api_key)

    def _cache_get(self, key: str, ttl: float) -> Any | None:
        hit = self._cache.get(key)
        if hit and time.monotonic() - hit[0] < ttl:
            return hit[1]
        return None

    def _cache_put(self, key: str, value: Any) -> None:
        self._cache[key] = (time.monotonic(), value)

    async def _cached(
        self, key: str, ttl: float, factory: Callable[[], Awaitable[Any]]
    ) -> Any:
        """Return a cached value, or await one shared in-flight fetch."""
        cached = self._cache_get(key, ttl)
        if cached is not None:
            return cached
        task = self._inflight.get(key)
        if task is None:
            task = asyncio.ensure_future(factory())
            self._inflight[key] = task
            task.add_done_callback(lambda _t, k=key: self._inflight.pop(k, None))
        return await task

    async def _cached_with_flag(
        self, key: str, ttl: float, factory: Callable[[], Awaitable[Any]]
    ) -> tuple[Any, bool]:
        """Like :meth:`_cached` but also reports whether the value was cached."""
        was_cached = self._cache_get(key, ttl) is not None
        return await self._cached(key, ttl, factory), was_cached

    async def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        if not self.configured:
            raise MarketDataError("TWELVEDATA_API_KEY is not configured", status_code=503)
        query = {**params, "apikey": self._api_key}
        try:
            async with httpx.AsyncClient(
                timeout=12.0, transport=self._transport
            ) as client:
                resp = await client.get(f"{self._base_url}{path}", params=query)
        except httpx.HTTPError as exc:
            logger.warning("market_request_failed", path=path, error=str(exc))
            raise MarketDataError("Market data provider is unreachable") from exc

        try:
            payload = resp.json()
        except ValueError as exc:
            raise MarketDataError("Market data provider returned a non-JSON response") from exc

        # Twelve Data signals rate limits with either a 429 or a 200 + code.
        if isinstance(payload, dict) and payload.get("status") == "error":
            code = _as_int(payload.get("code")) or resp.status_code
            message = payload.get("message") or "Market data provider rejected the request"
            logger.warning("market_provider_error", path=path, code=code, message=message)
            if code == 429:
                raise MarketDataError(
                    "Twelve Data rate limit reached (8 credits/minute on the free plan). "
                    "Wait a minute and refresh.",
                    status_code=429,
                )
            raise MarketDataError(message, status_code=502)
        if resp.status_code >= 400:
            raise MarketDataError(
                f"Market data provider returned HTTP {resp.status_code}",
                status_code=502,
            )
        return payload

    # --- public API -----------------------------------------------------

    async def _fetch_quotes(
        self, wanted: Sequence[str], key: str
    ) -> list[MarketQuote]:
        payload = await self._get("/quote", {"symbol": ",".join(wanted)})
        quotes: list[MarketQuote] = []
        if all(isinstance(v, dict) for v in payload.values()) and "symbol" not in payload:
            for symbol, item in payload.items():
                if item.get("status") == "error" or item.get("code"):
                    logger.info(
                        "market_quote_skipped", symbol=symbol, message=item.get("message")
                    )
                    continue
                quotes.append(normalize_quote(symbol, item))
        else:
            quotes.append(normalize_quote(wanted[0], payload))

        if not quotes:
            raise MarketDataError("No quote data returned for the requested symbols")
        # Preserve the caller's ordering so the watchlist doesn't jump around.
        order = {s: i for i, s in enumerate(wanted)}
        quotes.sort(key=lambda q: order.get(q.symbol.upper(), len(order)))
        self._cache_put(key, quotes)
        return quotes

    async def quotes(self, symbols: Sequence[str]) -> list[MarketQuote]:
        _quotes, _cached = await self.quotes_with_source(symbols)
        return _quotes

    async def quotes_with_source(
        self, symbols: Sequence[str]
    ) -> tuple[list[MarketQuote], bool]:
        """Quotes plus whether they came from the in-memory cache.

        The flag lets the UI say "cached" instead of implying a fresh
        provider call (and a fresh credit) happened.
        """
        wanted = [s.strip().upper() for s in symbols if s.strip()]
        if not wanted:
            return [], False
        key = "quotes:" + ",".join(sorted(wanted))
        return await self._cached_with_flag(
            key, self._quote_ttl, lambda: self._fetch_quotes(wanted, key)
        )

    async def search(self, query: str, limit: int = 8) -> list[MarketSearchResult]:
        """Ticker/company search (``/symbol_search``), cached for an hour."""
        term = query.strip()
        if not term:
            return []
        key = f"search:{term.lower()}:{limit}"

        async def fetch() -> list[MarketSearchResult]:
            payload = await self._get(
                "/symbol_search", {"symbol": term, "outputsize": limit}
            )
            rows = payload.get("data") if isinstance(payload, dict) else None
            results = [
                MarketSearchResult(
                    symbol=str(row.get("symbol") or ""),
                    name=str(row.get("instrument_name") or ""),
                    exchange=str(row.get("exchange") or ""),
                    currency=str(row.get("currency") or ""),
                    instrument_type=str(row.get("instrument_type") or ""),
                    country=str(row.get("country") or ""),
                )
                for row in (rows or [])
                if row.get("symbol")
            ]
            self._cache_put(key, results)
            return results

        return await self._cached(key, self._search_ttl, fetch)

    async def history(
        self, symbol: str, interval: str = "1day", outputsize: int = 30
    ) -> MarketHistory:
        symbol = symbol.strip().upper()
        key = f"history:{symbol}:{interval}:{outputsize}"

        async def fetch() -> MarketHistory:
            payload = await self._get(
                "/time_series",
                {"symbol": symbol, "interval": interval, "outputsize": outputsize},
            )
            meta = payload.get("meta") or {}
            points: Iterable[dict[str, Any]] = payload.get("values") or []
            series = [
                MarketPricePoint(
                    datetime=str(point.get("datetime")),
                    open=_as_float(point.get("open")),
                    high=_as_float(point.get("high")),
                    low=_as_float(point.get("low")),
                    close=_as_float(point.get("close")),
                    volume=_as_int(point.get("volume")),
                )
                for point in points
            ]
            series.reverse()  # provider returns newest first
            result = MarketHistory(
                symbol=meta.get("symbol") or symbol,
                interval=meta.get("interval") or interval,
                currency=meta.get("currency") or "",
                exchange=meta.get("exchange") or "",
                points=series,
            )
            self._cache_put(key, result)
            return result

        return await self._cached(key, self._history_ttl, fetch)

    async def usage(self) -> MarketUsage | None:
        async def fetch() -> MarketUsage | None:
            try:
                payload = await self._get("/api_usage", {})
            except MarketDataError:
                return None
            usage = MarketUsage(
                current_usage=_as_int(payload.get("current_usage")),
                plan_limit=_as_int(payload.get("plan_limit")),
                daily_usage=_as_int(payload.get("daily_usage")),
                plan_daily_limit=_as_int(payload.get("plan_daily_limit")),
                plan_category=payload.get("plan_category") or "",
            )
            self._cache_put("usage", usage)
            return usage

        return await self._cached("usage", self._usage_ttl, fetch)
