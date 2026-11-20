from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_market_service
from app.core.security import TokenPayload, get_current_user
from app.db.extensions import (
    PortfolioHolding,
    PortfolioSnapshot,
    VirtualPortfolio,
    VirtualTransaction,
)
from app.db.session import get_session
from app.db.util import as_dict
from app.engines.paper_trading import HoldingState as PaperHolding
from app.engines.paper_trading import PaperTradingEngine, PortfolioState
from app.models.schemas_ext import PortfolioIn, PortfolioOut, TradeIn, TradeOut
from app.services.market_data import MarketDataService, normalize_symbol

router = APIRouter(prefix="/trading", tags=["paper-trading"])


async def _load_state(session: AsyncSession, portfolio_id: str) -> PortfolioState:
    portfolio = await session.get(VirtualPortfolio, portfolio_id)
    if portfolio is None:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    holdings = (await session.execute(
        select(PortfolioHolding).where(PortfolioHolding.portfolio_id == portfolio_id)
    )).scalars().all()
    return PortfolioState(
        cash=float(portfolio.cash),
        realized_pnl=float(portfolio.realized_pnl),
        holdings={
            row.symbol: PaperHolding(row.symbol, float(row.quantity), float(row.average_cost))
            for row in holdings
        },
    )


async def _latest_prices(
    symbols: list[str],
    service: MarketDataService,
    session: AsyncSession,
    overrides: dict[str, float] | None = None,
) -> dict[str, float]:
    prices: dict[str, float] = {}
    for symbol in symbols:
        normalized = normalize_symbol(symbol)
        if overrides and normalized in overrides:
            prices[normalized] = float(overrides[normalized])
            continue
        bars, _, _ = await service.history(normalized, session=session, days=10)
        if not bars:
            raise HTTPException(status_code=422, detail=f"No price available for {normalized}")
        prices[normalized] = bars[-1].close
    return prices


def _portfolio_out(portfolio: VirtualPortfolio, valuation: dict, holdings: list[dict]) -> PortfolioOut:
    data = as_dict(portfolio)
    data.update(valuation)
    initial = float(portfolio.initial_cash)
    total_return = ((valuation["total_value"] - initial) / initial * 100) if initial else 0.0
    data["total_return_pct"] = round(total_return, 2)
    data["holdings"] = holdings
    return PortfolioOut(**data)


