"""Public-only formal input for the H-11 v4 G013 canary.

The 30-minute direction is produced by the already-frozen SHORT_V1 artifact
from the latest completed M1 bar.  The v3/v4 risk-width contract is preserved:
ATR(24) means the mean true range of the latest 24 completed H1 bars.  This
module has no Private API, credential, order, or broker-write surface.
"""

from __future__ import annotations

import hashlib
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from app.h11_auto.contracts import FormalHorizon, FormalSignal, SignalDecision
from app.h11_auto.formal_signal_feed import extract_formal_signal_from_sanitized_current
from app.h11_auto.v4_activation_preparation import V4ApprovedOperatorSelections
from app.h11_manual.contracts import Horizon, map_probability
from app.h11_manual.data import (
    DEFAULT_DATA_ROOT,
    CandleRepository,
    candles_to_frame,
    load_candle_csv,
    save_candle_csv,
)
from app.h11_manual.short_model import ShortModelArtifact, predict_short_model
from app.services.h11_v4_gmo_public_preflight import (
    V4GmoG013PublicOperation,
    V4GmoG013PublicOperationLedger,
)
from app.shadow.gmo_public import GmoPublicError, GmoPublicMarketDataClient
from app.shadow.models import Candle

MAXIMUM_FORMAL_SIGNAL_AGE_SECONDS = 120.0
G013_ATR_TIMEFRAME = "H1_COMPLETED_TRUE_RANGE_MEAN_24"
G013_FORMAL_PUBLIC_GET_COUNT = 2
G013_PUBLIC_CANDLE_REQUEST_GAP_SECONDS = 0.25
G013_FORMAL_M1_WINDOW_ROWS = 31


class V4GmoFormalCanarySourceError(RuntimeError):
    """Fixed safe failure for the public-only G013 input."""


@dataclass(frozen=True, repr=False)
class V4GmoFormalCanaryInput:
    signal: FormalSignal
    frozen_atr_24: Decimal
    input_provenance_digest: str
    atr_timeframe: str = G013_ATR_TIMEFRAME
    public_candle_refresh_performed: bool = False
    public_get_count: int = G013_FORMAL_PUBLIC_GET_COUNT
    private_api_read: bool = False
    credential_read: bool = False
    broker_write: bool = False

    def __post_init__(self) -> None:
        selections = V4ApprovedOperatorSelections()
        if (
            self.signal.strategy_version != selections.strategy_version
            or self.signal.signal_config_hash != selections.signal_config_hash
            or self.signal.horizon is not FormalHorizon.MINUTES_30
            or self.signal.decision not in {SignalDecision.BUY, SignalDecision.SELL}
            or not self.frozen_atr_24.is_finite()
            or self.frozen_atr_24 <= 0
            or not self.input_provenance_digest.startswith("sha256:")
            or len(self.input_provenance_digest) != 71
            or self.atr_timeframe != G013_ATR_TIMEFRAME
            or self.public_get_count != G013_FORMAL_PUBLIC_GET_COUNT
            or self.private_api_read
            or self.credential_read
            or self.broker_write
        ):
            raise V4GmoFormalCanarySourceError("G013_FORMAL_INPUT_INVALID")

    def to_safe_dict(self) -> dict[str, object]:
        return {
            "strategy_version": self.signal.strategy_version,
            "horizon": self.signal.horizon.value,
            "direction": self.signal.decision.value,
            "probability_up": format(self.signal.probability_up, "f"),
            "observed_at_utc": self.signal.observed_at_utc.isoformat(),
            "valid_until_utc": self.signal.valid_until_utc.isoformat(),
            "atr_24": format(self.frozen_atr_24.normalize(), "f"),
            "input_provenance_digest": self.input_provenance_digest,
            "atr_timeframe": self.atr_timeframe,
            "public_candle_refresh_performed": self.public_candle_refresh_performed,
            "public_get_count": self.public_get_count,
            "private_api_read": False,
            "credential_read": False,
            "broker_write": False,
        }

    def __repr__(self) -> str:
        return "V4GmoFormalCanaryInput(<sanitized-public-only>)"

    def __bool__(self) -> bool:
        return False


