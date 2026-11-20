from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import httpx
import structlog
from fastapi import APIRouter, Depends, Header, HTTPException, status

from app.config import Settings, get_settings
from app.db.tenant import demo_business_id
from app.core.security import TokenPayload, get_current_user
from app.engines.budget_variance import BudgetVarianceEngine
from app.engines.risk_detection import RiskDetectionEngine, RiskInputs
from app.models.schemas import AlertItem, AlertWebhookPayload, TriggerAlertCheckResponse

logger = structlog.get_logger("finsight.alerts")

router = APIRouter(prefix="/alerts", tags=["alerts"])

# In-memory alert store indexed by business_id
# In production, this maps to a `notifications` / `alerts` table in Supabase Postgres.
_ALERT_STORE: dict[str, list[dict[str, Any]]] = {}


def _get_business_alerts(business_id: str) -> list[dict[str, Any]]:
    if business_id not in _ALERT_STORE:
        # Seed initial automated alert messages from n8n & engines
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        _ALERT_STORE[business_id] = [
            {
                "id": str(uuid.uuid4()),
                "business_id": business_id,
                "title": "Budget Breach Detected: Marketing & Growth",
                "message": "Q3 Marketing actual spend (₹85,000) exceeded allocated budget (₹70,000) by +21.4% (₹15,000 variance). Immediate re-allocation review recommended.",
                "severity": "critical",
                "source": "n8n_automation",
                "timestamp": now_str,
                "read": False,
            },
            {
                "id": str(uuid.uuid4()),
                "business_id": business_id,
                "title": "Scheduled Risk Monitor: Liquidity Runway",
                "message": "Automated morning liquidity screen completed: Cash runway is 7.0 months. Working capital ratio is healthy at 2.35x.",
                "severity": "watch",
                "source": "n8n_automation",
                "timestamp": now_str,
                "read": False,
            },
            {
                "id": str(uuid.uuid4()),
                "business_id": business_id,
                "title": "Document RAG Indexing Verified",
                "message": "Multi-sheet financial model 'business_financial_model.xlsx' processed into 3 semantic chunks and available for advisor analysis.",
                "severity": "info",
                "source": "n8n_automation",
                "timestamp": now_str,
                "read": True,
            },
        ]
    return _ALERT_STORE[business_id]


@router.get("", response_model=list[AlertItem])
def list_alerts(
    user: TokenPayload = Depends(get_current_user),
) -> list[AlertItem]:
    """Returns active in-app alert messages for the authenticated business."""
    alerts = _get_business_alerts(user.business_id)
    return [AlertItem(**a) for a in alerts]


@router.post("/webhook", response_model=AlertItem)
def receive_n8n_webhook(
    payload: AlertWebhookPayload,
    x_n8n_secret: str | None = Header(None, alias="X-N8N-Secret"),
    settings: Settings = Depends(get_settings),
) -> AlertItem:
    """Webhook endpoint called by n8n Cloud / local n8n to deliver alert messages.

    Authenticated via the `X-N8N-Secret` header matching N8N_SHARED_SECRET.
    """
    if settings.N8N_SHARED_SECRET and x_n8n_secret != settings.N8N_SHARED_SECRET:
        # If secret is set, enforce validation
        logger.warning("n8n_webhook_unauthorized", provided_secret=bool(x_n8n_secret))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-N8N-Secret header",
        )

    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    new_alert = {
        "id": str(uuid.uuid4()),
        "business_id": payload.business_id,
        "title": payload.title,
        "message": payload.message,
        "severity": payload.severity,
        "source": payload.source,
        "timestamp": now_str,
        "read": False,
    }

    alerts = _get_business_alerts(payload.business_id)
    alerts.insert(0, new_alert)
    logger.info("n8n_alert_received", title=payload.title, severity=payload.severity)
    return AlertItem(**new_alert)


def push_alert(
    business_id: str,
    title: str,
    message: str,
    *,
    severity: str = "watch",
    source: str = "risk_engine",
) -> dict[str, Any]:
    """Insert an alert into the in-app stream and return it."""
    alerts = _get_business_alerts(business_id)
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    alert = {
        "id": str(uuid.uuid4()),
        "business_id": business_id,
        "title": title,
        "message": message,
        "severity": severity,
        "source": source,
        "timestamp": now_str,
        "read": False,
    }
    alerts.insert(0, alert)
    logger.info("alert_pushed", title=title, severity=severity, source=source)
    return alert


async def dispatch_alert_to_n8n(alert: dict[str, Any], settings: Settings) -> bool:
    """Forward one alert to the n8n webhook, if one is configured."""
    if not settings.N8N_WEBHOOK_URL:
        return False
    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            await client.post(
                settings.N8N_WEBHOOK_URL,
                json={
                    "business_id": alert["business_id"],
                    "title": alert["title"],
                    "message": alert["message"],
                    "severity": alert["severity"],
                    "source": alert["source"],
                },
                headers={"X-N8N-Secret": settings.N8N_SHARED_SECRET},
            )
        return True
    except Exception as exc:
        logger.debug("n8n_webhook_offline", error=str(exc))
        return False


