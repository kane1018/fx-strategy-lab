import logging
from typing import Any

from sqlalchemy.orm import Session

from app.models import ErrorLog

logger = logging.getLogger("fx_strategy_lab")


def record_error(
    db: Session,
    source: str,
    message: str,
    context: dict[str, Any] | None = None,
    severity: str = "error",
) -> None:
    logger.error("%s: %s", source, message)
    db.add(
        ErrorLog(
            source=source,
            severity=severity,
            message=message,
            context_json=context or {},
        )
    )
    db.commit()
