"""Frozen input contracts for H11_AUTO_PARALLEL_PHASE_A_NO_POST."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum


class H11AutoContractError(ValueError):
    """Raised when a signal or policy violates the Phase A contract."""


class SignalDecision(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    STAY = "STAY"


class FormalHorizon(str, Enum):
    MINUTES_10 = "10m"
    MINUTES_30 = "30m"


@dataclass(frozen=True)
class FormalSignal:
    """One finalized formal signal; rolling estimates are not accepted."""

    strategy_version: str
    signal_config_hash: str
    horizon: FormalHorizon
    observed_at_utc: datetime
    valid_until_utc: datetime
    decision: SignalDecision
    probability_up: Decimal
    finalized_bar: bool = True
    rolling_estimate: bool = False

    def __post_init__(self) -> None:
        if (
            not isinstance(self.strategy_version, str)
            or not self.strategy_version.strip()
            or not isinstance(self.signal_config_hash, str)
            or not self.signal_config_hash.strip()
        ):
            raise H11AutoContractError("signal version and config hash are required")
        if not isinstance(self.horizon, FormalHorizon) or not isinstance(
            self.decision, SignalDecision
        ):
            raise H11AutoContractError("signal horizon and decision are invalid")
        if not isinstance(self.observed_at_utc, datetime) or not isinstance(
            self.valid_until_utc, datetime
        ):
            raise H11AutoContractError("signal timestamps are invalid")
        if self.observed_at_utc.tzinfo is None or self.valid_until_utc.tzinfo is None:
            raise H11AutoContractError("signal timestamps must be timezone-aware")
        if self.valid_until_utc <= self.observed_at_utc:
            raise H11AutoContractError("signal validity must end after observation")
        if (
            not isinstance(self.probability_up, Decimal)
            or not self.probability_up.is_finite()
            or not Decimal("0") <= self.probability_up <= Decimal("1")
        ):
            raise H11AutoContractError("probability_up must be between zero and one")
        if (
            type(self.finalized_bar) is not bool
            or type(self.rolling_estimate) is not bool
            or not self.finalized_bar
            or self.rolling_estimate
        ):
            raise H11AutoContractError("only finalized formal signals are accepted")

    @property
    def fingerprint(self) -> str:
        payload = {
            "decision": self.decision.value,
            "horizon": self.horizon.value,
            "observed_at_utc": self.observed_at_utc.isoformat(),
            "probability_up": format(self.probability_up, "f"),
            "signal_config_hash": self.signal_config_hash,
            "strategy_version": self.strategy_version,
            "valid_until_utc": self.valid_until_utc.isoformat(),
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).hexdigest()


@dataclass(frozen=True)
class PhaseAExecutionPolicy:
    """Broker-independent policy used only by fake/paper execution.

    The strategy and one formal horizon must be selected explicitly.  The
    invariants cannot be weakened by constructor arguments.
    """

    strategy_version: str
    signal_config_hash: str
    selected_horizon: FormalHorizon
    max_positions: int = 1
    max_entries_per_day: int = 1
    scale_in_allowed: bool = False
    hedging_allowed: bool = False
    opposite_signal_as_exit_allowed: bool = False
    retry_allowed: bool = False
    repost_allowed: bool = False
    max_entry_attempts_per_intent: int = 1
    broker_native_protected_entry_required: bool = True

    def __post_init__(self) -> None:
        if (
            not isinstance(self.strategy_version, str)
            or not self.strategy_version.strip()
            or not isinstance(self.signal_config_hash, str)
            or not self.signal_config_hash.strip()
        ):
            raise H11AutoContractError("policy version and config hash are required")
        if not isinstance(self.selected_horizon, FormalHorizon):
            raise H11AutoContractError("policy horizon is invalid")
        immutable_requirements = (
            type(self.max_positions) is int and self.max_positions == 1,
            type(self.max_entries_per_day) is int and self.max_entries_per_day == 1,
            type(self.scale_in_allowed) is bool and not self.scale_in_allowed,
            type(self.hedging_allowed) is bool and not self.hedging_allowed,
            type(self.opposite_signal_as_exit_allowed) is bool
            and not self.opposite_signal_as_exit_allowed,
            type(self.retry_allowed) is bool and not self.retry_allowed,
            type(self.repost_allowed) is bool and not self.repost_allowed,
            type(self.max_entry_attempts_per_intent) is int
            and self.max_entry_attempts_per_intent == 1,
            type(self.broker_native_protected_entry_required) is bool
            and self.broker_native_protected_entry_required,
        )
        if not all(immutable_requirements):
            raise H11AutoContractError("Phase A safety invariants cannot be weakened")

    def accepts(self, signal: FormalSignal) -> bool:
        return (
            signal.strategy_version == self.strategy_version
            and signal.signal_config_hash == self.signal_config_hash
            and signal.horizon is self.selected_horizon
        )


def build_intent_id(*, signal: FormalSignal, policy: PhaseAExecutionPolicy) -> str:
    if not policy.accepts(signal):
        raise H11AutoContractError("signal does not match the frozen execution policy")
    canonical = "|".join(
        (
            "H11_AUTO_PARALLEL_V1",
            signal.fingerprint,
            policy.strategy_version,
            policy.signal_config_hash,
            policy.selected_horizon.value,
            signal.decision.value,
        )
    )
    return hashlib.sha256(canonical.encode()).hexdigest()
