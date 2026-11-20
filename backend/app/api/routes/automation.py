from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.security import TokenPayload, get_current_user
from app.db.extensions import ExecutionLog, Notification, WebhookEvent, WorkflowConfig
from app.db.session import get_session
from app.db.util import iso
from app.engines.automation import evaluate_event
from app.models.schemas_ext import (
    AutomationStatusOut,
    ExecutionLogOut,
    NotificationOut,
    WebhookEventIn,
    WebhookEventOut,
    WorkflowIn,
    WorkflowOut,
    WorkflowUpdateIn,
)

router = APIRouter(prefix="/automation", tags=["automation"])


def _workflow_out(workflow: WorkflowConfig) -> WorkflowOut:
    return WorkflowOut(
        id=workflow.id,
        name=workflow.name,
        workflow_type=workflow.workflow_type,
        enabled=workflow.enabled,
        webhook_url=workflow.webhook_url,
        schedule=workflow.schedule,
        last_run_at=workflow.last_run_at,
        last_status=workflow.last_status,
    )


def _event_out(event: WebhookEvent) -> WebhookEventOut:
    return WebhookEventOut(
        event_id=event.event_id,
        source=event.source,
        event_type=event.event_type,
        business_id=event.business_id,
        status=event.status,
        received_at=iso(event.received_at),
    )


def _log_out(log: ExecutionLog) -> ExecutionLogOut:
    return ExecutionLogOut(
        id=log.id,
        workflow=log.workflow,
        event_id=log.event_id,
        status=log.status,
        message=log.message,
        duration_ms=log.duration_ms,
        created_at=iso(log.created_at),
    )


def _notification_out(notification: Notification) -> NotificationOut:
    return NotificationOut(
        id=notification.id,
        title=notification.title,
        message=notification.message,
        severity=notification.severity,
        channel=notification.channel,
        is_read=notification.is_read,
        created_at=iso(notification.created_at),
    )


async def _find_workflow(
    session: AsyncSession,
    business_id: str,
    event_type: str,
    workflow_name: str,
) -> WorkflowConfig | None:
    if workflow_name:
        named = (await session.execute(
            select(WorkflowConfig).where(
                WorkflowConfig.business_id == business_id,
                WorkflowConfig.name == workflow_name,
            )
        )).scalars().first()
        if named is not None:
            return named

    typed = (await session.execute(
        select(WorkflowConfig).where(
            WorkflowConfig.business_id == business_id,
            WorkflowConfig.workflow_type == event_type,
            WorkflowConfig.enabled.is_(True),
        )
    )).scalars().first()
    return typed


