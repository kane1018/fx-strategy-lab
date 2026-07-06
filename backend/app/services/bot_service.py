from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import BotLog, BotStatus, RiskSettings
from app.schemas.trading import RiskConfig
from app.services.gmo_live_runner_boundary import (
    GmoLiveServiceBoundarySummary,
    build_gmo_live_service_no_post_hook_summary,
)


def get_or_create_bot_status(db: Session) -> BotStatus:
    status = db.scalar(select(BotStatus).order_by(BotStatus.id).limit(1))
    if not status:
        status = BotStatus(
            mode="demo",
            status="stopped",
            manual_stop_active=True,
            stop_reason="初期状態では停止",
        )
        db.add(status)
        db.commit()
        db.refresh(status)
    return status


def bot_snapshot(db: Session) -> dict[str, Any]:
    status = get_or_create_bot_status(db)
    return {
        "id": status.id,
        "mode": status.mode,
        "status": status.status,
        "manual_stop_active": status.manual_stop_active,
        "stop_reason": status.stop_reason,
        "last_heartbeat_at": (
            status.last_heartbeat_at.isoformat() if status.last_heartbeat_at else None
        ),
    }


def _build_bot_service_live_no_post_hook_summary() -> GmoLiveServiceBoundarySummary:
    # no-POST safety summary only; intentionally fails closed by default.
    return build_gmo_live_service_no_post_hook_summary(
        invoked_from_bot_service=True,
    )


def _record_bot_log(db: Session, status: BotStatus) -> None:
    db.add(
        BotLog(
            mode=status.mode,
            status=status.status,
            reason=status.stop_reason,
        )
    )


def start_bot(db: Session, mode: str) -> dict[str, Any]:
    status = get_or_create_bot_status(db)
    if mode not in {"demo", "practice"}:
        no_post_hook_summary = _build_bot_service_live_no_post_hook_summary()
        _ = no_post_hook_summary.service_hook_wired_into_bot_service
        status.status = "risk_stopped"
        status.manual_stop_active = True
        status.stop_reason = "実資金BotはこのMVPでは起動できません"
        if not no_post_hook_summary.runner_summary.runner_may_start_gmo_live_entry:
            status.stop_reason = (
                "実資金BotはこのMVPでは起動できません（"
                "GMO live no-POST hook blocked）"
            )
    else:
        status.mode = mode
        status.status = "running"
        status.manual_stop_active = False
        status.stop_reason = None
        status.last_heartbeat_at = datetime.utcnow()
    _record_bot_log(db, status)
    db.commit()
    return bot_snapshot(db)


def stop_bot(db: Session, reason: str = "手動停止") -> dict[str, Any]:
    status = get_or_create_bot_status(db)
    status.status = "stopped"
    status.manual_stop_active = True
    status.stop_reason = reason
    _record_bot_log(db, status)
    db.commit()
    return bot_snapshot(db)


def emergency_stop_bot(db: Session, reason: str) -> None:
    status = get_or_create_bot_status(db)
    status.status = "error_stopped"
    status.manual_stop_active = True
    status.stop_reason = reason
    _record_bot_log(db, status)
    db.commit()


def risk_stop_bot(db: Session, reason: str) -> None:
    status = get_or_create_bot_status(db)
    status.status = "risk_stopped"
    status.manual_stop_active = True
    status.stop_reason = reason
    _record_bot_log(db, status)
    db.commit()


def save_risk_settings(db: Session, risk: RiskConfig) -> RiskSettings:
    settings = db.scalar(select(RiskSettings).order_by(RiskSettings.id).limit(1))
    if not settings:
        settings = RiskSettings()
        db.add(settings)
    for field, value in risk.model_dump().items():
        setattr(settings, field, value)
    db.commit()
    db.refresh(settings)
    return settings
