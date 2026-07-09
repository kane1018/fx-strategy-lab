"""Frozen contracts for the E1 full-auto shadow engine.

This package is local-only and virtual-only.  The contracts deliberately do not
contain a broker, HTTP, credential, environment, or real-order capability.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any

E1_SCHEMA_VERSION = "e1-shadow-v1"
E1_STAGE_LABEL = "E1_SHADOW_FULL_AUTO_ENGINE_NO_POST"
HYPOTHESIS_REGISTRY_SCHEMA_VERSION = "e1-hypothesis-registry-v1"
ENGINE_CONTRACT_VERSION = "e1-shadow-engine-contract-v1"
USD_JPY_PIP = Decimal("0.01")
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")


class E1ContractError(ValueError):
    """An E1 input violated a frozen fail-closed contract."""


class E1Stage(str, Enum):
    SHADOW = E1_STAGE_LABEL


class HypothesisLabel(str, Enum):
    BUY_CANDIDATE = "HYPOTHESIS_BUY_CANDIDATE"
    SELL_CANDIDATE = "HYPOTHESIS_SELL_CANDIDATE"
    HOLD_CANDIDATE = "HYPOTHESIS_HOLD_CANDIDATE"
    NO_ACTION = "HYPOTHESIS_NO_ACTION"


class EngineLabel(str, Enum):
    ENTRY_BUY_CANDIDATE = "ENGINE_ENTRY_BUY_CANDIDATE"
    ENTRY_SELL_CANDIDATE = "ENGINE_ENTRY_SELL_CANDIDATE"
    EXIT_CANDIDATE = "ENGINE_EXIT_CANDIDATE"
    SETTLEMENT_CANDIDATE = "ENGINE_SETTLEMENT_CANDIDATE"
    NO_ACTION = "ENGINE_NO_ACTION"


class PositionSide(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"


class GateAction(str, Enum):
    VIRTUAL_ENTRY = "VIRTUAL_ENTRY"
    VIRTUAL_SETTLEMENT = "VIRTUAL_POSITION_SPECIFIC_SETTLEMENT"


class EnginePhase(str, Enum):
    BOOT_RECONCILE_REQUIRED = "BOOT_RECONCILE_REQUIRED"
    RESTART_ACK_REQUIRED = "RESTART_ACK_REQUIRED"
    READY_FLAT = "READY_FLAT"
    POSITION_OPEN = "POSITION_OPEN"
    RECONCILE_REQUIRED = "RECONCILE_REQUIRED"
    HALTED = "HALTED"


class ExecutionOutcome(str, Enum):
    ACCEPTED = "VIRTUAL_ACCEPTED"
    REJECTED = "VIRTUAL_REJECTED"
    TIMEOUT = "VIRTUAL_TIMEOUT_UNKNOWN"
    UNKNOWN = "VIRTUAL_RESULT_UNKNOWN"
    NETWORK_ERROR = "VIRTUAL_NETWORK_ERROR_UNKNOWN"
    PARTIAL_FILL = "VIRTUAL_PARTIAL_FILL_UNEXPECTED"


class FaultKind(str, Enum):
    NONE = "NONE"
    REJECTED = "REJECTED"
    TIMEOUT = "TIMEOUT"
    UNKNOWN_RESULT = "UNKNOWN_RESULT"
    NETWORK_ERROR = "NETWORK_ERROR"
    CRASH_MID_VIRTUAL_EXECUTION = "CRASH_MID_VIRTUAL_EXECUTION"
    PARTIAL_FILL = "PARTIAL_FILL"
    RESTART_RECONCILE = "RESTART_RECONCILE"


class PnlCategory(str, Enum):
    NOT_APPLICABLE = "NOT_APPLICABLE"
    WIN = "VIRTUAL_WIN"
    LOSS = "VIRTUAL_LOSS"
    BREAKEVEN = "VIRTUAL_BREAKEVEN"


class KillReason(str, Enum):
    MANUAL = "MANUAL_KILL"
    DEADMAN_HEARTBEAT_EXPIRED = "DEADMAN_HEARTBEAT_EXPIRED"
    RECONCILE_MISMATCH = "RECONCILE_MISMATCH"
    SAFETY_VIOLATION = "SAFETY_VIOLATION"
    CONFIG_HASH_MISMATCH = "CONFIG_HASH_MISMATCH"
    PERSISTENCE_FAILURE = "PERSISTENCE_FAILURE"
    EXECUTION_REJECTED = "EXECUTION_REJECTED"
    EXECUTION_UNCERTAIN = "EXECUTION_UNCERTAIN"


class ReconcileStatus(str, Enum):
    INITIAL_FLAT_CONFIRMED = "INITIAL_FLAT_CONFIRMED"
    MATCHED_STABLE_STATE = "MATCHED_STABLE_STATE"
    RECOVERED_NO_EFFECT = "RECOVERED_NO_EFFECT"
    RECOVERED_PLANNED_EFFECT = "RECOVERED_PLANNED_EFFECT"
    MISMATCH_HALTED = "MISMATCH_HALTED"


def canonical_timestamp(value: datetime | str) -> str:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        text = value.strip()
        if text.endswith("Z"):
            text = f"{text[:-1]}+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError as error:
            raise E1ContractError("timestamp must be ISO-8601") from error
    else:
        raise E1ContractError("timestamp must be a timezone-aware datetime")
    if parsed.tzinfo is None:
        raise E1ContractError("timestamp must include timezone")
    return parsed.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def parse_timestamp(value: datetime | str) -> datetime:
    return datetime.fromisoformat(canonical_timestamp(value).replace("Z", "+00:00"))


def finite_decimal(value: Decimal | int | float | str, *, field_name: str) -> Decimal:
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as error:
        raise E1ContractError(f"{field_name} must be Decimal-compatible") from error
    if not parsed.is_finite():
        raise E1ContractError(f"{field_name} must be finite")
    return parsed


def canonical_decimal(value: Decimal | int | float | str) -> str:
    parsed = finite_decimal(value, field_name="decimal")
    rendered = format(parsed, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return rendered or "0"


def _hash_payload(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()


def _safe_id(value: str, *, field_name: str) -> str:
    if not isinstance(value, str) or not _SAFE_ID.fullmatch(value):
        raise E1ContractError(f"{field_name} must be a safe local identifier")
    return value


def validate_safe_local_id(value: str, *, field_name: str) -> str:
    """Validate an identifier before it is ever used in a local path."""

    return _safe_id(value, field_name=field_name)


def shadow_safety_flags() -> dict[str, bool | int]:
    """Fixed safety metadata attached to every E1 journal event."""

    return {
        "real_order": False,
        "private_api_used": False,
        "credential_or_env_read": False,
        "broker_read_performed": False,
        "real_http_performed": False,
        "real_post_count": 0,
        "no_order_execution": True,
        "live_trading_environment_enabled": False,
    }


@dataclass(frozen=True)
class FrozenHypothesisSpec:
    """Pre-registered hypothesis identity; rules remain outside the executor."""

    hypothesis_id: str
    version: str
    rule_digest: str
    track: str = "HYPOTHESIS_E1_E2_ONLY"
    live_eligible: bool = False

    def __post_init__(self) -> None:
        _safe_id(self.hypothesis_id, field_name="hypothesis_id")
        _safe_id(self.version, field_name="version")
        if (
            not isinstance(self.rule_digest, str)
            or len(self.rule_digest) != 64
            or any(character not in "0123456789abcdef" for character in self.rule_digest)
        ):
            raise E1ContractError("rule_digest must be a lowercase SHA-256 digest")
        if self.track != "HYPOTHESIS_E1_E2_ONLY" or self.live_eligible is not False:
            raise E1ContractError("E1 hypotheses cannot be live-eligible")


@dataclass(frozen=True)
class FrozenHypothesisRegistry:
    """Immutable registry whose hash is folded into every E1 config hash."""

    specs: tuple[FrozenHypothesisSpec, ...] = ()
    schema_version: str = HYPOTHESIS_REGISTRY_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != HYPOTHESIS_REGISTRY_SCHEMA_VERSION:
            raise E1ContractError("hypothesis registry schema is fixed")
        if not isinstance(self.specs, tuple) or any(
            not isinstance(spec, FrozenHypothesisSpec) for spec in self.specs
        ):
            raise E1ContractError("hypothesis registry specs must be a tuple")
        identities = [(spec.hypothesis_id, spec.version) for spec in self.specs]
        if len(identities) != len(set(identities)):
            raise E1ContractError("hypothesis registry identities must be unique")
        if identities != sorted(identities):
            raise E1ContractError("hypothesis registry specs must use canonical sorted order")

    @property
    def registry_hash(self) -> str:
        return _hash_payload(
            {
                "schema_version": self.schema_version,
                "specs": [asdict(spec) for spec in self.specs],
            }
        )

    def contains(self, *, hypothesis_id: str, version: str) -> bool:
        return any(
            spec.hypothesis_id == hypothesis_id and spec.version == version
            for spec in self.specs
        )


EMPTY_HYPOTHESIS_REGISTRY_HASH = FrozenHypothesisRegistry().registry_hash
INFRASTRUCTURE_FIXTURE_SPEC = FrozenHypothesisSpec(
    hypothesis_id="E1_INFRASTRUCTURE_FIXTURE",
    version="v1",
    rule_digest=hashlib.sha256(b"E1_INFRASTRUCTURE_FIXTURE_V1").hexdigest(),
)
DEFAULT_HYPOTHESIS_REGISTRY = FrozenHypothesisRegistry(specs=(INFRASTRUCTURE_FIXTURE_SPEC,))


@dataclass(frozen=True)
class E1Policy:
    """Immutable shadow-only policy; defaults have no live-risk meaning."""

    schema_version: str = E1_SCHEMA_VERSION
    stage: E1Stage = E1Stage.SHADOW
    hypothesis_registry: FrozenHypothesisRegistry = DEFAULT_HYPOTHESIS_REGISTRY
    allowed_symbol: str = "USD_JPY"
    fixed_virtual_units: int = 1
    max_positions: int = 1
    max_entries_per_day: int = 10
    max_virtual_loss_per_trade: Decimal = Decimal("2")
    max_daily_virtual_loss: Decimal = Decimal("5")
    max_weekly_virtual_loss: Decimal = Decimal("20")
    max_consecutive_losses: int = 5
    max_spread_pips: Decimal = Decimal("0.5")
    max_data_age_seconds: int = 30
    cooldown_seconds: int = 60
    token_ttl_seconds: int = 5
    heartbeat_timeout_seconds: int = 10_800
    require_virtual_protective_stop: bool = True
    allow_real_order: bool = False
    allow_private_api: bool = False
    allow_broker_call: bool = False
    allow_scale_in: bool = False
    allow_position_flip: bool = False
    allow_hedging: bool = False
    allow_martingale: bool = False
    allow_grid: bool = False
    allow_nanpin: bool = False

    def __post_init__(self) -> None:
        if self.schema_version != E1_SCHEMA_VERSION or self.stage is not E1Stage.SHADOW:
            raise E1ContractError("E1 policy schema/stage is fixed")
        if self.allowed_symbol != "USD_JPY":
            raise E1ContractError("E1 currently supports USD_JPY only")
        if not isinstance(self.hypothesis_registry, FrozenHypothesisRegistry):
            raise E1ContractError("E1 policy requires a FrozenHypothesisRegistry")
        positive_ints = (
            self.fixed_virtual_units,
            self.max_entries_per_day,
            self.max_consecutive_losses,
            self.token_ttl_seconds,
            self.heartbeat_timeout_seconds,
        )
        if any(type(value) is not int or value <= 0 for value in positive_ints):
            raise E1ContractError("E1 integer limits must be positive integers")
        if self.max_positions != 1:
            raise E1ContractError("E1 max_positions is structurally fixed at one")
        if type(self.max_data_age_seconds) is not int or self.max_data_age_seconds < 0:
            raise E1ContractError("max_data_age_seconds must be non-negative")
        if type(self.cooldown_seconds) is not int or self.cooldown_seconds < 0:
            raise E1ContractError("cooldown_seconds must be non-negative")
        for name in (
            "max_virtual_loss_per_trade",
            "max_daily_virtual_loss",
            "max_weekly_virtual_loss",
            "max_spread_pips",
        ):
            parsed = finite_decimal(getattr(self, name), field_name=name)
            if parsed < 0:
                raise E1ContractError(f"{name} must be non-negative")
            object.__setattr__(self, name, parsed)
        if self.require_virtual_protective_stop is not True:
            raise E1ContractError("virtual protective stop is mandatory in E1")
        forbidden_flags = (
            self.allow_real_order,
            self.allow_private_api,
            self.allow_broker_call,
            self.allow_scale_in,
            self.allow_position_flip,
            self.allow_hedging,
            self.allow_martingale,
            self.allow_grid,
            self.allow_nanpin,
        )
        if any(type(value) is not bool or value for value in forbidden_flags):
            raise E1ContractError("E1 unsafe strategy/execution flags are fixed false")

    @property
    def config_hash(self) -> str:
        payload = asdict(self)
        payload["stage"] = self.stage.value
        payload["engine_contract_version"] = ENGINE_CONTRACT_VERSION
        payload["hypothesis_label_schema"] = [label.value for label in HypothesisLabel]
        payload["engine_label_schema"] = [label.value for label in EngineLabel]
        for name in (
            "max_virtual_loss_per_trade",
            "max_daily_virtual_loss",
            "max_weekly_virtual_loss",
            "max_spread_pips",
        ):
            payload[name] = canonical_decimal(payload[name])
        return _hash_payload(payload)


@dataclass(frozen=True)
class MarketFrame:
    """Caller-supplied local/synthetic frame; it performs no data retrieval."""

    symbol: str
    evaluation_time: str
    market_data_time: str
    bid: Decimal
    ask: Decimal
    market_open: bool = True
    event_clear: bool = True
    trading_window_open: bool = True
    feed_consistent: bool = True

    def __post_init__(self) -> None:
        if self.symbol != "USD_JPY":
            raise E1ContractError("MarketFrame supports USD_JPY only")
        canonical_timestamp(self.evaluation_time)
        canonical_timestamp(self.market_data_time)
        bid = finite_decimal(self.bid, field_name="bid")
        ask = finite_decimal(self.ask, field_name="ask")
        if bid <= 0 or ask <= 0 or ask < bid:
            raise E1ContractError("bid/ask must be positive and ask >= bid")
        for value in (
            self.market_open,
            self.event_clear,
            self.trading_window_open,
            self.feed_consistent,
        ):
            if type(value) is not bool:
                raise E1ContractError("MarketFrame safety gates must be bool")

    @classmethod
    def build(
        cls,
        *,
        symbol: str,
        evaluation_time: datetime | str,
        market_data_time: datetime | str,
        bid: Decimal | int | float | str,
        ask: Decimal | int | float | str,
        market_open: bool = True,
        event_clear: bool = True,
        trading_window_open: bool = True,
        feed_consistent: bool = True,
    ) -> MarketFrame:
        return cls(
            symbol=symbol,
            evaluation_time=canonical_timestamp(evaluation_time),
            market_data_time=canonical_timestamp(market_data_time),
            bid=finite_decimal(bid, field_name="bid"),
            ask=finite_decimal(ask, field_name="ask"),
            market_open=market_open,
            event_clear=event_clear,
            trading_window_open=trading_window_open,
            feed_consistent=feed_consistent,
        )

    @property
    def spread_pips(self) -> Decimal:
        return (self.ask - self.bid) / USD_JPY_PIP

    @property
    def age_seconds(self) -> float:
        elapsed = parse_timestamp(self.evaluation_time) - parse_timestamp(self.market_data_time)
        return elapsed.total_seconds()


@dataclass(frozen=True)
class EngineDecision:
    """A label is data only.  It is not accepted by the virtual executor."""

    engine_label: EngineLabel
    config_hash: str
    reason_code: str
    hypothesis_label: HypothesisLabel | None = None
    hypothesis_id: str | None = None
    hypothesis_version: str | None = None
    position_ref: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.engine_label, EngineLabel):
            raise E1ContractError("engine_label must use the ENGINE_ namespace")
        if self.hypothesis_label is not None and not isinstance(
            self.hypothesis_label, HypothesisLabel
        ):
            raise E1ContractError("hypothesis_label must use the HYPOTHESIS_ namespace")
        if not isinstance(self.config_hash, str) or len(self.config_hash) != 64:
            raise E1ContractError("config_hash must be a SHA-256 digest")
        _safe_id(self.reason_code, field_name="reason_code")
        settlement_labels = {EngineLabel.EXIT_CANDIDATE, EngineLabel.SETTLEMENT_CANDIDATE}
        if self.engine_label in settlement_labels:
            if self.position_ref is None:
                raise E1ContractError("settlement decisions require a position_ref")
            _safe_id(self.position_ref, field_name="position_ref")
            if (
                self.hypothesis_label is not None
                or self.hypothesis_id is not None
                or self.hypothesis_version is not None
            ):
                raise E1ContractError("settlement decisions cannot carry hypothesis metadata")
        elif self.position_ref is not None:
            raise E1ContractError("entry/no-action decisions cannot carry a position_ref")
        else:
            if (
                self.hypothesis_label is None
                or self.hypothesis_id is None
                or self.hypothesis_version is None
            ):
                raise E1ContractError("hypothesis decisions require registered identity metadata")
            _safe_id(self.hypothesis_id, field_name="hypothesis_id")
            _safe_id(self.hypothesis_version, field_name="hypothesis_version")
            expected_engine_label = {
                HypothesisLabel.BUY_CANDIDATE: EngineLabel.ENTRY_BUY_CANDIDATE,
                HypothesisLabel.SELL_CANDIDATE: EngineLabel.ENTRY_SELL_CANDIDATE,
                HypothesisLabel.HOLD_CANDIDATE: EngineLabel.NO_ACTION,
                HypothesisLabel.NO_ACTION: EngineLabel.NO_ACTION,
            }[self.hypothesis_label]
            if self.engine_label is not expected_engine_label:
                raise E1ContractError("hypothesis and engine label namespaces do not map")

    @property
    def decision_digest(self) -> str:
        return _hash_payload(
            {
                "config_hash": self.config_hash,
                "engine_label": self.engine_label.value,
                "hypothesis_id": self.hypothesis_id,
                "hypothesis_label": (
                    self.hypothesis_label.value
                    if self.hypothesis_label is not None
                    else None
                ),
                "hypothesis_version": self.hypothesis_version,
                "position_ref": self.position_ref,
                "reason_code": self.reason_code,
            }
        )


def build_hypothesis_decision(
    label: HypothesisLabel,
    *,
    config_hash: str,
    reason_code: str,
    hypothesis_id: str = INFRASTRUCTURE_FIXTURE_SPEC.hypothesis_id,
    hypothesis_version: str = INFRASTRUCTURE_FIXTURE_SPEC.version,
) -> EngineDecision:
    if not isinstance(label, HypothesisLabel):
        raise E1ContractError("label must be a HypothesisLabel")
    mapping = {
        HypothesisLabel.BUY_CANDIDATE: EngineLabel.ENTRY_BUY_CANDIDATE,
        HypothesisLabel.SELL_CANDIDATE: EngineLabel.ENTRY_SELL_CANDIDATE,
        HypothesisLabel.HOLD_CANDIDATE: EngineLabel.NO_ACTION,
        HypothesisLabel.NO_ACTION: EngineLabel.NO_ACTION,
    }
    return EngineDecision(
        engine_label=mapping[label],
        hypothesis_label=label,
        hypothesis_id=hypothesis_id,
        hypothesis_version=hypothesis_version,
        config_hash=config_hash,
        reason_code=reason_code,
    )


def build_settlement_decision(
    *,
    position_ref: str,
    config_hash: str,
    reason_code: str,
    exit_candidate: bool = False,
) -> EngineDecision:
    return EngineDecision(
        engine_label=(
            EngineLabel.EXIT_CANDIDATE
            if exit_candidate
            else EngineLabel.SETTLEMENT_CANDIDATE
        ),
        config_hash=config_hash,
        reason_code=reason_code,
        position_ref=position_ref,
    )


@dataclass(frozen=True)
class VirtualPosition:
    position_ref: str
    symbol: str
    side: PositionSide
    units: int
    entry_price: Decimal
    protective_stop_price: Decimal

    def __post_init__(self) -> None:
        _safe_id(self.position_ref, field_name="position_ref")
        if self.symbol != "USD_JPY" or not isinstance(self.side, PositionSide):
            raise E1ContractError("virtual position symbol/side is invalid")
        if type(self.units) is not int or self.units <= 0:
            raise E1ContractError("virtual position units must be positive")
        entry = finite_decimal(self.entry_price, field_name="entry_price")
        stop = finite_decimal(self.protective_stop_price, field_name="protective_stop_price")
        if entry <= 0 or stop <= 0:
            raise E1ContractError("virtual position prices must be positive")
        if self.side is PositionSide.LONG and stop >= entry:
            raise E1ContractError("long virtual protective stop must be below entry")
        if self.side is PositionSide.SHORT and stop <= entry:
            raise E1ContractError("short virtual protective stop must be above entry")


def position_digest(position: VirtualPosition | None) -> str:
    if position is None:
        return _hash_payload({"position": "FLAT", "schema_version": E1_SCHEMA_VERSION})
    return _hash_payload(
        {
            "entry_price": canonical_decimal(position.entry_price),
            "position_ref": position.position_ref,
            "protective_stop_price": canonical_decimal(position.protective_stop_price),
            "schema_version": E1_SCHEMA_VERSION,
            "side": position.side.value,
            "symbol": position.symbol,
            "units": position.units,
        }
    )


@dataclass(frozen=True)
class EntryIntent:
    intent_id: str
    run_id: str
    config_hash: str
    created_at: str
    position: VirtualPosition

    def __post_init__(self) -> None:
        _safe_id(self.intent_id, field_name="intent_id")
        _safe_id(self.run_id, field_name="run_id")
        canonical_timestamp(self.created_at)
        if len(self.config_hash) != 64 or not isinstance(self.position, VirtualPosition):
            raise E1ContractError("entry intent contract is invalid")

    @property
    def intent_digest(self) -> str:
        return _hash_payload(
            {
                "config_hash": self.config_hash,
                "created_at": self.created_at,
                "intent_id": self.intent_id,
                "position_digest": position_digest(self.position),
                "run_id": self.run_id,
            }
        )


@dataclass(frozen=True)
class SettlementIntent:
    intent_id: str
    run_id: str
    config_hash: str
    created_at: str
    position_ref: str
    exit_price: Decimal
    pnl_category: PnlCategory
    virtual_loss: Decimal

    def __post_init__(self) -> None:
        _safe_id(self.intent_id, field_name="intent_id")
        _safe_id(self.run_id, field_name="run_id")
        _safe_id(self.position_ref, field_name="position_ref")
        canonical_timestamp(self.created_at)
        if len(self.config_hash) != 64:
            raise E1ContractError("settlement config_hash is invalid")
        if finite_decimal(self.exit_price, field_name="exit_price") <= 0:
            raise E1ContractError("exit_price must be positive")
        loss = finite_decimal(self.virtual_loss, field_name="virtual_loss")
        if loss < 0:
            raise E1ContractError("virtual_loss stores a non-negative magnitude")
        if self.pnl_category is not PnlCategory.LOSS and loss != 0:
            raise E1ContractError("only VIRTUAL_LOSS may carry virtual_loss")

    @property
    def intent_digest(self) -> str:
        return _hash_payload(
            {
                "config_hash": self.config_hash,
                "created_at": self.created_at,
                "exit_price": canonical_decimal(self.exit_price),
                "intent_id": self.intent_id,
                "pnl_category": self.pnl_category.value,
                "position_ref": self.position_ref,
                "run_id": self.run_id,
                "virtual_loss": canonical_decimal(self.virtual_loss),
            }
        )


@dataclass(frozen=True)
class ShadowGateToken:
    """Single-use capability bound to one virtual intent and config hash."""

    token_id: str
    run_id: str
    intent_id: str
    intent_digest: str
    action: GateAction
    stage: E1Stage
    config_hash: str
    issued_at: str
    expires_at: str

    def __post_init__(self) -> None:
        _safe_id(self.token_id, field_name="token_id")
        _safe_id(self.run_id, field_name="run_id")
        _safe_id(self.intent_id, field_name="intent_id")
        if (
            not isinstance(self.intent_digest, str)
            or len(self.intent_digest) != 64
            or any(character not in "0123456789abcdef" for character in self.intent_digest)
        ):
            raise E1ContractError("ShadowGateToken intent_digest is invalid")
        if self.stage is not E1Stage.SHADOW or not isinstance(self.action, GateAction):
            raise E1ContractError("ShadowGateToken stage/action is invalid")
        if len(self.config_hash) != 64:
            raise E1ContractError("ShadowGateToken config_hash is invalid")
        issued = parse_timestamp(self.issued_at)
        expires = parse_timestamp(self.expires_at)
        if expires <= issued:
            raise E1ContractError("ShadowGateToken expiry must be after issue")

    def is_expired(self, now: datetime | str) -> bool:
        return parse_timestamp(now) >= parse_timestamp(self.expires_at)


def build_token_expiry(now: datetime | str, ttl_seconds: int) -> str:
    return canonical_timestamp(parse_timestamp(now) + timedelta(seconds=ttl_seconds))


@dataclass(frozen=True)
class FaultInjection:
    kind: FaultKind = FaultKind.NONE
    apply_effect_before_fault: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.kind, FaultKind) or type(self.apply_effect_before_fault) is not bool:
            raise E1ContractError("fault injection contract is invalid")
        supports_effect = {
            FaultKind.TIMEOUT,
            FaultKind.UNKNOWN_RESULT,
            FaultKind.NETWORK_ERROR,
            FaultKind.CRASH_MID_VIRTUAL_EXECUTION,
        }
        if self.apply_effect_before_fault and self.kind not in supports_effect:
            raise E1ContractError("this fault kind cannot apply an effect before failing")


@dataclass(frozen=True)
class VirtualExecutionResult:
    outcome: ExecutionOutcome
    observed_state_digest: str
    position_count: int

    def __post_init__(self) -> None:
        if not isinstance(self.outcome, ExecutionOutcome):
            raise E1ContractError("virtual execution outcome is invalid")
        if not isinstance(self.observed_state_digest, str) or len(self.observed_state_digest) != 64:
            raise E1ContractError("observed_state_digest is invalid")
        if self.position_count not in {0, 1}:
            raise E1ContractError("E1 position_count must be zero or one")


@dataclass(frozen=True)
class E1CycleResult:
    status: str
    phase: EnginePhase
    reason_codes: tuple[str, ...]
    virtual_execution_attempted: bool
    token_issued: bool
    actual_post_count: int = 0
    real_http_performed: bool = False
    broker_or_private_api_used: bool = False
    live_permission_granted: bool = False

    def __post_init__(self) -> None:
        _safe_id(self.status, field_name="status")
        if not isinstance(self.phase, EnginePhase):
            raise E1ContractError("cycle phase is invalid")
        if any(
            not isinstance(reason, str) or not _SAFE_ID.fullmatch(reason)
            for reason in self.reason_codes
        ):
            raise E1ContractError("cycle reason_codes must be safe identifiers")
        if (
            self.actual_post_count != 0
            or self.real_http_performed
            or self.broker_or_private_api_used
            or self.live_permission_granted
        ):
            raise E1ContractError("E1 results cannot carry live execution state")

    def __bool__(self) -> bool:
        return False


def make_local_id(prefix: str, payload: dict[str, Any]) -> str:
    _safe_id(prefix, field_name="prefix")
    return f"{prefix}:{_hash_payload(payload)[:24]}"


def classify_pnl(position: VirtualPosition, exit_price: Decimal) -> tuple[PnlCategory, Decimal]:
    price = finite_decimal(exit_price, field_name="exit_price")
    if position.side is PositionSide.LONG:
        pnl = (price - position.entry_price) * position.units
    else:
        pnl = (position.entry_price - price) * position.units
    if not math.isfinite(float(pnl)):
        raise E1ContractError("virtual PnL must be finite")
    if pnl > 0:
        return PnlCategory.WIN, Decimal("0")
    if pnl < 0:
        return PnlCategory.LOSS, -pnl
    return PnlCategory.BREAKEVEN, Decimal("0")