def build_g013_formal_canary_input(
    *,
    m1: pd.DataFrame,
    h1: pd.DataFrame,
    artifact: ShortModelArtifact,
    now_utc: datetime,
    public_candle_refresh_performed: bool,
) -> V4GmoFormalCanaryInput:
    """Build one exact formal signal and frozen risk width from completed bars."""

    if now_utc.tzinfo is None or len(m1) < 31 or len(h1) < 25:
        raise V4GmoFormalCanarySourceError("G013_FORMAL_HISTORY_INSUFFICIENT")
    now_utc = now_utc.astimezone(UTC)
    selections = V4ApprovedOperatorSelections()
    if artifact.config_hash != selections.signal_config_hash:
        raise V4GmoFormalCanarySourceError("G013_FORMAL_ARTIFACT_MISMATCH")
    try:
        origin = _require_latest_completed_bar(
            m1,
            now_utc=now_utc,
            duration=timedelta(minutes=1),
            error_code="G013_FORMAL_M1_NOT_COMPLETED",
        )
        _require_latest_completed_bar(
            h1,
            now_utc=now_utc,
            duration=timedelta(hours=1),
            error_code="G013_FORMAL_H1_NOT_COMPLETED",
        )
        p_up = predict_short_model(
            artifact,
            m1,
            len(m1) - 1,
            Horizon.MINUTES_30,
        )
    except (KeyError, TypeError, ValueError, IndexError) as error:
        raise V4GmoFormalCanarySourceError("G013_FORMAL_SIGNAL_INVALID") from error
    age = (now_utc - origin.astimezone(UTC)).total_seconds()
    if not 0 <= age <= MAXIMUM_FORMAL_SIGNAL_AGE_SECONDS:
        raise V4GmoFormalCanarySourceError("G013_FORMAL_SIGNAL_STALE")
    direction = map_probability(p_up)
    snapshot = {
        "horizon": "30m",
        "direction": direction.value,
        "status": "OK",
        "p_up": p_up,
        "origin_time_utc": origin.astimezone(UTC).isoformat(),
        "model_config_hash": artifact.config_hash,
        "recorded_mode": "PROSPECTIVE",
    }
    try:
        signal = extract_formal_signal_from_sanitized_current(
            {"signals": [snapshot]},
            selected_horizon=FormalHorizon.MINUTES_30,
            strategy_version=selections.strategy_version,
        )
    except ValueError as error:
        raise V4GmoFormalCanarySourceError("G013_FORMAL_SIGNAL_INVALID") from error
    if signal.decision not in {SignalDecision.BUY, SignalDecision.SELL}:
        raise V4GmoFormalCanarySourceError("G013_FORMAL_SIGNAL_STAY")
    atr = _completed_h1_atr_24(h1)
    return V4GmoFormalCanaryInput(
        signal=signal,
        frozen_atr_24=atr,
        input_provenance_digest=_input_provenance_digest(
            m1=m1,
            h1=h1,
            artifact_config_hash=artifact.config_hash,
        ),
        public_candle_refresh_performed=public_candle_refresh_performed,
    )


def _require_latest_completed_bar(
    frame: pd.DataFrame,
    *,
    now_utc: datetime,
    duration: timedelta,
    error_code: str,
) -> datetime:
    """Return the latest origin only when the ordered bar is fully closed."""

    try:
        timestamps = pd.to_datetime(frame["time_utc"], utc=True, errors="raise")
    except (KeyError, TypeError, ValueError) as error:
        raise V4GmoFormalCanarySourceError(error_code) from error
    if (
        len(timestamps) == 0
        or timestamps.isna().any()
        or timestamps.duplicated().any()
        or not timestamps.is_monotonic_increasing
    ):
        raise V4GmoFormalCanarySourceError(error_code)
    latest = timestamps.iloc[-1].to_pydatetime().astimezone(UTC)
    if latest + duration > now_utc:
        raise V4GmoFormalCanarySourceError(error_code)
    return latest


def _input_provenance_digest(
    *,
    m1: pd.DataFrame,
    h1: pd.DataFrame,
    artifact_config_hash: str,
) -> str:
    """Bind the exact public bars and frozen model config without retaining data."""

    digest = hashlib.sha256()
    digest.update(artifact_config_hash.encode())
    for label, frame in (("M1", m1), ("H1", h1)):
        digest.update(label.encode())
        try:
            normalized = frame[["time_utc", "open", "high", "low", "close"]].copy()
        except KeyError as error:
            raise V4GmoFormalCanarySourceError("G013_INPUT_PROVENANCE_INVALID") from error
        normalized["time_utc"] = pd.to_datetime(
            normalized["time_utc"], utc=True, errors="raise"
        ).astype(str)
        digest.update(
            normalized.to_csv(index=False, lineterminator="\n").encode()
        )
    return "sha256:" + digest.hexdigest()


