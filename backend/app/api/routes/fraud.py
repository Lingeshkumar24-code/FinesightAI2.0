from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.core.security import TokenPayload, get_current_user
from app.db.extensions import AlertReview, FraudAlert, FraudTransaction
from app.db.util import as_dict, iso
from app.engines.fraud_detection import detect_fraud, parse_transaction_csv, summarize_fraud
from app.models.schemas_ext import (
    AlertOut,
    FraudSummaryOut,
    FraudTransactionOut,
    FraudUploadOut,
    ReviewIn,
)

router = APIRouter(prefix="/fraud", tags=["fraud-detection"])

_REVIEW_ACTIONS = {"confirm", "dismiss", "escalate"}


def _alert_out(alert: FraudAlert) -> AlertOut:
    data = as_dict(alert)
    return AlertOut(**{key: (iso(data.get(key)) if key in {"created_at", "date"} else data.get(key)) for key in AlertOut.model_fields})


def _transaction_out(record: FraudTransaction) -> FraudTransactionOut:
    data = as_dict(record)
    return FraudTransactionOut(**{key: (iso(data.get(key)) if key == "created_at" else data.get(key)) for key in FraudTransactionOut.model_fields})


@router.post("/transactions/upload", response_model=FraudUploadOut)
async def upload_transactions(
    file: UploadFile,
    user: TokenPayload = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> FraudUploadOut:
    raw = await file.read()
    parsed, errors = parse_transaction_csv(raw)
    batch_id = str(uuid.uuid4())

    existing = (await session.execute(
        select(FraudTransaction).where(FraudTransaction.business_id == user.business_id)
    )).scalars().all()
    history = [as_dict(record) for record in existing]
    new_records = [{**record, "batch_id": batch_id} for record in parsed]

    alerts = [
        alert for alert in detect_fraud(history + new_records)
        if any(record["transaction_id"] == alert["transaction_id"] for record in new_records)
    ]

    for record in new_records:
        session.add(FraudTransaction(business_id=user.business_id, source="upload", **record))
    for alert in alerts:
        session.add(FraudAlert(
            business_id=user.business_id,
            batch_id=batch_id,
            risk_level=alert["risk_level"],
            reason=alert["reason"],
            detection_method=alert["detection_method"],
            recommended_action=alert["recommended_action"],
            **{key: alert[key] for key in ("transaction_id", "amount", "date", "vendor")},
        ))
    await session.commit()

    summary = summarize_fraud(history + new_records, alerts)
    return FraudUploadOut(
        batch_id=batch_id,
        received=len(parsed) + len(errors),
        valid=len(parsed),
        invalid=len(errors),
        validation_errors=errors,
        alerts_created=len(alerts),
        summary=summary,
    )


@router.get("/transactions", response_model=list[FraudTransactionOut])
async def list_transactions(
    limit: int = 100,
    user: TokenPayload = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[FraudTransactionOut]:
    rows = (await session.execute(
        select(FraudTransaction)
        .where(FraudTransaction.business_id == user.business_id)
        .order_by(FraudTransaction.created_at.desc())
        .limit(limit)
    )).scalars().all()
    return [_transaction_out(row) for row in rows]


@router.get("/alerts", response_model=list[AlertOut])
async def list_alerts(
    status_filter: str | None = None,
    user: TokenPayload = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[AlertOut]:
    query = select(FraudAlert).where(FraudAlert.business_id == user.business_id)
    if status_filter:
        query = query.where(FraudAlert.status == status_filter)
    rows = (await session.execute(query.order_by(FraudAlert.created_at.desc()))).scalars().all()
    return [_alert_out(row) for row in rows]


@router.post("/alerts/{alert_id}/review", response_model=AlertOut)
async def review_alert(
    alert_id: str,
    payload: ReviewIn,
    user: TokenPayload = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> AlertOut:
    action = payload.action.strip().lower()
    if action not in _REVIEW_ACTIONS:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Unsupported review action: {payload.action}")

    alert = await session.get(FraudAlert, alert_id)
    if alert is None or alert.business_id != user.business_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fraud alert not found")

    alert.status = {
        "confirm": "confirmed",
        "dismiss": "dismissed",
        "escalate": "escalated",
    }[action]
    session.add(AlertReview(
        alert_id=alert.id,
        business_id=user.business_id,
        reviewer=payload.reviewer or "owner",
        action=action,
        note=payload.note,
    ))
    await session.commit()
    await session.refresh(alert)
    return _alert_out(alert)


@router.get("/summary", response_model=FraudSummaryOut)
async def fraud_summary(
    user: TokenPayload = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> FraudSummaryOut:
    transactions = (await session.execute(
        select(FraudTransaction).where(FraudTransaction.business_id == user.business_id)
    )).scalars().all()
    alerts = (await session.execute(
        select(FraudAlert).where(FraudAlert.business_id == user.business_id)
    )).scalars().all()
    reviews = (await session.execute(
        select(AlertReview).where(AlertReview.business_id == user.business_id)
    )).scalars().all()

    alert_rows = [as_dict(row) for row in alerts]
    for row in alert_rows:
        row["created_at"] = iso(row["created_at"])
    review_rows = [as_dict(row) for row in reviews]
    for row in review_rows:
        row["created_at"] = iso(row["created_at"])

    summary = summarize_fraud([as_dict(row) for row in transactions], alert_rows, review_rows)
    return FraudSummaryOut(**summary)