@router.post("/portfolios", response_model=PortfolioOut)
async def create_portfolio(
    payload: PortfolioIn,
    user: TokenPayload = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> PortfolioOut:
    if payload.initial_cash <= 0:
        raise HTTPException(status_code=422, detail="initial_cash must be positive")
    portfolio = VirtualPortfolio(
        business_id=user.business_id,
        name=payload.name,
        initial_cash=payload.initial_cash,
        cash=payload.initial_cash,
    )
    session.add(portfolio)
    await session.commit()
    await session.refresh(portfolio)
    return _portfolio_out(portfolio, {"cash": portfolio.cash, "invested": 0.0, "total_value": portfolio.cash, "unrealized_pnl": 0.0, "realized_pnl": 0.0}, [])


@router.get("/portfolios", response_model=list[PortfolioOut])
async def list_portfolios(
    user: TokenPayload = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    service: MarketDataService = Depends(get_market_service),
) -> list[PortfolioOut]:
    portfolios = (await session.execute(
        select(VirtualPortfolio).where(VirtualPortfolio.business_id == user.business_id)
    )).scalars().all()
    output = []
    for portfolio in portfolios:
        state = await _load_state(session, portfolio.id)
        prices = await _latest_prices(list(state.holdings.keys()), service, session) if state.holdings else {}
        valuation = PaperTradingEngine.value_portfolio(state, prices)
        holdings = [
            {
                "symbol": symbol,
                "quantity": holding.quantity,
                "average_cost": holding.average_cost,
                "last_price": prices.get(symbol, holding.average_cost),
                "market_value": round(holding.quantity * prices.get(symbol, holding.average_cost), 2),
            }
            for symbol, holding in state.holdings.items()
        ]
        output.append(_portfolio_out(portfolio, valuation, holdings))
    return output


@router.post("/portfolios/{portfolio_id}/trades", response_model=TradeOut)
async def execute_trade(
    portfolio_id: str,
    payload: TradeIn,
    user: TokenPayload = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    service: MarketDataService = Depends(get_market_service),
) -> TradeOut:
    portfolio = await session.get(VirtualPortfolio, portfolio_id)
    if portfolio is None or portfolio.business_id != user.business_id:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    symbol = normalize_symbol(payload.symbol)
    override = {symbol: payload.price} if payload.price is not None else None
    prices = await _latest_prices([symbol], service, session, override)
    state = await _load_state(session, portfolio_id)
    engine = PaperTradingEngine()
    try:
        result = engine.apply_trade(state, payload.side, symbol, payload.quantity, prices[symbol], payload.fee)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    for holding in result.holdings.values():
        row = (await session.execute(
            select(PortfolioHolding).where(
                PortfolioHolding.portfolio_id == portfolio_id,
                PortfolioHolding.symbol == holding.symbol,
            )
        )).scalars().first()
        if row is None:
            session.add(
                PortfolioHolding(
                    portfolio_id=portfolio_id,
                    symbol=holding.symbol,
                    quantity=holding.quantity,
                    average_cost=holding.average_cost,
                )
            )
        else:
            row.quantity = holding.quantity
            row.average_cost = holding.average_cost
    removed = set(result.holdings)
    existing = (await session.execute(
        select(PortfolioHolding).where(PortfolioHolding.portfolio_id == portfolio_id)
    )).scalars().all()
    for row in existing:
        if row.symbol not in removed:
            await session.delete(row)

    transaction = VirtualTransaction(
        portfolio_id=portfolio_id,
        business_id=user.business_id,
        symbol=symbol,
        side=payload.side,
        quantity=payload.quantity,
        price=prices[symbol],
        amount=result.amount,
        fee=result.fee,
        realized_pnl=result.realized_pnl - portfolio.realized_pnl,
        executed_at=datetime.now(timezone.utc).isoformat(),
    )
    session.add(transaction)
    portfolio.cash = result.cash
    portfolio.realized_pnl = result.realized_pnl
    await session.commit()
    await session.refresh(transaction)
    return TradeOut(**as_dict(transaction))


@router.get("/portfolios/{portfolio_id}/transactions", response_model=list[TradeOut])
async def transactions(
    portfolio_id: str,
    user: TokenPayload = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[TradeOut]:
    portfolio = await session.get(VirtualPortfolio, portfolio_id)
    if portfolio is None or portfolio.business_id != user.business_id:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    rows = (await session.execute(
        select(VirtualTransaction).where(VirtualTransaction.portfolio_id == portfolio_id).order_by(VirtualTransaction.created_at)
    )).scalars().all()
    return [TradeOut(**as_dict(row)) for row in rows]


@router.post("/portfolios/{portfolio_id}/snapshot")
async def snapshot(
    portfolio_id: str,
    user: TokenPayload = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    service: MarketDataService = Depends(get_market_service),
) -> dict:
    portfolio = await session.get(VirtualPortfolio, portfolio_id)
    if portfolio is None or portfolio.business_id != user.business_id:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    state = await _load_state(session, portfolio_id)
    prices = await _latest_prices(list(state.holdings.keys()), service, session) if state.holdings else {}
    valuation = PaperTradingEngine.value_portfolio(state, prices)
    row = PortfolioSnapshot(
        portfolio_id=portfolio_id,
        snapshot_date=datetime.now(timezone.utc).date().isoformat(),
        cash=valuation["cash"],
        invested=valuation["invested"],
        total_value=valuation["total_value"],
        unrealized_pnl=valuation["unrealized_pnl"],
        realized_pnl=valuation["realized_pnl"],
    )
    session.add(row)
    await session.commit()
    return as_dict(row)


@router.get("/portfolios/{portfolio_id}/snapshots")
async def snapshots(
    portfolio_id: str,
    user: TokenPayload = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    portfolio = await session.get(VirtualPortfolio, portfolio_id)
    if portfolio is None or portfolio.business_id != user.business_id:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    rows = (await session.execute(
        select(PortfolioSnapshot).where(PortfolioSnapshot.portfolio_id == portfolio_id).order_by(PortfolioSnapshot.snapshot_date)
    )).scalars().all()
    return [as_dict(row) for row in rows]
