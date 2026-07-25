"""Public-only finite input adapter for the H-11 v4 unattended shadow controller.

This adapter is the network layer that the pure
``v4_unattended_shadow_controller`` deliberately excludes.  It performs a fixed,
finite set of GMO **Public** GETs (status, ticker, M1, H1), reuses the already
frozen SHORT_V1 / 30-minute inference and the H1 ATR(24) risk width, and hands
the controller one exact typed ``FormalSignal`` and one
``V4UnattendedShadowSnapshot``.

Structural boundary (enforced by the accompanying no-POST test):

* Public read-only market data only (klines / ticker / status).
* No Private API, credential, Keychain, broker order/cancel/close/OCO write,
  hard guard, permit, notification, scheduler, or resident process.

The broker-derived preflight dimensions (account flat, active orders, boot
reconciliation, fresh broker snapshot) cannot be observed without a Private GET,
so this Public-only phase reports them fail-closed.  A Public-only cycle
therefore never becomes ``SHADOW_WOULD_ENTER_NON_AUTHORIZING``; that decision is
reserved for the separately reviewed full-operational (Private GET) phase.  A
shadow observation is not an authorization, permit, or performance proof.
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import ROUND_CEILING, Decimal, InvalidOperation
from pathlib import Path
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from app.h11_auto.contracts import (
    FormalHorizon,
    FormalSignal,
    H11AutoContractError,
    SignalDecision,
)
from app.h11_auto.formal_signal_feed import (
    extract_formal_signal_from_sanitized_current,
)
from app.h11_auto.v4_gmo_contracts import V4GmoPreflightSnapshot
from app.h11_auto.v4_gmo_protection import H11_V4_GMO_PROTECTION_SPEC
from app.h11_auto.v4_unattended_shadow_controller import (
    V4_UNATTENDED_SHADOW_SIGNAL_CONFIG_HASH,
    V4_UNATTENDED_SHADOW_SYMBOL,
    V4UnattendedShadowSnapshot,
)
from app.h11_manual.contracts import Horizon, map_probability
from app.h11_manual.data import candles_to_frame
from app.h11_manual.short_model import predict_short_model
from app.shadow.gmo_public import GmoPublicError, GmoPublicMarketDataClient
from app.shadow.models import Candle, Ticker

if TYPE_CHECKING:
    from app.h11_manual.short_model import ShortModelArtifact

V4_UNATTENDED_SHADOW_PUBLIC_SCHEMA = "H11_V4_UNATTENDED_SHADOW_PUBLIC_ADAPTER_V1"
V4_UNATTENDED_SHADOW_STRATEGY_VERSION = "SHORT_V1"
# Match the frozen formal-canary source: the 30-minute direction stays fresh for
# up to five minutes (one sixth of the horizon) after the latest completed bar.
V4_UNATTENDED_SHADOW_MAXIMUM_SIGNAL_AGE_SECONDS = Decimal("300")
# A quote up to five seconds behind the local clock is clock skew, not a stale
# quote; the upper bound mirrors the controller's frozen quote-age window.
V4_UNATTENDED_SHADOW_QUOTE_SKEW_SECONDS = Decimal("5")
V4_UNATTENDED_SHADOW_QUOTE_STALE_SECONDS = Decimal("5")
V4_UNATTENDED_SHADOW_PIP_SIZE = Decimal("0.01")
V4_UNATTENDED_SHADOW_M1_WINDOW_ROWS = 31
V4_UNATTENDED_SHADOW_H1_MINIMUM_ROWS = 25
V4_UNATTENDED_SHADOW_PUBLIC_GET_GAP_SECONDS = 0.25
V4_UNATTENDED_SHADOW_PUBLIC_GET_COUNT = 5

_JST = ZoneInfo("Asia/Tokyo")
_SHADOW_EXPORT_ROOT = Path(__file__).resolve().parents[2] / "shadow_exports"


class V4UnattendedShadowPublicError(RuntimeError):
    """Fixed safe Public-shadow adapter failure; messages carry safe labels only."""


@dataclass(frozen=True, repr=False)
class V4UnattendedShadowObservation:
    """One Public-only observation handed to the pure controller.

    ``signal`` and ``snapshot`` are consumed in-process by the controller; this
    object is never serialized and never exposes direction, probability, price,
    or any raw candle.
    """

    signal: FormalSignal
    snapshot: V4UnattendedShadowSnapshot
    completed_slot_utc: datetime
    public_get_count: int = V4_UNATTENDED_SHADOW_PUBLIC_GET_COUNT
    private_api_read: bool = False
    credential_read: bool = False
    broker_read_performed: bool = False
    broker_write_performed: bool = False

    def __post_init__(self) -> None:
        if (
            type(self.signal) is not FormalSignal
            or type(self.snapshot) is not V4UnattendedShadowSnapshot
            or self.completed_slot_utc.tzinfo is None
            or self.public_get_count != V4_UNATTENDED_SHADOW_PUBLIC_GET_COUNT
            or self.private_api_read
            or self.credential_read
            or self.broker_read_performed
            or self.broker_write_performed
        ):
            raise V4UnattendedShadowPublicError("SHADOW_PUBLIC_OBSERVATION_INVALID")

    def __repr__(self) -> str:
        return "V4UnattendedShadowObservation(<sanitized-public-only>)"

    def __bool__(self) -> bool:
        return False


def observe_public_shadow_cycle(
    *,
    slot_state_root: Path,
    artifact: ShortModelArtifact,
    now_utc: datetime,
    client_factory: Callable[[], GmoPublicMarketDataClient] = GmoPublicMarketDataClient,
    sleeper: Callable[[float], None] = time.sleep,
) -> V4UnattendedShadowObservation:
    """Perform one finite Public-only observation for a single completed M1 slot.

    The same completed slot is claimed once under ``backend/shadow_exports`` and
    never retried.  Any network, schema, freshness, or history failure is
    fail-closed with a fixed safe label.  No broker, credential, or private
    surface is touched.
    """

    if now_utc.tzinfo is None:
        raise V4UnattendedShadowPublicError("SHADOW_PUBLIC_CLOCK_INVALID")
    # Duck-typed acceptance mirrors build_g013_formal_canary_input: a matching
    # frozen config hash is required and predict_short_model rejects a
    # non-functional artifact at runtime with SHADOW_PUBLIC_SIGNAL_INVALID.
    if getattr(artifact, "config_hash", None) != V4_UNATTENDED_SHADOW_SIGNAL_CONFIG_HASH:
        raise V4UnattendedShadowPublicError("SHADOW_PUBLIC_ARTIFACT_MISMATCH")
    current = now_utc.astimezone(UTC)
    expected_slot = current.replace(second=0, microsecond=0) - timedelta(minutes=1)
    _claim_slot(slot_state_root=slot_state_root, slot_utc=expected_slot)

    status_text, ticker, m1_candles, h1_candles = _fetch_public_inputs(
        current=current,
        client_factory=client_factory,
        sleeper=sleeper,
    )

    market_open = status_text == "OPEN"
    quote_age_seconds, quote_fresh = _quote_age(ticker=ticker, now_utc=current)
    spread_pips = _spread_pips(ticker=ticker)

    m1_window = _completed_m1_window(candles=m1_candles, expected_slot=expected_slot)
    h1_completed = _completed_h1_frame(candles=h1_candles, now_utc=current)
    signal, frozen_atr_24 = _build_signal_and_atr(
        m1_window=m1_window,
        h1_completed=h1_completed,
        artifact=artifact,
        now_utc=current,
    )
    planned_loss_bound_jpy = _planned_loss_bound_jpy(frozen_atr_24=frozen_atr_24)

    snapshot = V4UnattendedShadowSnapshot(
        preflight=_fail_closed_preflight(
            data_fresh=quote_fresh, clock_synchronized=quote_fresh
        ),
        market_open=market_open,
        quote_age_seconds=quote_age_seconds,
        spread_pips=spread_pips,
        # A single Public observation has no prior reference quote to drift from.
        reference_deviation_pips=Decimal("0"),
        frozen_atr_24=frozen_atr_24,
        planned_loss_bound_jpy=planned_loss_bound_jpy,
    )
    return V4UnattendedShadowObservation(
        signal=signal,
        snapshot=snapshot,
        completed_slot_utc=expected_slot,
    )


def _fail_closed_preflight(
    *, data_fresh: bool, clock_synchronized: bool
) -> V4GmoPreflightSnapshot:
    """Broker/account/notification dimensions are unobservable without Private GET.

    Every broker-derived dimension is reported fail-closed so a Public-only cycle
    can never reach an actionable ``SHADOW_WOULD_ENTER`` decision. Rather than
    leave the account counts at their zero default — which would silently read as
    a flat/clear account that AGENTS.md forbids inferring from Public data — they
    are set to a non-zero unobserved sentinel so the block reasons explicitly name
    ``POSITION_NOT_FLAT``, ``ACTIVE_ORDER_EXISTS``, and ``DAILY_ENTRY_LIMIT_REACHED``.
    """

    return V4GmoPreflightSnapshot(
        boot_reconciled=False,
        process_lock_held=True,
        data_fresh=data_fresh,
        clock_synchronized=clock_synchronized,
        notification_path_ready=False,
        broker_snapshot_fresh=False,
        position_count=1,
        active_order_count=1,
        entries_today=1,
    )


def _fetch_public_inputs(
    *,
    current: datetime,
    client_factory: Callable[[], GmoPublicMarketDataClient],
    sleeper: Callable[[float], None],
) -> tuple[str, Ticker, list[Candle], list[Candle]]:
    """Fetch status, ticker, today M1, and yesterday+today H1 exactly once each."""

    today = current.astimezone(_JST).strftime("%Y%m%d")
    yesterday = (current.astimezone(_JST) - timedelta(days=1)).strftime("%Y%m%d")
    client: GmoPublicMarketDataClient | None = None
    failed = False
    result: tuple[str, Ticker, list[Candle], list[Candle]] | None = None
    try:
        client = client_factory()
        status_text = client.service_status()
        sleeper(V4_UNATTENDED_SHADOW_PUBLIC_GET_GAP_SECONDS)
        ticker = client.fetch_ticker(V4_UNATTENDED_SHADOW_SYMBOL)
        sleeper(V4_UNATTENDED_SHADOW_PUBLIC_GET_GAP_SECONDS)
        m1_candles = client.fetch_candles(
            V4_UNATTENDED_SHADOW_SYMBOL, "M1", 0, price_type="BID", date=today
        )
        sleeper(V4_UNATTENDED_SHADOW_PUBLIC_GET_GAP_SECONDS)
        h1_prev = client.fetch_candles(
            V4_UNATTENDED_SHADOW_SYMBOL, "H1", 0, price_type="BID", date=yesterday
        )
        sleeper(V4_UNATTENDED_SHADOW_PUBLIC_GET_GAP_SECONDS)
        h1_today = client.fetch_candles(
            V4_UNATTENDED_SHADOW_SYMBOL, "H1", 0, price_type="BID", date=today
        )
        result = (str(status_text), ticker, m1_candles, [*h1_prev, *h1_today])
    except (GmoPublicError, KeyError, TypeError, ValueError):
        failed = True
    finally:
        if client is not None:
            try:
                client.client.close()
            except Exception:
                pass
    if failed or result is None:
        raise V4UnattendedShadowPublicError("SHADOW_PUBLIC_GET_FAILED_NO_RETRY")
    return result


def _quote_age(*, ticker: Ticker, now_utc: datetime) -> tuple[Decimal, bool]:
    try:
        observed = datetime.fromisoformat(str(ticker.time).replace("Z", "+00:00"))
    except ValueError as error:
        raise V4UnattendedShadowPublicError("SHADOW_PUBLIC_TICKER_TIME_INVALID") from error
    if observed.tzinfo is None:
        raise V4UnattendedShadowPublicError("SHADOW_PUBLIC_TICKER_TIME_INVALID")
    age_seconds = (now_utc - observed.astimezone(UTC)).total_seconds()
    age = Decimal(str(age_seconds))
    fresh = (
        -V4_UNATTENDED_SHADOW_QUOTE_SKEW_SECONDS
        <= age
        <= V4_UNATTENDED_SHADOW_QUOTE_STALE_SECONDS
    )
    return age, bool(fresh)


def _spread_pips(*, ticker: Ticker) -> Decimal:
    try:
        bid = Decimal(str(ticker.bid))
        ask = Decimal(str(ticker.ask))
    except (InvalidOperation, TypeError) as error:
        raise V4UnattendedShadowPublicError("SHADOW_PUBLIC_TICKER_PRICE_INVALID") from error
    if not bid.is_finite() or not ask.is_finite() or bid <= 0 or ask < bid:
        raise V4UnattendedShadowPublicError("SHADOW_PUBLIC_TICKER_PRICE_INVALID")
    return (ask - bid) / V4_UNATTENDED_SHADOW_PIP_SIZE


def _completed_m1_window(*, candles: list[Candle], expected_slot: datetime) -> pd.DataFrame:
    """Return exactly the 31 completed one-minute bars ending at ``expected_slot``."""

    frame = _candle_frame(candles=candles, error="SHADOW_PUBLIC_M1_DATA_INVALID")
    completed = frame[frame["time_utc"] <= expected_slot].reset_index(drop=True)
    if len(completed) < V4_UNATTENDED_SHADOW_M1_WINDOW_ROWS:
        raise V4UnattendedShadowPublicError("SHADOW_PUBLIC_M1_HISTORY_INSUFFICIENT")
    window = completed.tail(V4_UNATTENDED_SHADOW_M1_WINDOW_ROWS).reset_index(drop=True)
    times = window["time_utc"]
    if (
        times.iloc[-1].to_pydatetime().astimezone(UTC) != expected_slot
        or not bool((times.diff().iloc[1:] == pd.Timedelta(minutes=1)).all())
    ):
        raise V4UnattendedShadowPublicError("SHADOW_PUBLIC_M1_WINDOW_INVALID")
    return window


def _completed_h1_frame(*, candles: list[Candle], now_utc: datetime) -> pd.DataFrame:
    """Return the completed H1 bars (>=25) used only for the frozen ATR(24)."""

    frame = _candle_frame(candles=candles, error="SHADOW_PUBLIC_H1_DATA_INVALID")
    completed = frame[
        frame["time_utc"] + pd.Timedelta(hours=1) <= now_utc
    ].reset_index(drop=True)
    if len(completed) < V4_UNATTENDED_SHADOW_H1_MINIMUM_ROWS:
        raise V4UnattendedShadowPublicError("SHADOW_PUBLIC_H1_HISTORY_INSUFFICIENT")
    return completed


def _candle_frame(*, candles: list[Candle], error: str) -> pd.DataFrame:
    try:
        frame = candles_to_frame(candles)
        frame = frame.loc[:, ["time_utc", "open", "high", "low", "close"]].copy()
        frame["time_utc"] = pd.to_datetime(frame["time_utc"], utc=True, errors="raise")
    except (KeyError, TypeError, ValueError) as source_error:
        raise V4UnattendedShadowPublicError(error) from source_error
    if (
        frame.empty
        or frame["time_utc"].isna().any()
        or frame["time_utc"].duplicated().any()
    ):
        raise V4UnattendedShadowPublicError(error)
    return frame.sort_values("time_utc").reset_index(drop=True)


def _build_signal_and_atr(
    *,
    m1_window: pd.DataFrame,
    h1_completed: pd.DataFrame,
    artifact: ShortModelArtifact,
    now_utc: datetime,
) -> tuple[FormalSignal, Decimal]:
    """Reuse the frozen SHORT_V1 30m inference and H1 ATR(24) without rejecting STAY.

    A cross-check test asserts this produces the identical BUY/SELL signal and
    ATR as the actual-canary ``build_g013_formal_canary_input`` builder.
    """

    origin = _require_latest_completed_bar(
        m1_window, now_utc=now_utc, duration=timedelta(minutes=1),
        error="SHADOW_PUBLIC_M1_NOT_COMPLETED",
    )
    _require_latest_completed_bar(
        h1_completed, now_utc=now_utc, duration=timedelta(hours=1),
        error="SHADOW_PUBLIC_H1_NOT_COMPLETED",
    )
    try:
        p_up = predict_short_model(
            artifact, m1_window, len(m1_window) - 1, Horizon.MINUTES_30
        )
    except (KeyError, TypeError, ValueError, IndexError) as error:
        raise V4UnattendedShadowPublicError("SHADOW_PUBLIC_SIGNAL_INVALID") from error
    age = (now_utc - origin).total_seconds()
    if not Decimal("0") <= Decimal(str(age)) <= V4_UNATTENDED_SHADOW_MAXIMUM_SIGNAL_AGE_SECONDS:
        raise V4UnattendedShadowPublicError("SHADOW_PUBLIC_SIGNAL_STALE")
    direction = map_probability(p_up)
    snapshot = {
        "horizon": FormalHorizon.MINUTES_30.value,
        "direction": direction.value,
        "status": "OK",
        "p_up": p_up,
        "origin_time_utc": origin.isoformat(),
        "model_config_hash": artifact.config_hash,
        "recorded_mode": "PROSPECTIVE",
    }
    try:
        signal = extract_formal_signal_from_sanitized_current(
            {"signals": [snapshot]},
            selected_horizon=FormalHorizon.MINUTES_30,
            strategy_version=V4_UNATTENDED_SHADOW_STRATEGY_VERSION,
        )
    except H11AutoContractError as error:
        raise V4UnattendedShadowPublicError("SHADOW_PUBLIC_SIGNAL_INVALID") from error
    if signal.decision not in (
        SignalDecision.BUY,
        SignalDecision.SELL,
        SignalDecision.STAY,
    ):
        raise V4UnattendedShadowPublicError("SHADOW_PUBLIC_SIGNAL_INVALID")
    return signal, _completed_h1_atr_24(h1_completed)


def _require_latest_completed_bar(
    frame: pd.DataFrame,
    *,
    now_utc: datetime,
    duration: timedelta,
    error: str,
) -> datetime:
    try:
        timestamps = pd.to_datetime(frame["time_utc"], utc=True, errors="raise")
    except (KeyError, TypeError, ValueError) as source_error:
        raise V4UnattendedShadowPublicError(error) from source_error
    if (
        len(timestamps) == 0
        or timestamps.isna().any()
        or timestamps.duplicated().any()
        or not timestamps.is_monotonic_increasing
    ):
        raise V4UnattendedShadowPublicError(error)
    latest = timestamps.iloc[-1].to_pydatetime().astimezone(UTC)
    if latest + duration > now_utc:
        raise V4UnattendedShadowPublicError(error)
    return latest


def _completed_h1_atr_24(frame: pd.DataFrame) -> Decimal:
    """Mean true range of the latest 24 completed H1 bars (frozen risk width)."""

    try:
        high = pd.to_numeric(frame["high"], errors="raise").to_numpy(dtype=float)
        low = pd.to_numeric(frame["low"], errors="raise").to_numpy(dtype=float)
        close = pd.to_numeric(frame["close"], errors="raise").to_numpy(dtype=float)
    except (KeyError, TypeError, ValueError) as error:
        raise V4UnattendedShadowPublicError("SHADOW_PUBLIC_ATR_INPUT_INVALID") from error
    if (
        len(close) < 25
        or not np.isfinite(high[-25:]).all()
        or not np.isfinite(low[-25:]).all()
        or not np.isfinite(close[-25:]).all()
    ):
        raise V4UnattendedShadowPublicError("SHADOW_PUBLIC_ATR_INPUT_INVALID")
    prior_close = close[-25:-1]
    tr = np.maximum(
        high[-24:] - low[-24:],
        np.maximum(np.abs(high[-24:] - prior_close), np.abs(low[-24:] - prior_close)),
    )
    atr_value = float(np.mean(tr))
    if not np.isfinite(atr_value) or atr_value <= 0:
        raise V4UnattendedShadowPublicError("SHADOW_PUBLIC_ATR_INPUT_INVALID")
    return Decimal(str(round(atr_value, 8)))


def _planned_loss_bound_jpy(*, frozen_atr_24: Decimal) -> int:
    """Planned per-trade loss = stop distance (ATR x frozen multiplier) x size.

    Fail-closed: the controller blocks with ``PLANNED_LOSS_LIMIT_EXCEEDED`` when
    this exceeds the frozen per-trade cap, so no artificial clamp is applied.
    """

    multiplier = Decimal(H11_V4_GMO_PROTECTION_SPEC["stop_loss_atr_multiplier"])
    size = Decimal(H11_V4_GMO_PROTECTION_SPEC["max_intended_size"])
    planned = (frozen_atr_24 * multiplier * size).to_integral_value(rounding=ROUND_CEILING)
    value = int(planned)
    if value <= 0:
        raise V4UnattendedShadowPublicError("SHADOW_PUBLIC_PLANNED_LOSS_INVALID")
    return value


def _claim_slot(*, slot_state_root: Path, slot_utc: datetime) -> None:
    """Claim one completed slot once, fail-closed, under ``backend/shadow_exports``."""

    resolved = slot_state_root.resolve()
    root = _SHADOW_EXPORT_ROOT.resolve()
    if resolved == root or not resolved.is_relative_to(root):
        raise V4UnattendedShadowPublicError("SHADOW_PUBLIC_SLOT_ROOT_OUTSIDE_EXPORTS")
    if slot_state_root.is_symlink():
        raise V4UnattendedShadowPublicError("SHADOW_PUBLIC_SLOT_ROOT_INVALID")
    try:
        slot_state_root.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise V4UnattendedShadowPublicError("SHADOW_PUBLIC_SLOT_ROOT_INVALID") from error
    marker = slot_state_root / f"slot-{slot_utc.strftime('%Y%m%dT%H%MZ')}-observed.json"
    payload = (
        '{"schema":"' + V4_UNATTENDED_SHADOW_PUBLIC_SCHEMA + '",'
        '"completed_slot_utc":"' + slot_utc.isoformat() + '",'
        '"status":"OBSERVED_NO_RETRY","broker_post_count":0}\n'
    )
    try:
        descriptor = os.open(marker, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as error:
        raise V4UnattendedShadowPublicError("SHADOW_PUBLIC_SLOT_ALREADY_OBSERVED") from error
    except OSError as error:
        raise V4UnattendedShadowPublicError("SHADOW_PUBLIC_SLOT_CLAIM_FAILED") from error
