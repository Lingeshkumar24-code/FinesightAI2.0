import httpx
import pytest

from app.api.routes import market_outlook as market_routes
from app.services.twelve_data import TwelveDataClient

OVERVIEW_PAYLOAD = {
    "SPY": {
        "symbol": "SPY",
        "name": "SPDR S&P 500 ETF Trust",
        "exchange": "NYSE Arca",
        "currency": "USD",
        "datetime": "2026-11-18",
        "close": "682.11",
        "change": "3.20",
        "percent_change": "0.4712",
        "is_market_open": False,
    },
    "QQQ": {
        "symbol": "QQQ",
        "name": "Invesco QQQ Trust",
        "exchange": "NASDAQ",
        "currency": "USD",
        "datetime": "2026-11-18",
        "close": "604.88",
        "change": "-1.15",
        "percent_change": "-0.1897",
        "is_market_open": False,
    },
}


@pytest.fixture()
def fake_market(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/api_usage"):
            return httpx.Response(
                200,
                json={
                    "current_usage": 2,
                    "plan_limit": 8,
                    "daily_usage": 12,
                    "plan_daily_limit": 800,
                    "plan_category": "basic",
                },
            )
        return httpx.Response(200, json=OVERVIEW_PAYLOAD)

    td = TwelveDataClient("test-key", transport=httpx.MockTransport(handler))
    monkeypatch.setattr(market_routes, "_client", lambda settings: td)
    return td


def test_market_overview_returns_live_quotes(client, auth_headers, fake_market):
    resp = client.get("/api/v1/market/overview", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["source"] == "twelvedata"
    assert [q["symbol"] for q in body["quotes"]] == ["SPY", "QQQ"]
    assert body["quotes"][0]["price"] == pytest.approx(682.11)
    assert body["as_of"]


def test_market_overview_requires_auth(client):
    assert client.get("/api/v1/market/overview").status_code == 401


def test_market_overview_rejects_too_many_symbols(client, auth_headers, fake_market):
    resp = client.get(
        "/api/v1/market/overview", headers=auth_headers, params={"symbols": "A,B,C,D,E,F,G"}
    )
    assert resp.status_code == 422
    assert "credits" in resp.json()["detail"]


def test_market_history_rejects_unknown_interval(client, auth_headers, fake_market):
    resp = client.get(
        "/api/v1/market/history", headers=auth_headers, params={"symbol": "SPY", "interval": "7min"}
    )
    assert resp.status_code == 422


def test_market_rate_limit_is_surfaced(client, auth_headers, monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            429, json={"code": 429, "message": "out of credits", "status": "error"}
        )

    td = TwelveDataClient("test-key", transport=httpx.MockTransport(handler))
    monkeypatch.setattr(market_routes, "_client", lambda settings: td)

    resp = client.get("/api/v1/market/overview", headers=auth_headers)
    assert resp.status_code == 429
    assert "rate limit" in resp.json()["detail"].lower()

# --- search -----------------------------------------------------------

SEARCH_PAYLOAD = {
    "data": [
        {
            "symbol": "AAPL",
            "instrument_name": "Apple Inc.",
            "exchange": "NASDAQ",
            "currency": "USD",
            "instrument_type": "Common Stock",
            "country": "United States",
        },
        {
            "symbol": "APLE",
            "instrument_name": "Apple Hospitality REIT Inc.",
            "exchange": "NYSE",
            "currency": "USD",
            "instrument_type": "Common Stock",
            "country": "United States",
        },
    ],
    "status": "ok",
}


def test_market_search_normalizes_results_and_caches(client, auth_headers, monkeypatch):
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        assert request.url.path.endswith("/symbol_search")
        return httpx.Response(200, json=SEARCH_PAYLOAD)

    td = TwelveDataClient("test-key", transport=httpx.MockTransport(handler))
    monkeypatch.setattr(market_routes, "_client", lambda settings: td)

    resp = client.get("/api/v1/market/search", headers=auth_headers, params={"q": "apple"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert [r["symbol"] for r in body] == ["AAPL", "APLE"]
    assert body[0]["name"] == "Apple Inc."
    assert body[0]["instrument_type"] == "Common Stock"

    again = client.get("/api/v1/market/search", headers=auth_headers, params={"q": "apple"})
    assert again.status_code == 200
    assert calls["count"] == 1


def test_market_search_requires_auth(client):
    assert client.get("/api/v1/market/search", params={"q": "aapl"}).status_code == 401


# --- investment outlook -----------------------------------------------


def daily_history_payload(closes: list[float]) -> dict:
    values = [
        {
            "datetime": f"2026-01-{i + 1:02d}",
            "open": str(c),
            "high": str(c * 1.01),
            "low": str(c * 0.99),
            "close": str(c),
            "volume": "1000000",
        }
        for i, c in enumerate(closes)
    ]
    values.reverse()  # Twelve Data returns newest first
    return {
        "meta": {"symbol": "AAPL", "interval": "1day", "currency": "USD", "exchange": "NASDAQ"},
        "values": values,
        "status": "ok",
    }


def up_trend_closes(count: int = 120) -> list[float]:
    closes = [100.0]
    for i in range(count):
        closes.append(closes[-1] * (1.0015 if i % 3 else 0.9995))
    return closes


def test_market_outlook_returns_profit_and_loss_scenarios(
    client, auth_headers, monkeypatch
):
    payload = daily_history_payload(up_trend_closes())

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/time_series")
        return httpx.Response(200, json=payload)

    td = TwelveDataClient("test-key", transport=httpx.MockTransport(handler))
    monkeypatch.setattr(market_routes, "_client", lambda settings: td)

    resp = client.post(
        "/api/v1/market/outlook",
        headers=auth_headers,
        json={
            "symbol": "aapl",
            "amount": 10000,
            "horizon_months": 12,
            "cash_available": 62000,
            "monthly_net_income": 5800,
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["symbol"] == "AAPL"
    assert body["expected_value"] > 0
    assert body["best_case_value"] >= body["expected_value"] >= body["worst_case_value"]
    assert body["var_95_loss"] >= 0
    assert 0 <= body["probability_of_loss_pct"] <= 100
    assert body["latest_close"] is not None
    assert any("available cash" in note for note in body["notes"])
    assert body["alert"] is None


def test_market_outlook_notify_raises_alert_and_dispatches(
    client, auth_headers, monkeypatch
):
    payload = daily_history_payload(up_trend_closes())

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    td = TwelveDataClient("test-key", transport=httpx.MockTransport(handler))
    monkeypatch.setattr(market_routes, "_client", lambda settings: td)

    dispatched: list[dict] = []

    async def fake_dispatch(alert, settings):
        dispatched.append(alert)
        return True

    monkeypatch.setattr(market_routes.alerts_routes, "dispatch_alert_to_n8n", fake_dispatch)

    resp = client.post(
        "/api/v1/market/outlook",
        headers=auth_headers,
        json={"symbol": "AAPL", "amount": 5000, "horizon_months": 6, "notify": True},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["alert"]["title"].startswith("Investment Outlook: AAPL")
    assert dispatched and dispatched[0]["title"] == body["alert"]["title"]

    feed = client.get("/api/v1/alerts", headers=auth_headers).json()
    assert any(a["title"] == body["alert"]["title"] for a in feed)


def test_market_outlook_rejects_bad_amount(client, auth_headers, monkeypatch):
    td = TwelveDataClient(
        "test-key",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json=daily_history_payload(up_trend_closes()))
        ),
    )
    monkeypatch.setattr(market_routes, "_client", lambda settings: td)

    resp = client.post(
        "/api/v1/market/outlook",
        headers=auth_headers,
        json={"symbol": "AAPL", "amount": -5, "horizon_months": 6},
    )
    assert resp.status_code == 422
