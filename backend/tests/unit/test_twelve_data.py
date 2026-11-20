import asyncio

import httpx
import pytest

from app.services.twelve_data import MarketDataError, TwelveDataClient

QUOTE_PAYLOAD = {
    "symbol": "AAPL",
    "name": "Apple Inc.",
    "exchange": "NASDAQ",
    "currency": "USD",
    "datetime": "2026-11-18",
    "open": "351.10",
    "high": "353.00",
    "low": "350.25",
    "close": "352.45",
    "previous_close": "351.91",
    "change": "0.54",
    "percent_change": "0.1534",
    "volume": "48123000",
    "is_market_open": False,
}

HISTORY_PAYLOAD = {
    "meta": {
        "symbol": "AAPL",
        "interval": "1day",
        "currency": "USD",
        "exchange": "NASDAQ",
    },
    "values": [
        {
            "datetime": "2026-11-18",
            "open": "351.1",
            "high": "353",
            "low": "350.2",
            "close": "352.45",
            "volume": "48123000",
        },
        {
            "datetime": "2026-11-17",
            "open": "350.0",
            "high": "352",
            "low": "349.5",
            "close": "351.91",
            "volume": "39123000",
        },
    ],
    "status": "ok",
}


def make_client(handler, **kwargs) -> TwelveDataClient:
    return TwelveDataClient("test-key", transport=httpx.MockTransport(handler), **kwargs)


@pytest.mark.asyncio
async def test_normalizes_single_quote():
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json=QUOTE_PAYLOAD)

    quotes = await make_client(handler).quotes(["aapl"])

    assert len(quotes) == 1
    quote = quotes[0]
    assert quote.symbol == "AAPL"
    assert quote.price == pytest.approx(352.45)
    assert quote.percent_change == pytest.approx(0.1534)
    assert quote.volume == 48_123_000
    assert quote.is_market_open is False
    assert calls[0].url.params["symbol"] == "AAPL"
    assert calls[0].url.params["apikey"] == "test-key"


@pytest.mark.asyncio
async def test_batch_quote_keeps_request_order_and_skips_symbol_errors():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "MSFT": {**QUOTE_PAYLOAD, "symbol": "MSFT", "close": "508.33"},
                "AAPL": QUOTE_PAYLOAD,
                "BAD": {"code": 400, "message": "symbol not found", "status": "error"},
            },
        )

    quotes = await make_client(handler).quotes(["MSFT", "AAPL", "BAD"])

    assert [q.symbol for q in quotes] == ["MSFT", "AAPL"]


@pytest.mark.asyncio
async def test_quotes_are_cached_until_ttl_expires():
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return httpx.Response(200, json=QUOTE_PAYLOAD)

    cached = make_client(handler, quote_ttl=60.0)
    await cached.quotes(["AAPL"])
    await cached.quotes(["AAPL"])
    assert calls["count"] == 1

    stale = make_client(handler, quote_ttl=-1.0)
    await stale.quotes(["AAPL"])
    await stale.quotes(["AAPL"])
    assert calls["count"] == 3


@pytest.mark.asyncio
async def test_history_is_returned_oldest_first():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=HISTORY_PAYLOAD)

    history = await make_client(handler).history("AAPL")

    assert history.symbol == "AAPL"
    assert [p.datetime for p in history.points] == ["2026-11-17", "2026-11-18"]
    assert history.points[-1].close == pytest.approx(352.45)


@pytest.mark.asyncio
async def test_concurrent_identical_requests_share_one_provider_call():
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return httpx.Response(200, json=QUOTE_PAYLOAD)

    client = make_client(handler)
    first, second = await asyncio.gather(client.quotes(["AAPL"]), client.quotes(["aapl"]))

    assert calls["count"] == 1
    assert [q.symbol for q in first] == ["AAPL"]
    assert [q.symbol for q in second] == ["AAPL"]


@pytest.mark.asyncio
async def test_missing_api_key_raises_configuration_error():
    client = TwelveDataClient("")
    with pytest.raises(MarketDataError) as excinfo:
        await client.quotes(["AAPL"])
    assert excinfo.value.status_code == 503
    assert "TWELVEDATA_API_KEY" in str(excinfo.value)


@pytest.mark.asyncio
async def test_rate_limit_error_maps_to_429():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            429, json={"code": 429, "message": "out of credits", "status": "error"}
        )

    with pytest.raises(MarketDataError) as excinfo:
        await make_client(handler).quotes(["AAPL"])
    assert excinfo.value.status_code == 429