async def evaluate_and_dispatch_alerts(
    business_id: str | None = None,
    settings: Settings | None = None,
    *,
    force_dispatch: bool = False,
) -> list[dict[str, Any]]:
    """Core evaluation engine that performs the scheduled automated budget & risk

    monitoring check matching the n8n cron schedule.
    """
    business_id = business_id or demo_business_id()
    alerts = _get_business_alerts(business_id)
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    generated_alerts: list[dict[str, Any]] = []

    # 1. Evaluate Budget Variance Engine
    budget_engine = BudgetVarianceEngine(watch_threshold_pct=5.0, breach_threshold_pct=10.0)
    sample_budget = {
        "marketing": 70000.0,
        "engineering": 125000.0,
        "operations": 45000.0,
        "legal": 15000.0,
        "facilities": 20000.0,
    }
    sample_actual = {
        "marketing": 85000.0,
        "engineering": 120000.0,
        "operations": 44200.0,
        "legal": 15000.0,
        "facilities": 21500.0,
    }
    budget_report = budget_engine.evaluate(
        period="2026-Q3",
        budget=sample_budget,
        actual=sample_actual,
    )

    for breach in budget_report.breaches():
        alert_title = f"🚨 Automated Alert: Budget Breach in {breach.category.capitalize()}"
        # Avoid duplicate alerts if the same breach is already in the stream
        if not any(a["title"] == alert_title for a in alerts):
            alert = {
                "id": str(uuid.uuid4()),
                "business_id": business_id,
                "title": alert_title,
                "message": f"{breach.category.capitalize()} variance reached {breach.variance_pct:+.1f}% (₹{breach.variance_abs:,.0f} variance). Breach threshold is 10.0%.",
                "severity": "critical",
                "source": "n8n_automation",
                "timestamp": now_str,
                "read": False,
            }
            alerts.insert(0, alert)
            generated_alerts.append(alert)

    # 2. Evaluate Risk Engine
    risk_engine = RiskDetectionEngine()
    risk_report = risk_engine.evaluate(
        RiskInputs(
            current_ratio=2.35,
            debt_to_equity=0.54,
            net_margin_pct=18.7,
            cash_runway_months=7.0,
            revenue_mom_change_pct=2.5,
        )
    )

    for flag in risk_report.flags:
        if flag.level.value in ("watch", "high", "critical"):
            alert_title = f"⚠️ Automated Alert: {flag.code.replace('_', ' ').title()}"
            if not any(a["title"] == alert_title for a in alerts):
                alert = {
                    "id": str(uuid.uuid4()),
                    "business_id": business_id,
                    "title": alert_title,
                    "message": flag.message,
                    "severity": flag.level.value,
                    "source": "n8n_automation",
                    "timestamp": now_str,
                    "read": False,
                }
                alerts.insert(0, alert)
                generated_alerts.append(alert)

    # 3. Dispatch Webhook to external n8n if configured — only when this run
    # produced something new, so the scheduled monitor doesn't re-notify
    # subscribers every cycle about alerts they already received. An explicit
    # manual check (force_dispatch) always round-trips to n8n so the
    # automation can be exercised on demand.
    if settings and settings.N8N_WEBHOOK_URL and (generated_alerts or force_dispatch):
        try:
            async with httpx.AsyncClient(timeout=4.0) as client:
                await client.post(
                    settings.N8N_WEBHOOK_URL,
                    json={
                        "event": "automated_financial_check",
                        "business_id": business_id,
                        "alerts_count": len(generated_alerts),
                        "breaches_count": len(budget_report.breaches()),
                        "overall_risk": risk_report.overall_level.value,
                    },
                    headers={"X-N8N-Secret": settings.N8N_SHARED_SECRET},
                )
        except Exception as exc:
            logger.debug("n8n_webhook_offline", error=str(exc))

    return generated_alerts


@router.post("/trigger-check", response_model=TriggerAlertCheckResponse)
async def trigger_automated_alert_check(
    user: TokenPayload = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> TriggerAlertCheckResponse:
    """Manually triggers an automated financial monitoring check (simulating the

    n8n daily schedule): evaluates budget variance and risk thresholds, logs new
    alert messages, and forwards them to n8n if N8N_WEBHOOK_URL is configured.
    """
    business_id = user.business_id
    generated = await evaluate_and_dispatch_alerts(
        business_id, settings, force_dispatch=True
    )
    alerts = _get_business_alerts(business_id)
    return TriggerAlertCheckResponse(
        status="success",
        alerts_generated=len(generated),
        n8n_webhook_dispatched=bool(settings.N8N_WEBHOOK_URL),
        alerts=[AlertItem(**a) for a in alerts],
    )


@router.post("/{alert_id}/read", response_model=AlertItem)
def mark_alert_read(
    alert_id: str,
    user: TokenPayload = Depends(get_current_user),
) -> AlertItem:
    alerts = _get_business_alerts(user.business_id)
    for a in alerts:
        if a["id"] == alert_id:
            a["read"] = True
            return AlertItem(**a)
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")


@router.delete("/{alert_id}")
def dismiss_alert(
    alert_id: str,
    user: TokenPayload = Depends(get_current_user),
) -> dict[str, str]:
    alerts = _get_business_alerts(user.business_id)
    initial_len = len(alerts)
    alerts[:] = [a for a in alerts if a["id"] != alert_id]
    if len(alerts) == initial_len:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
    return {"status": "dismissed", "alert_id": alert_id}
