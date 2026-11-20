from app.engines.paper_trading import HoldingState, PaperTradingEngine, PortfolioState


def test_buy_updates_cash_and_average_cost() -> None:
    engine = PaperTradingEngine()
    state = PortfolioState(cash=10_000)

    first = engine.apply_trade(state, "buy", "tcs.ns", 10, 100)
    assert first.cash == 9_000
    assert first.holdings["TCS.NS"].average_cost == 100

    second = engine.apply_trade(
        PortfolioState(cash=first.cash, realized_pnl=first.realized_pnl, holdings=first.holdings),
        "buy",
        "TCS.NS",
        10,
        200,
    )
    assert second.cash == 7_000
    assert second.holdings["TCS.NS"].quantity == 20
    assert second.holdings["TCS.NS"].average_cost == 150


def test_sell_realizes_pnl_and_removes_closed_holding() -> None:
    engine = PaperTradingEngine()
    state = PortfolioState(
        cash=5_000,
        holdings={"INFY.NS": HoldingState("INFY.NS", 20, 100)},
    )
    result = engine.apply_trade(state, "sell", "INFY.NS", 20, 130, fee=10)
    assert result.cash == 7_590
    assert result.realized_pnl == 590
    assert "INFY.NS" not in result.holdings


def test_trade_validation_and_portfolio_valuation() -> None:
    engine = PaperTradingEngine()
    state = PortfolioState(cash=500)
    for kwargs in (
        {"side": "hold", "symbol": "TCS.NS", "quantity": 1, "price": 100},
        {"side": "buy", "symbol": "TCS.NS", "quantity": 0, "price": 100},
        {"side": "buy", "symbol": "TCS.NS", "quantity": 1, "price": 0},
        {"side": "buy", "symbol": "TCS.NS", "quantity": 10, "price": 100},
        {"side": "sell", "symbol": "TCS.NS", "quantity": 1, "price": 100},
    ):
        try:
            engine.apply_trade(state, **kwargs)
        except ValueError:
            continue
        raise AssertionError(f"expected validation error for {kwargs}")

    valued = PortfolioState(
        cash=1_000,
        realized_pnl=50,
        holdings={"TCS.NS": HoldingState("TCS.NS", 5, 200)},
    )
    valuation = PaperTradingEngine.value_portfolio(valued, {"TCS.NS": 240})
    assert valuation["invested"] == 1_200
    assert valuation["unrealized_pnl"] == 200
    assert valuation["total_value"] == 2_200