@router.post("/workflows", response_model=WorkflowOut)
async def create_workflow(
    payload: WorkflowIn,
    user: TokenPayload = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> WorkflowOut:
    workflow = WorkflowConfig(
        id=str(uuid.uuid4()),
        business_id=user.business_id,
        **payload.model_dump(),
    )
    session.add(workflow)
    await session.commit()
    await session.refresh(workflow)
    return _workflow_out(workflow)


@router.get("/workflows", response_model=list[WorkflowOut])
async def list_workflows(
    user: TokenPayload = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[WorkflowOut]:
    rows = (await session.execute(
        select(WorkflowConfig).where(WorkflowConfig.business_id == user.business_id)
    )).scalars().all()
    return [_workflow_out(row) for row in rows]


@router.patch("/workflows/{workflow_id}", response_model=WorkflowOut)
async def update_workflow(
    workflow_id: str,
    payload: WorkflowUpdateIn,
    user: TokenPayload = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> WorkflowOut:
    workflow = await session.get(WorkflowConfig, workflow_id)
    if workflow is None or workflow.business_id != user.business_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(workflow, field, value)
    await session.commit()
    await session.refresh(workflow)
    return _workflow_out(workflow)


@router.post("/webhooks/receive", response_model=WebhookEventOut)
async def receive_webhook(
    payload: WebhookEventIn,
    user: TokenPayload = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    x_n8n_secret: str | None = Header(default=None, alias="X-N8N-Secret"),
) -> WebhookEventOut:
    settings = get_settings()
    if settings.N8N_SHARED_SECRET and x_n8n_secret != settings.N8N_SHARED_SECRET:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid webhook secret")

    event_id = payload.event_id.strip() or str(uuid.uuid4())
    existing = await session.get(WebhookEvent, event_id)
    if existing is not None:
        return _event_out(existing)

    started = time.perf_counter()
    workflow = await _find_workflow(session, user.business_id, payload.event_type, payload.workflow)
    outcome = evaluate_event(payload.event_type, payload.payload)

    event = WebhookEvent(
        event_id=event_id,
        source="n8n",
        event_type=payload.event_type,
        business_id=user.business_id,
        payload_json=json.dumps(payload.payload),
        status="processed",
    )
    session.add(event)
    session.add(ExecutionLog(
        id=str(uuid.uuid4()),
        business_id=user.business_id,
        workflow=workflow.name if workflow else (payload.workflow or payload.event_type),
        event_id=event_id,
        status=outcome.status,
        message=outcome.message,
        duration_ms=int((time.perf_counter() - started) * 1000),
    ))
    session.add(Notification(
        id=str(uuid.uuid4()),
        business_id=user.business_id,
        title=outcome.title,
        message=outcome.notification_message,
        severity=outcome.severity,
        channel="in_app",
        is_read=False,
    ))

    if workflow is not None:
        workflow.last_run_at = datetime.now(timezone.utc).isoformat()
        workflow.last_status = outcome.status

    await session.commit()
    await session.refresh(event)
    return _event_out(event)


@router.post("/workflows/{workflow_id}/run", response_model=ExecutionLogOut)
async def run_workflow(
    workflow_id: str,
    user: TokenPayload = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ExecutionLogOut:
    workflow = await session.get(WorkflowConfig, workflow_id)
    if workflow is None or workflow.business_id != user.business_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found")

    started = time.perf_counter()
    outcome = evaluate_event(workflow.workflow_type, {"workflow": workflow.name})
    log = ExecutionLog(
        id=str(uuid.uuid4()),
        business_id=user.business_id,
        workflow=workflow.name,
        event_id="",
        status=outcome.status,
        message=outcome.message,
        duration_ms=int((time.perf_counter() - started) * 1000),
    )
    workflow.last_run_at = datetime.now(timezone.utc).isoformat()
    workflow.last_status = outcome.status
    session.add(log)
    session.add(Notification(
        id=str(uuid.uuid4()),
        business_id=user.business_id,
        title=outcome.title,
        message=outcome.notification_message,
        severity=outcome.severity,
        channel="in_app",
        is_read=False,
    ))
    await session.commit()
    await session.refresh(log)
    return _log_out(log)


@router.get("/notifications", response_model=list[NotificationOut])
async def list_notifications(
    unread_only: bool = False,
    user: TokenPayload = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[NotificationOut]:
    query = select(Notification).where(Notification.business_id == user.business_id)
    if unread_only:
        query = query.where(Notification.is_read.is_(False))
    rows = (await session.execute(query.order_by(Notification.created_at.desc()).limit(50))).scalars().all()
    return [_notification_out(row) for row in rows]


@router.post("/notifications/{notification_id}/read", response_model=NotificationOut)
async def mark_notification_read(
    notification_id: str,
    user: TokenPayload = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> NotificationOut:
    notification = await session.get(Notification, notification_id)
    if notification is None or notification.business_id != user.business_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    notification.is_read = True
    await session.commit()
    await session.refresh(notification)
    return _notification_out(notification)


@router.get("/status", response_model=AutomationStatusOut)
async def automation_status(
    user: TokenPayload = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> AutomationStatusOut:
    settings = get_settings()
    workflows = (await session.execute(
        select(WorkflowConfig).where(WorkflowConfig.business_id == user.business_id)
    )).scalars().all()
    events = (await session.execute(
        select(WebhookEvent).where(WebhookEvent.business_id == user.business_id)
        .order_by(WebhookEvent.received_at.desc()).limit(20)
    )).scalars().all()
    logs = (await session.execute(
        select(ExecutionLog).where(ExecutionLog.business_id == user.business_id)
        .order_by(ExecutionLog.created_at.desc()).limit(20)
    )).scalars().all()
    notifications = (await session.execute(
        select(Notification).where(Notification.business_id == user.business_id)
        .order_by(Notification.created_at.desc()).limit(20)
    )).scalars().all()

    return AutomationStatusOut(
        configured=bool(settings.N8N_WEBHOOK_URL and settings.N8N_SHARED_SECRET),
        workflows=[_workflow_out(row) for row in workflows],
        recent_events=[_event_out(row) for row in events],
        recent_logs=[_log_out(row) for row in logs],
        notifications=[_notification_out(row) for row in notifications],
    )