def refresh_g013_formal_canary_input(
    *,
    operation_ledger: V4GmoG013PublicOperationLedger,
    data_root: Path = DEFAULT_DATA_ROOT,
    now_utc: datetime | None = None,
    sleeper: Callable[[float], None] = time.sleep,
) -> V4GmoFormalCanaryInput:
    """Fetch current-day M1 and H1 exactly once each, then build the input."""

    operation_ledger.claim_once(V4GmoG013PublicOperation.FORMAL_CANDLES)
    current = (now_utc or datetime.now(UTC)).astimezone(UTC)
    # Derive the formal ATR(24) only from the official h1_bid.csv basis
    # (current-day fresh H1 saved below + official completed history). The
    # development/stage supplemental H1 caches are excluded here so the live
    # risk width never depends on non-official or stale historical bars.
    repository = CandleRepository(data_root, supplemental_h1_paths=())
    client = GmoPublicMarketDataClient()
    date_label = current.astimezone(ZoneInfo("Asia/Tokyo")).strftime("%Y%m%d")
    try:
        try:
            m1_candles = client.fetch_candles(
                "USD_JPY", "M1", limit=0, price_type="BID", date=date_label
            )
        except GmoPublicError as error:
            raise V4GmoFormalCanarySourceError(
                "G013_PUBLIC_M1_CANDLE_REFRESH_FAILED_NO_RETRY"
            ) from error
        sleeper(G013_PUBLIC_CANDLE_REQUEST_GAP_SECONDS)
        try:
            h1_candles = client.fetch_candles(
                "USD_JPY", "H1", limit=0, price_type="BID", date=date_label
            )
        except GmoPublicError as error:
            raise V4GmoFormalCanarySourceError(
                "G013_PUBLIC_H1_CANDLE_REFRESH_FAILED_NO_RETRY"
            ) from error
    finally:
        client.client.close()
    try:
        fresh_m1_completed, m1 = _fresh_exact_m1_window(
            candles=m1_candles,
            now_utc=current,
        )
        m1_cache = pd.concat(
            [load_candle_csv(repository.m1_path), fresh_m1_completed],
            ignore_index=True,
        )
        h1_cache = pd.concat(
            [load_candle_csv(repository.h1_path), candles_to_frame(h1_candles)],
            ignore_index=True,
        )
        m1_cache = repository._completed(m1_cache, minutes=1, now=current)
        h1_cache = repository._completed(h1_cache, minutes=60, now=current)
        save_candle_csv(repository.m1_path, m1_cache)
        save_candle_csv(repository.h1_path, h1_cache)
        artifact = ShortModelArtifact.load(data_root / "short_model_artifact.json")
        h1 = repository.load_h1(now=current)
    except (OSError, ValueError) as error:
        raise V4GmoFormalCanarySourceError("G013_FORMAL_LOCAL_INPUT_INVALID") from error
    return build_g013_formal_canary_input(
        m1=m1,
        h1=h1,
        artifact=artifact,
        now_utc=current,
        public_candle_refresh_performed=True,
    )


def _fresh_exact_m1_window(
    *, candles: list[Candle], now_utc: datetime
) -> tuple[pd.DataFrame, pd.DataFrame]:
    try:
        raw_times = pd.to_datetime(
            [candle.time for candle in candles], utc=True, errors="raise"
        )
        frame = candles_to_frame(candles)
    except (TypeError, ValueError) as error:
        raise V4GmoFormalCanarySourceError("G013_FORMAL_M1_WINDOW_INVALID") from error
    if len(frame) != len(candles) or raw_times.duplicated().any():
        raise V4GmoFormalCanarySourceError("G013_FORMAL_M1_WINDOW_INVALID")
    expected_slot = now_utc.astimezone(UTC).replace(second=0, microsecond=0) - timedelta(
        minutes=1
    )
    timestamps = pd.to_datetime(frame["time_utc"], utc=True, errors="coerce")
    completed = frame[timestamps + pd.Timedelta(minutes=1) <= now_utc].reset_index(drop=True)
    if len(completed) < G013_FORMAL_M1_WINDOW_ROWS:
        raise V4GmoFormalCanarySourceError("G013_FORMAL_HISTORY_INSUFFICIENT")
    window = completed.tail(G013_FORMAL_M1_WINDOW_ROWS).reset_index(drop=True)
    window_times = pd.to_datetime(window["time_utc"], utc=True, errors="coerce")
    if (
        window_times.isna().any()
        or window_times.duplicated().any()
        or window_times.iloc[-1].to_pydatetime().astimezone(UTC) != expected_slot
        or not bool((window_times.diff().iloc[1:] == pd.Timedelta(minutes=1)).all())
    ):
        raise V4GmoFormalCanarySourceError("G013_FORMAL_M1_WINDOW_INVALID")
    return completed, window


def _completed_h1_atr_24(frame: pd.DataFrame) -> Decimal:
    try:
        high = pd.to_numeric(frame["high"], errors="raise").to_numpy(dtype=float)
        low = pd.to_numeric(frame["low"], errors="raise").to_numpy(dtype=float)
        close = pd.to_numeric(frame["close"], errors="raise").to_numpy(dtype=float)
    except (KeyError, TypeError, ValueError) as error:
        raise V4GmoFormalCanarySourceError("G013_ATR_INPUT_INVALID") from error
    if (
        len(close) < 25
        or not np.isfinite(high[-25:]).all()
        or not np.isfinite(low[-25:]).all()
        or not np.isfinite(close[-25:]).all()
    ):
        raise V4GmoFormalCanarySourceError("G013_ATR_INPUT_INVALID")
    prior_close = close[-25:-1]
    tr = np.maximum(
        high[-24:] - low[-24:],
        np.maximum(np.abs(high[-24:] - prior_close), np.abs(low[-24:] - prior_close)),
    )
    atr_value = float(np.mean(tr))
    if not np.isfinite(atr_value) or atr_value <= 0:
        raise V4GmoFormalCanarySourceError("G013_ATR_INPUT_INVALID")
    return Decimal(str(round(atr_value, 8)))
