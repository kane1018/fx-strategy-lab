"""Public-only formal-aware G013 observer.

This observer remains non-authorizing.  It first consumes the existing exact
M1 preview slot.  Only an actionable M1 candidate causes one additional fresh
H1 Public GET, used solely to prove that the frozen ATR(24) input is available.
It never writes candle caches, imports the actual canary, or exposes a trading
direction, price, probability, order sheet, or confirmation challenge.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from app.h11_manual.data import DEFAULT_DATA_ROOT, CandleRepository, candles_to_frame, load_candle_csv
from app.services.h11_v4_gmo_formal_canary_source import (
    G013_PUBLIC_CANDLE_REQUEST_GAP_SECONDS,
    V4GmoFormalCanarySourceError,
    _completed_h1_atr_24,
    _require_latest_completed_bar,
)
from app.services.h11_v4_gmo_signal_preview import run_g013_signal_preview
from app.shadow.gmo_public import GmoPublicError, GmoPublicMarketDataClient


class G013FormalAwarePreviewError(RuntimeError):
    """Fixed safe failure for the public-only formal-aware observer."""


@dataclass(frozen=True, repr=False)
class G013FormalAwarePreviewReport:
    status: str
    candidate_actionable: bool
    formal_candidate_actionable: bool
    public_get_count: int
    broker_post_count: int = 0
    private_api_read: bool = False
    credential_read: bool = False
    broker_write: bool = False
    permit_issued: bool = False
    actual_generation_consumed: bool = False
    direction_exposed: bool = False
    probability_exposed: bool = False
    price_exposed: bool = False
    raw_market_data_exposed: bool = False
    order_sheet_exposed: bool = False
    challenge_exposed: bool = False

    def to_safe_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "candidate_actionable": self.candidate_actionable,
            "formal_candidate_actionable": self.formal_candidate_actionable,
            "public_get_count": self.public_get_count,
            "broker_post_count": self.broker_post_count,
            "private_api_read": False,
            "credential_read": False,
            "broker_write": False,
            "permit_issued": False,
            "actual_generation_consumed": False,
            "direction_exposed": False,
            "probability_exposed": False,
            "price_exposed": False,
            "raw_market_data_exposed": False,
            "order_sheet_exposed": False,
            "challenge_exposed": False,
        }

    def __repr__(self) -> str:
        return "G013FormalAwarePreviewReport(<sanitized-public-only>)"


def run_g013_formal_aware_preview(
    *,
    repository: Path,
    now_utc: datetime | None = None,
    sleeper: Callable[[float], None] = time.sleep,
) -> G013FormalAwarePreviewReport:
    """Observe one completed M1 slot and conditionally validate fresh H1 risk input."""

    current = (now_utc or datetime.now(UTC)).astimezone(UTC)
    preview = run_g013_signal_preview(repository=repository, now_utc=current)
    if not preview.candidate_actionable:
        return G013FormalAwarePreviewReport(
            status="G013_FORMAL_AWARE_PREVIEW_NON_ACTIONABLE",
            candidate_actionable=False,
            formal_candidate_actionable=False,
            public_get_count=1,
        )

    _validate_fresh_completed_h1(now_utc=current, sleeper=sleeper)
    return G013FormalAwarePreviewReport(
        status="G013_FORMAL_AWARE_PREVIEW_FORMAL_ACTIONABLE",
        candidate_actionable=True,
        formal_candidate_actionable=True,
        public_get_count=2,
    )


def _validate_fresh_completed_h1(*, now_utc: datetime, sleeper: Callable[[float], None]) -> None:
    """Read one current-day H1 response and validate the formal ATR basis in memory."""

    client = GmoPublicMarketDataClient()
    date_label = now_utc.astimezone(ZoneInfo("Asia/Tokyo")).strftime("%Y%m%d")
    try:
        sleeper(G013_PUBLIC_CANDLE_REQUEST_GAP_SECONDS)
        candles = client.fetch_candles(
            "USD_JPY", "H1", limit=0, price_type="BID", date=date_label
        )
    except GmoPublicError as error:
        raise G013FormalAwarePreviewError(
            "G013_FORMAL_AWARE_H1_REFRESH_FAILED_NO_RETRY"
        ) from error
    finally:
        client.client.close()
    try:
        repository = CandleRepository(DEFAULT_DATA_ROOT, supplemental_h1_paths=())
        merged = pd.concat(
            [load_candle_csv(repository.h1_path), candles_to_frame(candles)],
            ignore_index=True,
        )
        merged["time_utc"] = pd.to_datetime(merged["time_utc"], utc=True, errors="raise")
        merged = (
            merged.sort_values("time_utc")
            .drop_duplicates("time_utc", keep="last")
            .reset_index(drop=True)
        )
        merged["time_utc"] = merged["time_utc"].map(lambda value: value.isoformat())
        h1 = repository._completed(merged, minutes=60, now=now_utc)
        _require_latest_completed_bar(
            h1,
            now_utc=now_utc,
            duration=timedelta(hours=1),
            error_code="G013_FORMAL_AWARE_H1_NOT_COMPLETED",
        )
        _completed_h1_atr_24(h1)
    except (OSError, ValueError, V4GmoFormalCanarySourceError) as error:
        raise G013FormalAwarePreviewError("G013_FORMAL_AWARE_H1_INPUT_INVALID") from error
