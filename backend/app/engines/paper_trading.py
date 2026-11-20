from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class HoldingState:
    symbol: str
    quantity: float
    average_cost: float


@dataclass
class PortfolioState:
    cash: float
    realized_pnl: float = 0.0
    holdings: dict[str, HoldingState] = field(default_factory=dict)


@dataclass
class TradeResult:
    cash: float
    realized_pnl: float
    holdings: dict[str, HoldingState]
    amount: float
    fee: float
    side: str
    symbol: str
    quantity: float
    price: float


class PaperTradingEngine:
    def apply_trade(
        self,
        state: PortfolioState,
        side: str,
        symbol: str,
        quantity: float,
        price: float,
        fee: float = 0.0,
    ) -> TradeResult:
        if side not in ("buy", "sell"):
            raise ValueError("side must be 'buy' or 'sell'")
        if quantity <= 0:
            raise ValueError("quantity must be positive")
        if price <= 0:
            raise ValueError("price must be positive")
        if fee < 0:
            raise ValueError("fee must be non-negative")

        symbol = symbol.strip().upper()
        amount = round(quantity * price, 2)
        fee = round(fee, 2)
        holdings = {key: HoldingState(value.symbol, value.quantity, value.average_cost) for key, value in state.holdings.items()}
        cash = state.cash
        realized_pnl = state.realized_pnl

        if side == "buy":
            total = amount + fee
            if total > cash + 1e-9:
                raise ValueError(f"Insufficient virtual cash: need {total:.2f}, have {cash:.2f}")
            holding = holdings.get(symbol)
            if holding is None:
                holdings[symbol] = HoldingState(symbol, quantity, price)
            else:
                total_quantity = holding.quantity + quantity
                holding.average_cost = round(
                    ((holding.quantity * holding.average_cost) + amount) / total_quantity, 4
                )
                holding.quantity = round(total_quantity, 6)
            cash = round(cash - total, 2)
        else:
            holding = holdings.get(symbol)
            if holding is None or holding.quantity + 1e-9 < quantity:
                available = holding.quantity if holding else 0.0
                raise ValueError(f"Insufficient holdings: need {quantity}, have {available}")
            proceeds = amount - fee
            realized_pnl = round(realized_pnl + ((price - holding.average_cost) * quantity) - fee, 2)
            holding.quantity = round(holding.quantity - quantity, 6)
            if holding.quantity <= 1e-9:
                holdings.pop(symbol, None)
            cash = round(cash + proceeds, 2)

        return TradeResult(
            cash=cash,
            realized_pnl=realized_pnl,
            holdings=holdings,
            amount=amount,
            fee=fee,
            side=side,
            symbol=symbol,
            quantity=quantity,
            price=price,
        )

    @staticmethod
    def value_portfolio(state: PortfolioState, prices: dict[str, float]) -> dict:
        invested = sum(holding.quantity * prices.get(holding.symbol, holding.average_cost) for holding in state.holdings.values())
        cost_basis = sum(holding.quantity * holding.average_cost for holding in state.holdings.values())
        total = state.cash + invested
        return {
            "cash": round(state.cash, 2),
            "invested": round(invested, 2),
            "cost_basis": round(cost_basis, 2),
            "unrealized_pnl": round(invested - cost_basis, 2),
            "realized_pnl": round(state.realized_pnl, 2),
            "total_value": round(total, 2),
        }
