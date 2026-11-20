from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_market_service
from app.core.security import TokenPayload, get_current_user
from app.db.extensions import (
    ModelEvaluation,
    PredictionRecord,
    TechnicalIndicatorRow,
    Watchlist,
)
from app.db.session import get_session
from app.db.util import as_dict, iso
from app.engines.market_indicators import TechnicalAnalysisEngine
from app.engines.market_prediction import (
    SUPPORTED_HORIZONS,
    SUPPORTED_MODELS,
    StockPredictionEngine,
)
from app.models.schemas_ext import (
    EvaluationOut,
    IndicatorsOut,
    PredictionOut,
    PredictionRequest,
    PricePoint,
    StockHistoryOut,
    StockInfoOut,
    WatchlistIn,
    WatchlistOut,
)
from app.services.market_data import (
    DEFAULT_SYMBOLS,
    SYMBOL_NAMES,
    MarketDataService,
    normalize_symbol,
    quote_from_bars,
)

router = APIRouter(prefix="/market", tags=["market-intelligence"])


@router.get("/symbols")
def symbols() -> dict:
    return {
        "default": [
            {"symbol": symbol, "name": SYMBOL_NAMES.get(symbol, symbol), "exchange": "NSE"}
            for symbol in DEFAULT_SYMBOLS
        ],
        "note": "Historical/delayed NSE data via yfinance. Not live exchange prices. Search accepts any yfinance-supported symbol.",
    }


@router.get("/quote/{symbol}", response_model=StockInfoOut)
async def quote(
    symbol: str,
    service: MarketDataService = Depends(get_market_service),
    session: AsyncSession = Depends(get_session),
    _user: TokenPayload = Depends(get_current_user),
) -> StockInfoOut:
    normalized = normalize_symbol(symbol)
    bars, source, data_status = await service.history(normalized, session=session, days=400)
    return StockInfoOut(**quote_from_bars(normalized, bars, source, data_status))


@router.get("/history/{symbol}", response_model=StockHistoryOut)
async def history(
    symbol: str,
    days: int = 400,
    refresh: bool = False,
    service: MarketDataService = Depends(get_market_service),
    session: AsyncSession = Depends(get_session),
    _user: TokenPayload = Depends(get_current_user),
) -> StockHistoryOut:
    normalized = normalize_symbol(symbol)
    bars, source, data_status = await service.history(
        normalized, session=session, days=min(max(days, 30), 400), refresh=refresh
    )
    return StockHistoryOut(
        symbol=normalized,
        source=source,
        data_status=data_status,
        as_of=bars[-1].date if bars else "",
        points=[PricePoint(**bar.__dict__) for bar in bars],
    )


@router.get("/indicators/{symbol}", response_model=IndicatorsOut)
async def indicators(
    symbol: str,
    service: MarketDataService = Depends(get_market_service),
    session: AsyncSession = Depends(get_session),
    _user: TokenPayload = Depends(get_current_user),
) -> IndicatorsOut:
    normalized = normalize_symbol(symbol)
    bars, source, data_status = await service.history(normalized, session=session, days=400)
    analysis = TechnicalAnalysisEngine().analyze(bars)
    existing_rows = (
        await session.execute(
            select(TechnicalIndicatorRow.trade_date, TechnicalIndicatorRow.indicator)
            .where(TechnicalIndicatorRow.symbol == normalized)
        )
    ).all()
    existing_keys = {(row[0], row[1]) for row in existing_rows}
    new_rows: list[TechnicalIndicatorRow] = []
    for item in analysis:
        for point in item.values:
            key = (point["date"], item.indicator)
            if key not in existing_keys:
                new_rows.append(
                    TechnicalIndicatorRow(
                        symbol=normalized,
                        trade_date=point["date"],
                        indicator=item.indicator,
                        value=point["value"],
                        params_json="{}",
                    )
                )
                existing_keys.add(key)
    if new_rows:
        session.add_all(new_rows)
    await session.commit()
    return IndicatorsOut(
        symbol=normalized,
        source=source,
        data_status=data_status,
        indicators=[{"indicator": item.indicator, "description": item.description, "values": item.values} for item in analysis],
    )


