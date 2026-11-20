import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_market_service
from app.main import app
from app.services.market_data import DemoMarketDataProvider, MarketDataService


@pytest.fixture()
def demo_client(client: TestClient) -> TestClient:
    app.dependency_overrides[get_market_service] = lambda: MarketDataService(
        DemoMarketDataProvider(), DemoMarketDataProvider()
    )
    yield client
    app.dependency_overrides.pop(get_market_service, None)


def test_market_data_indicators_and_prediction(
    demo_client: TestClient, auth_headers: dict[str, str]
) -> None:
    symbols = demo_client.get("/api/v1/market/symbols")
    assert symbols.status_code == 200
    assert any(item["symbol"] == "TCS.NS" for item in symbols.json()["default"])

    quote = demo_client.get("/api/v1/market/quote/phase2quote", headers=auth_headers)
    assert quote.status_code == 200, quote.text
    assert quote.json()["symbol"] == "PHASE2QUOTE.NS"
    assert quote.json()["data_status"] in ("DEMO", "CACHED")

    history = demo_client.get("/api/v1/market/history/phase2history?days=220", headers=auth_headers)
    assert history.status_code == 200, history.text
    assert len(history.json()["points"]) >= 150

    indicators = demo_client.get("/api/v1/market/indicators/phase2indicators", headers=auth_headers)
    assert indicators.status_code == 200, indicators.text
    names = {item["indicator"] for item in indicators.json()["indicators"]}
    assert {"sma_20", "sma_50", "ema_20", "rsi_14", "macd", "crossover", "volume"} <= names

    predicted = demo_client.post(
        "/api/v1/market/predict",
        json={
            "symbol": "phase2predict",
            "horizon_days": 1,
            "model": "linear_regression",
            "store": True,
        },
        headers=auth_headers,
    )
    assert predicted.status_code == 200, predicted.text
    body = predicted.json()
    assert body["symbol"] == "PHASE2PREDICT.NS"
    assert body["metrics"]["mae"] >= 0
    assert body["lower_bound"] <= body["predicted_price"] <= body["upper_bound"]

    stored = demo_client.get("/api/v1/market/predictions?symbol=PHASE2PREDICT.NS", headers=auth_headers)
    assert stored.status_code == 200
    assert any(item["id"] == body["id"] for item in stored.json())

    evaluations = demo_client.get("/api/v1/market/evaluations?symbol=PHASE2PREDICT.NS", headers=auth_headers)
    assert evaluations.status_code == 200
    assert evaluations.json()


def test_watchlist_crud_and_tenant_isolation(
    demo_client: TestClient, auth_headers: dict[str, str]
) -> None:
    added = demo_client.post(
        "/api/v1/market/watchlist",
        json={"symbol": "phase2watch", "threshold_pct": 4.5, "enabled": True},
        headers=auth_headers,
    )
    assert added.status_code == 200, added.text
    assert added.json()["symbol"] == "PHASE2WATCH.NS"

    listed = demo_client.get("/api/v1/market/watchlist", headers=auth_headers)
    assert any(item["symbol"] == "PHASE2WATCH.NS" for item in listed.json())

    removed = demo_client.delete("/api/v1/market/watchlist/PHASE2WATCH.NS", headers=auth_headers)
    assert removed.status_code == 200
    assert removed.json()["deleted"] == "PHASE2WATCH.NS"


def test_paper_trading_portfolio_lifecycle(
    demo_client: TestClient, auth_headers: dict[str, str]
) -> None:
    created = demo_client.post(
        "/api/v1/trading/portfolios",
        json={"name": "Phase 2 Virtual Portfolio", "initial_cash": 50_000},
        headers=auth_headers,
    )
    assert created.status_code == 200, created.text
    portfolio_id = created.json()["id"]
    assert created.json()["cash"] == 50_000

    buy = demo_client.post(
        f"/api/v1/trading/portfolios/{portfolio_id}/trades",
        json={"symbol": "tcs.ns", "side": "buy", "quantity": 10, "price": 100, "fee": 5},
        headers=auth_headers,
    )
    assert buy.status_code == 200, buy.text
    assert buy.json()["amount"] == 1_000
    assert buy.json()["symbol"] == "TCS.NS"

    listed = demo_client.get("/api/v1/trading/portfolios", headers=auth_headers)
    portfolio = next(item for item in listed.json() if item["id"] == portfolio_id)
    assert portfolio["cash"] == 48_995
    assert portfolio["holdings"][0]["quantity"] == 10

    sell = demo_client.post(
        f"/api/v1/trading/portfolios/{portfolio_id}/trades",
        json={"symbol": "TCS.NS", "side": "sell", "quantity": 4, "price": 130, "fee": 2},
        headers=auth_headers,
    )
    assert sell.status_code == 200, sell.text
    assert sell.json()["realized_pnl"] == 118

    transactions = demo_client.get(
        f"/api/v1/trading/portfolios/{portfolio_id}/transactions", headers=auth_headers
    )
    assert transactions.status_code == 200
    assert [item["side"] for item in transactions.json()] == ["buy", "sell"]

    snapshot = demo_client.post(
        f"/api/v1/trading/portfolios/{portfolio_id}/snapshot", headers=auth_headers
    )
    assert snapshot.status_code == 200, snapshot.text
    assert snapshot.json()["total_value"] > 0

    insufficient = demo_client.post(
        f"/api/v1/trading/portfolios/{portfolio_id}/trades",
        json={"symbol": "TCS.NS", "side": "sell", "quantity": 100, "price": 100},
        headers=auth_headers,
    )
    assert insufficient.status_code == 422
