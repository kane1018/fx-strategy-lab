"""Approved H-11 v4 activation-preparation contracts (disabled/no-POST).

The operator selections are frozen here so host, account-ownership, cadence,
clock, and notification rehearsals can share one deterministic contract.  The
module deliberately has no broker transport, credential loader, network
client, activation permit, or real notification sender.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import Enum

from app.h11_auto.contracts import FormalHorizon

V4_ACTIVATION_PREPARATION_VERSION = "H11_V4_ACTIVATION_PREPARATION_NO_POST_V1"


class V4ActivationPreparationError(ValueError):
    """Safe validation failure for the disabled preparation layer."""


class V4AccountOwnershipMode(str, Enum):
    EXCLUSIVE_DURING_AUTO = "EXCLUSIVE_DURING_AUTO"


class V4HostSelection(str, Enum):
    CURRENT_MAC_SUPERVISED_FAKE_REHEARSAL = "CURRENT_MAC_SUPERVISED_FAKE_REHEARSAL"


class V4NotificationRoute(str, Enum):
    PUSHOVER = "PUSHOVER"
    EMAIL = "EMAIL"


class V4CadenceMethod(str, Enum):
    PRIVATE_GET = "PRIVATE_GET"
    PRIVATE_POST = "PRIVATE_POST"


@dataclass(frozen=True)
class V4ApprovedOperatorSelections:
    """Selections approved on 2026-07-15; not an activation decision."""

    selected_horizon: FormalHorizon = FormalHorizon.MINUTES_30
    strategy_version: str = "SHORT_V1"
    signal_config_hash: str = (
        "sha256:ca08df187ae11b89192f1bbb4f77adc712ad41dc07d06d85bd67c9c7bcf6135d"
    )
    risk_policy_label: str = "H11_AUTO_INITIAL_MINIMUM_LIVE_V1"
    per_trade_loss_bound_jpy: int = 5_000
    daily_loss_limit_jpy: int = 10_000
    monthly_loss_limit_jpy: int = 50_000
    maximum_consecutive_losses: int = 5
    maximum_entries_per_day: int = 1
    heartbeat_interval_seconds: int = 15
    maximum_heartbeat_age_seconds: int = 60
    account_ownership: V4AccountOwnershipMode = (
        V4AccountOwnershipMode.EXCLUSIVE_DURING_AUTO
    )
    host_selection: V4HostSelection = (
        V4HostSelection.CURRENT_MAC_SUPERVISED_FAKE_REHEARSAL
    )
    primary_notification: V4NotificationRoute = V4NotificationRoute.PUSHOVER
    secondary_notification: V4NotificationRoute = V4NotificationRoute.EMAIL
    private_get_minimum_interval_seconds: float = 0.25
    private_post_minimum_interval_seconds: float = 1.10
    maximum_clock_skew_seconds: float = 5.0
    actual_activation_allowed: bool = False

    def __post_init__(self) -> None:
        requirements = (
            self.selected_horizon is FormalHorizon.MINUTES_30,
            self.strategy_version == "SHORT_V1",
            self.signal_config_hash
            == "sha256:ca08df187ae11b89192f1bbb4f77adc712ad41dc07d06d85bd67c9c7bcf6135d",
            self.risk_policy_label == "H11_AUTO_INITIAL_MINIMUM_LIVE_V1",
            self.per_trade_loss_bound_jpy == 5_000,
            self.daily_loss_limit_jpy == 10_000,
            self.monthly_loss_limit_jpy == 50_000,
            self.maximum_consecutive_losses == 5,
            self.maximum_entries_per_day == 1,
            self.heartbeat_interval_seconds == 15,
            self.maximum_heartbeat_age_seconds == 60,
            self.account_ownership is V4AccountOwnershipMode.EXCLUSIVE_DURING_AUTO,
            self.host_selection
            is V4HostSelection.CURRENT_MAC_SUPERVISED_FAKE_REHEARSAL,
            self.primary_notification is V4NotificationRoute.PUSHOVER,
            self.secondary_notification is V4NotificationRoute.EMAIL,
            self.private_get_minimum_interval_seconds == 0.25,
            self.private_post_minimum_interval_seconds == 1.10,
            self.maximum_clock_skew_seconds == 5.0,
            type(self.actual_activation_allowed) is bool
            and not self.actual_activation_allowed,
        )
        if not all(requirements):
            raise V4ActivationPreparationError(
                "approved v4 preparation selections cannot be changed"
            )

    @property
    def digest(self) -> str:
        payload = asdict(self)
        for key in (
            "selected_horizon",
            "account_ownership",
            "host_selection",
            "primary_notification",
            "secondary_notification",
        ):
            payload[key] = payload[key].value
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()

    def __bool__(self) -> bool:
        return False


@dataclass(frozen=True)
class V4AccountExclusivityObservation:
    """Sanitized account-use facts. No identifiers or broker payloads."""

    broker_snapshot_known: bool
    manual_trade_session_active: bool
    other_private_api_client_active: bool
    unowned_position_count: int
    unowned_active_order_count: int

    def __post_init__(self) -> None:
        flags = (
            self.broker_snapshot_known,
            self.manual_trade_session_active,
            self.other_private_api_client_active,
        )
        counts = (self.unowned_position_count, self.unowned_active_order_count)
        if any(type(value) is not bool for value in flags):
            raise V4ActivationPreparationError("account observation flags are invalid")
        if any(type(value) is not int or value < 0 for value in counts):
            raise V4ActivationPreparationError("account observation counts are invalid")


@dataclass(frozen=True)
class V4AccountExclusivityResult:
    ready: bool
    halt_required: bool
    reasons: tuple[str, ...]
    actual_activation_allowed: bool = False

    def __bool__(self) -> bool:
        return False


def evaluate_v4_account_exclusivity(
    observation: V4AccountExclusivityObservation,
) -> V4AccountExclusivityResult:
    """Require temporal account exclusivity before any future automatic entry."""

    checks = (
        (observation.broker_snapshot_known, "BROKER_SNAPSHOT_UNKNOWN"),
        (not observation.manual_trade_session_active, "MANUAL_TRADE_SESSION_ACTIVE"),
        (
            not observation.other_private_api_client_active,
            "OTHER_PRIVATE_API_CLIENT_ACTIVE",
        ),
        (observation.unowned_position_count == 0, "UNOWNED_POSITION_PRESENT"),
        (observation.unowned_active_order_count == 0, "UNOWNED_ACTIVE_ORDER_PRESENT"),
    )
    reasons = tuple(reason for passed, reason in checks if not passed)
    return V4AccountExclusivityResult(
        ready=not reasons,
        halt_required=bool(reasons),
        reasons=reasons,
    )


# Private API pacing (GMO official: GET <=6/s, POST <=1/s per account, plus an
# undocumented adaptive throttle under load whose response shape is unspecified).
# Both 2026-07-21 incidents (entry POST unknown with no broker order record;
# post-entry reconciliation unknown after a fill) coincided with reconcile GETs
# and a POST packed into the same one-second window, so the callers now PACE
# conservatively and the gate enforces slightly looser floors as a fail-closed
# backstop (pacing must always satisfy the gate with margin — the gate never
# sleeps or retries, it only refuses).
V4_PRIVATE_GET_PACING_SECONDS = 0.55  # caller-side GET->GET spacing (~1.8/s)
V4_PRIVATE_POST_TO_GET_PACING_SECONDS = 1.10  # first GET after any POST
V4_PRIVATE_GET_TO_POST_PACING_SECONDS = 1.10  # POST after any GET
V4_PRIVATE_POST_TO_POST_PACING_SECONDS = 1.20  # POST after any POST
V4_PRIVATE_GATE_GET_MINIMUM_SECONDS = 0.50  # gate backstop, below pacing
V4_PRIVATE_GATE_CROSS_MINIMUM_SECONDS = 1.00  # gate backstop GET<->POST


@dataclass
class V4PrivateApiCadenceGate:
    """Account-wide cadence gate; it never sleeps, queues, or retries."""

    get_minimum_interval_seconds: float = V4_PRIVATE_GATE_GET_MINIMUM_SECONDS
    post_minimum_interval_seconds: float = 1.10
    cross_minimum_interval_seconds: float = V4_PRIVATE_GATE_CROSS_MINIMUM_SECONDS
    _last_get_at: float | None = None
    _last_post_at: float | None = None

    def __post_init__(self) -> None:
        values = (
            self.get_minimum_interval_seconds,
            self.post_minimum_interval_seconds,
            self.cross_minimum_interval_seconds,
        )
        if any(
            isinstance(value, bool)
            or not isinstance(value, int | float)
            or not math.isfinite(value)
            or value <= 0
            for value in values
        ):
            raise V4ActivationPreparationError("cadence intervals are invalid")
        if self.get_minimum_interval_seconds < V4_PRIVATE_GATE_GET_MINIMUM_SECONDS:
            raise V4ActivationPreparationError(
                "private GET cadence exceeds the two-per-second safety contract"
            )
        if self.post_minimum_interval_seconds < 1.10:
            raise V4ActivationPreparationError("private POST cadence is not conservative")
        if self.cross_minimum_interval_seconds < V4_PRIVATE_GATE_CROSS_MINIMUM_SECONDS:
            raise V4ActivationPreparationError(
                "private GET/POST cross cadence is not conservative"
            )

    def admit(self, *, method: V4CadenceMethod, now_monotonic: float) -> bool:
        if (
            isinstance(now_monotonic, bool)
            or not isinstance(now_monotonic, int | float)
            or not math.isfinite(now_monotonic)
            or now_monotonic < 0
        ):
            raise V4ActivationPreparationError("cadence clock is invalid")
        if method is V4CadenceMethod.PRIVATE_GET:
            admitted = self._admitted(
                previous=self._last_get_at,
                now=float(now_monotonic),
                minimum=self.get_minimum_interval_seconds,
            ) and self._admitted(
                previous=self._last_post_at,
                now=float(now_monotonic),
                minimum=self.cross_minimum_interval_seconds,
            )
            if admitted:
                self._last_get_at = float(now_monotonic)
            return admitted
        if method is V4CadenceMethod.PRIVATE_POST:
            admitted = self._admitted(
                previous=self._last_post_at,
                now=float(now_monotonic),
                minimum=self.post_minimum_interval_seconds,
            ) and self._admitted(
                previous=self._last_get_at,
                now=float(now_monotonic),
                minimum=self.cross_minimum_interval_seconds,
            )
            if admitted:
                self._last_post_at = float(now_monotonic)
            return admitted
        raise V4ActivationPreparationError("cadence method is invalid")

    @staticmethod
    def _admitted(*, previous: float | None, now: float, minimum: float) -> bool:
        if previous is None:
            return True
        if now < previous:
            return False
        return now - previous + 1e-12 >= minimum

    def __bool__(self) -> bool:
        return False


def v4_reconciliation_get_offsets_seconds() -> tuple[float, float, float]:
    """Fixed schedule for executions, positions, and active-orders GETs."""

    return (
        0.0,
        V4_PRIVATE_GET_PACING_SECONDS,
        2 * V4_PRIVATE_GET_PACING_SECONDS,
    )


@dataclass(frozen=True)
class V4ClockObservation:
    wall_time_utc: datetime
    monotonic_seconds: float
    previous_wall_time_utc: datetime | None
    previous_monotonic_seconds: float | None
    system_clock_sync_known: bool
    absolute_clock_skew_seconds: float | None

    def __post_init__(self) -> None:
        if self.wall_time_utc.tzinfo is None:
            raise V4ActivationPreparationError("wall clock must be timezone-aware")
        if self.previous_wall_time_utc is not None and self.previous_wall_time_utc.tzinfo is None:
            raise V4ActivationPreparationError("previous wall clock must be timezone-aware")
        for value in (self.monotonic_seconds, self.previous_monotonic_seconds):
            if value is not None and (
                isinstance(value, bool)
                or not isinstance(value, int | float)
                or not math.isfinite(value)
                or value < 0
            ):
                raise V4ActivationPreparationError("monotonic clock is invalid")
        if type(self.system_clock_sync_known) is not bool:
            raise V4ActivationPreparationError("clock sync state is invalid")
        skew = self.absolute_clock_skew_seconds
        if skew is not None and (
            isinstance(skew, bool)
            or not isinstance(skew, int | float)
            or not math.isfinite(skew)
            or skew < 0
        ):
            raise V4ActivationPreparationError("clock skew is invalid")


@dataclass(frozen=True)
class V4ClockAssessment:
    synchronized: bool
    halt_required: bool
    reasons: tuple[str, ...]
    skew_bucket: str
    actual_activation_allowed: bool = False

    def __bool__(self) -> bool:
        return False


def assess_v4_clock(
    observation: V4ClockObservation,
    *,
    maximum_clock_skew_seconds: float = 5.0,
) -> V4ClockAssessment:
    if maximum_clock_skew_seconds != 5.0:
        raise V4ActivationPreparationError("clock skew bound is frozen at five seconds")
    reasons: list[str] = []
    if not observation.system_clock_sync_known:
        reasons.append("CLOCK_SYNC_UNKNOWN")
    skew = observation.absolute_clock_skew_seconds
    if skew is None:
        reasons.append("CLOCK_SKEW_UNKNOWN")
        bucket = "UNKNOWN"
    elif skew > maximum_clock_skew_seconds:
        reasons.append("CLOCK_SKEW_EXCEEDED")
        bucket = "OVER_5_SECONDS"
    elif skew > 1.0:
        bucket = "ONE_TO_FIVE_SECONDS"
    else:
        bucket = "AT_MOST_ONE_SECOND"
    if observation.previous_wall_time_utc is not None:
        previous_wall = observation.previous_wall_time_utc.astimezone(UTC)
        current_wall = observation.wall_time_utc.astimezone(UTC)
        if current_wall < previous_wall:
            reasons.append("WALL_CLOCK_MOVED_BACKWARDS")
    if observation.previous_monotonic_seconds is not None:
        if observation.monotonic_seconds <= observation.previous_monotonic_seconds:
            reasons.append("MONOTONIC_CLOCK_NOT_PROGRESSING")
    normalized = tuple(dict.fromkeys(reasons))
    return V4ClockAssessment(
        synchronized=not normalized,
        halt_required=bool(normalized),
        reasons=normalized,
        skew_bucket=bucket,
    )