@router.post("/predict", response_model=PredictionOut)
async def predict(
    payload: PredictionRequest,
    service: MarketDataService = Depends(get_market_service),
    session: AsyncSession = Depends(get_session),
    user: TokenPayload = Depends(get_current_user),
) -> PredictionOut:
    normalized = normalize_symbol(payload.symbol)
    if payload.horizon_days not in SUPPORTED_HORIZONS:
        raise HTTPException(status_code=422, detail=f"horizon_days must be one of {SUPPORTED_HORIZONS}")
    if payload.model not in SUPPORTED_MODELS:
        raise HTTPException(status_code=422, detail=f"model must be one of {SUPPORTED_MODELS}")
    bars, source, data_status = await service.history(normalized, session=session, days=400, refresh=True)
    engine = StockPredictionEngine()
    try:
        result = engine.predict(
            normalized, bars, horizon_days=payload.horizon_days, model=payload.model, data_source=source
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    metrics = {
        "mae": result.evaluation.mae,
        "rmse": result.evaluation.rmse,
        "directional_accuracy": result.evaluation.directional_accuracy,
        "sample_size": result.evaluation.sample_size,
        "backtest": result.evaluation.backtest,
        "feature_count": result.feature_count,
        "data_status": data_status,
    }
    prediction = PredictionRecord(
        business_id=user.business_id,
        symbol=normalized,
        model=result.model,
        horizon_days=result.horizon_days,
        predicted_price=result.predicted_price,
        predicted_direction=result.predicted_direction,
        lower_bound=result.lower_bound,
        upper_bound=result.upper_bound,
        last_actual_price=result.last_actual_price,
        metrics_json=json.dumps(metrics),
        target_date=result.target_date,
        data_source=source,
    )
    evaluation = ModelEvaluation(
        symbol=normalized,
        model=result.model,
        horizon_days=result.horizon_days,
        mae=result.evaluation.mae,
        rmse=result.evaluation.rmse,
        directional_accuracy=result.evaluation.directional_accuracy,
        sample_size=result.evaluation.sample_size,
        backtest_json=json.dumps(result.evaluation.backtest),
        data_source=source,
    )
    if payload.store:
        session.add(prediction)
        session.add(evaluation)
        await session.commit()
        await session.refresh(prediction)
        created_at = iso(prediction.created_at)
        prediction_id = prediction.id
    else:
        created_at = datetime.now(timezone.utc).isoformat()
        prediction_id = "not_stored"

    return PredictionOut(
        id=prediction_id,
        symbol=normalized,
        model=result.model,
        horizon_days=result.horizon_days,
        predicted_price=result.predicted_price,
        predicted_direction=result.predicted_direction,
        lower_bound=result.lower_bound,
        upper_bound=result.upper_bound,
        last_actual_price=result.last_actual_price,
        metrics=metrics,
        created_at=created_at,
        target_date=result.target_date,
        actual_price=None,
        data_source=source,
    )


@router.get("/predictions", response_model=list[PredictionOut])
async def predictions(
    symbol: str | None = None,
    user: TokenPayload = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[PredictionOut]:
    query = select(PredictionRecord).where(PredictionRecord.business_id == user.business_id)
    if symbol:
        query = query.where(PredictionRecord.symbol == normalize_symbol(symbol))
    rows = (await session.execute(query.order_by(PredictionRecord.created_at.desc()))).scalars().all()
    output = []
    for row in rows:
        data = as_dict(row)
        data["metrics"] = json.loads(row.metrics_json)
        output.append(PredictionOut(**data))
    return output


@router.get("/evaluations", response_model=list[EvaluationOut])
async def evaluations(
    symbol: str | None = None,
    _user: TokenPayload = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[EvaluationOut]:
    query = select(ModelEvaluation)
    if symbol:
        query = query.where(ModelEvaluation.symbol == normalize_symbol(symbol))
    rows = (await session.execute(query.order_by(ModelEvaluation.created_at.desc()))).scalars().all()
    return [EvaluationOut(**as_dict(row)) for row in rows]


@router.get("/watchlist", response_model=list[WatchlistOut])
async def get_watchlist(
    user: TokenPayload = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[WatchlistOut]:
    rows = (await session.execute(
        select(Watchlist).where(Watchlist.business_id == user.business_id)
    )).scalars().all()
    return [WatchlistOut(**as_dict(row)) for row in rows]


@router.post("/watchlist", response_model=WatchlistOut)
async def add_watchlist(
    payload: WatchlistIn,
    user: TokenPayload = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> WatchlistOut:
    normalized = normalize_symbol(payload.symbol)
    row = (await session.execute(
        select(Watchlist).where(Watchlist.business_id == user.business_id, Watchlist.symbol == normalized)
    )).scalars().first()
    if row is None:
        row = Watchlist(business_id=user.business_id, symbol=normalized)
        session.add(row)
    row.threshold_pct = payload.threshold_pct
    row.enabled = payload.enabled
    await session.commit()
    await session.refresh(row)
    return WatchlistOut(**as_dict(row))


@router.delete("/watchlist/{symbol}")
async def remove_watchlist(
    symbol: str,
    user: TokenPayload = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    normalized = normalize_symbol(symbol)
    await session.execute(
        delete(Watchlist).where(Watchlist.business_id == user.business_id, Watchlist.symbol == normalized)
    )
    await session.commit()
    return {"deleted": normalized}
