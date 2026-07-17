"""Frozen generation contract for the GMO relaxed v4 pre-canary path.

This is deliberately separate from ``H11_AUTO_GENERATION_V1``.  The strict
schema requires atomic protection and a dedicated account, while the operator
selected GMO v4 profile uses MARKET entry, a bounded protection gap, and
temporal account exclusivity.  Sharing one schema would weaken the strict
profile.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from app.h11_auto.runtime_safety import DeadManPolicy, PhaseBRiskPolicy
from app.h11_auto.v4_activation_preparation import V4ApprovedOperatorSelections
from app.h11_auto.v4_gmo_contracts import (
    V4_GMO_BLOCKED_HOURS_JST,
    V4_GMO_EXIT_PROFILE,
    V4_GMO_FRIDAY_ENTRY_CUTOFF_HOUR_JST,
    V4_GMO_FRIDAY_ENTRY_START_HOUR_JST,
    V4_GMO_MAXIMUM_HOLD_SECONDS,
    V4_GMO_PROFILE_VERSION,
    V4_GMO_WEEKEND_DAYS_JST,
    V4_GMO_WEEKEND_EXIT_SEQUENCE_START_HOUR_JST,
    V4_GMO_WEEKEND_EXIT_SEQUENCE_START_MINUTE_JST,
    V4_GMO_WEEKEND_FLAT_HOUR_JST,
    V4_GMO_WEEKEND_FLAT_WEEKDAY_JST,
    V4GmoExecutionPolicy,
)
from app.h11_auto.v4_gmo_evidence import H11_V4_GMO_CAPABILITY_EVIDENCE_HASH
from app.h11_auto.v4_gmo_protection import H11_V4_GMO_PROTECTION_CONTRACT_HASH

V4_GMO_GENERATION_SCHEMA = "H11_AUTO_GENERATION_V4_GMO_FRIDAY_LIMITED_V2"
V4_GMO_GENERATION_STATUS = "OPERATOR_FROZEN_NOT_ACTIVATED"
V4_GMO_GENERATION_ARTIFACT = Path(
    "docs/templates/h11_v4_gmo_frozen_generation.json"
)
_SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
_LABEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,127}$")


class V4GmoGenerationError(ValueError):
    """Fail-closed generation validation error containing safe labels only."""


@dataclass(frozen=True)
class V4GmoFrozenGeneration:
    schema: str
    status: str
    generation_label: str
    implementation_digest: str
    operator_selection_digest: str
    execution_profile: str
    policy_config_hash: str
    strategy_version: str
    signal_config_hash: str
    selected_horizon: str
    symbol: str
    quantity_units: int
    account_ownership: str
    temporary_unprotected_gap_accepted: bool
    maximum_unprotected_seconds: int
    protection_contract_hash: str
    broker_capability_evidence_hash: str
    risk_policy_label: str
    risk_policy_digest: str
    per_trade_loss_bound_jpy: int
    daily_loss_limit_jpy: int
    monthly_loss_limit_jpy: int
    maximum_consecutive_losses: int
    blocked_hours_jst: tuple[int, ...]
    friday_entry_start_hour_jst: int
    friday_entry_cutoff_hour_jst: int
    weekend_days_jst: tuple[int, ...]
    weekend_flat_weekday_jst: int
    weekend_flat_hour_jst: int
    weekend_exit_sequence_start_hour_jst: int
    weekend_exit_sequence_start_minute_jst: int
    maximum_hold_seconds: int
    exit_profile_label: str
    dead_man_policy_label: str
    dead_man_policy_digest: str
    heartbeat_interval_seconds: int
    maximum_heartbeat_age_seconds: int
    adverse_slippage_allowance_pips: str
    maximum_entries_per_day: int
    same_action_retry_allowed: bool
    same_action_repost_allowed: bool
    actual_post_authorized: bool = False
    live_ready: bool = False
    unattended_live_supported: bool = False

    def __post_init__(self) -> None:
        selections = V4ApprovedOperatorSelections()
        requirements = (
            self.schema == V4_GMO_GENERATION_SCHEMA,
            self.status == V4_GMO_GENERATION_STATUS,
            bool(_LABEL.fullmatch(self.generation_label)),
            bool(_SHA256.fullmatch(self.implementation_digest)),
            self.operator_selection_digest == selections.digest,
            self.execution_profile == V4_GMO_PROFILE_VERSION,
            bool(_SHA256.fullmatch(self.policy_config_hash)),
            self.strategy_version == selections.strategy_version,
            self.signal_config_hash == selections.signal_config_hash,
            self.selected_horizon == selections.selected_horizon.value,
            self.symbol == "USD_JPY",
            self.quantity_units == 1_000,
            self.account_ownership == selections.account_ownership.value,
            self.temporary_unprotected_gap_accepted is True,
            self.maximum_unprotected_seconds == 15,
            self.protection_contract_hash == H11_V4_GMO_PROTECTION_CONTRACT_HASH,
            self.broker_capability_evidence_hash
            == H11_V4_GMO_CAPABILITY_EVIDENCE_HASH,
            self.risk_policy_label == selections.risk_policy_label,
            self.per_trade_loss_bound_jpy == 5_000,
            self.daily_loss_limit_jpy == 10_000,
            self.monthly_loss_limit_jpy == 50_000,
            self.maximum_consecutive_losses == 5,
            self.blocked_hours_jst == V4_GMO_BLOCKED_HOURS_JST,
            self.friday_entry_start_hour_jst
            == V4_GMO_FRIDAY_ENTRY_START_HOUR_JST,
            self.friday_entry_cutoff_hour_jst
            == V4_GMO_FRIDAY_ENTRY_CUTOFF_HOUR_JST,
            self.weekend_days_jst == V4_GMO_WEEKEND_DAYS_JST,
            self.weekend_flat_weekday_jst == V4_GMO_WEEKEND_FLAT_WEEKDAY_JST,
            self.weekend_flat_hour_jst == V4_GMO_WEEKEND_FLAT_HOUR_JST,
            self.weekend_exit_sequence_start_hour_jst
            == V4_GMO_WEEKEND_EXIT_SEQUENCE_START_HOUR_JST,
            self.weekend_exit_sequence_start_minute_jst
            == V4_GMO_WEEKEND_EXIT_SEQUENCE_START_MINUTE_JST,
            self.maximum_hold_seconds == V4_GMO_MAXIMUM_HOLD_SECONDS,
            self.exit_profile_label == V4_GMO_EXIT_PROFILE,
            self.dead_man_policy_label == "H11_AUTO_DEAD_MAN_15_60_V1",
            self.heartbeat_interval_seconds == 15,
            self.maximum_heartbeat_age_seconds == 60,
            self.adverse_slippage_allowance_pips == "5.0",
            self.maximum_entries_per_day == 1,
            self.same_action_retry_allowed is False,
            self.same_action_repost_allowed is False,
            self.actual_post_authorized is False,
            self.live_ready is False,
            self.unattended_live_supported is False,
        )
        if not all(requirements):
            raise V4GmoGenerationError("v4 GMO frozen generation mismatch")
        derived_policy = V4GmoExecutionPolicy(
            strategy_version=self.strategy_version,
            signal_config_hash=self.signal_config_hash,
            selected_horizon=selections.selected_horizon,
            protection_contract_hash=self.protection_contract_hash,
            broker_capability_evidence_hash=self.broker_capability_evidence_hash,
        )
        if self.policy_config_hash != derived_policy.config_hash:
            raise V4GmoGenerationError("v4 GMO policy config hash mismatch")
        if self.risk_policy_digest != v4_gmo_risk_policy().digest:
            raise V4GmoGenerationError("v4 GMO risk policy digest mismatch")
        if self.dead_man_policy_digest != v4_gmo_dead_man_policy().digest:
            raise V4GmoGenerationError("v4 GMO dead-man policy digest mismatch")

    @property
    def canonical_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))

    @property
    def digest(self) -> str:
        return "sha256:" + hashlib.sha256(self.canonical_json.encode()).hexdigest()

    def __bool__(self) -> bool:
        return False


def build_v4_gmo_frozen_generation(
    *,
    generation_label: str,
    implementation_digest: str,
    policy: V4GmoExecutionPolicy,
) -> V4GmoFrozenGeneration:
    """Build the exact disabled generation selected for the first canary."""

    selections = V4ApprovedOperatorSelections()
    risk_policy = v4_gmo_risk_policy()
    dead_man_policy = v4_gmo_dead_man_policy()
    if (
        policy.strategy_version != selections.strategy_version
        or policy.signal_config_hash != selections.signal_config_hash
        or policy.selected_horizon is not selections.selected_horizon
    ):
        raise V4GmoGenerationError("v4 GMO policy does not match operator selection")
    return V4GmoFrozenGeneration(
        schema=V4_GMO_GENERATION_SCHEMA,
        status=V4_GMO_GENERATION_STATUS,
        generation_label=generation_label,
        implementation_digest=implementation_digest,
        operator_selection_digest=selections.digest,
        execution_profile=V4_GMO_PROFILE_VERSION,
        policy_config_hash=policy.config_hash,
        strategy_version=policy.strategy_version,
        signal_config_hash=policy.signal_config_hash,
        selected_horizon=policy.selected_horizon.value,
        symbol="USD_JPY",
        quantity_units=policy.requested_size,
        account_ownership=selections.account_ownership.value,
        temporary_unprotected_gap_accepted=policy.temporary_unprotected_gap_accepted,
        maximum_unprotected_seconds=policy.max_unprotected_seconds,
        protection_contract_hash=policy.protection_contract_hash,
        broker_capability_evidence_hash=policy.broker_capability_evidence_hash,
        risk_policy_label=risk_policy.policy_label,
        risk_policy_digest=risk_policy.digest,
        per_trade_loss_bound_jpy=policy.max_loss_per_trade_yen,
        daily_loss_limit_jpy=policy.max_loss_per_day_yen,
        monthly_loss_limit_jpy=policy.max_loss_per_month_yen,
        maximum_consecutive_losses=policy.max_consecutive_losses,
        blocked_hours_jst=policy.blocked_hours_jst,
        friday_entry_start_hour_jst=policy.friday_entry_start_hour_jst,
        friday_entry_cutoff_hour_jst=policy.friday_entry_cutoff_hour_jst,
        weekend_days_jst=policy.weekend_days_jst,
        weekend_flat_weekday_jst=policy.weekend_flat_weekday_jst,
        weekend_flat_hour_jst=policy.weekend_flat_hour_jst,
        weekend_exit_sequence_start_hour_jst=(
            policy.weekend_exit_sequence_start_hour_jst
        ),
        weekend_exit_sequence_start_minute_jst=(
            policy.weekend_exit_sequence_start_minute_jst
        ),
        maximum_hold_seconds=policy.maximum_hold_seconds,
        exit_profile_label=policy.exit_profile_label,
        dead_man_policy_label=dead_man_policy.policy_label,
        dead_man_policy_digest=dead_man_policy.digest,
        heartbeat_interval_seconds=selections.heartbeat_interval_seconds,
        maximum_heartbeat_age_seconds=selections.maximum_heartbeat_age_seconds,
        adverse_slippage_allowance_pips="5.0",
        maximum_entries_per_day=policy.max_entries_per_day,
        same_action_retry_allowed=policy.same_action_retry_allowed,
        same_action_repost_allowed=policy.same_action_repost_allowed,
    )


def v4_gmo_risk_policy() -> PhaseBRiskPolicy:
    selections = V4ApprovedOperatorSelections()
    return PhaseBRiskPolicy(
        policy_label=selections.risk_policy_label,
        per_trade_loss_bound_jpy=selections.per_trade_loss_bound_jpy,
        daily_loss_limit_jpy=selections.daily_loss_limit_jpy,
        monthly_loss_limit_jpy=selections.monthly_loss_limit_jpy,
        maximum_consecutive_losses=selections.maximum_consecutive_losses,
        maximum_entries_per_day=selections.maximum_entries_per_day,
    )


def v4_gmo_dead_man_policy() -> DeadManPolicy:
    selections = V4ApprovedOperatorSelections()
    return DeadManPolicy(
        policy_label="H11_AUTO_DEAD_MAN_15_60_V1",
        maximum_heartbeat_age_seconds=selections.maximum_heartbeat_age_seconds,
    )


def load_v4_gmo_frozen_generation(
    *, repository: Path, implementation_digest: str
) -> V4GmoFrozenGeneration:
    """Load the committed artifact and bind it to the reviewed source digest."""

    path = repository.resolve() / V4_GMO_GENERATION_ARTIFACT
    if not path.is_file() or path.is_symlink():
        raise V4GmoGenerationError("v4 GMO frozen generation artifact missing")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise TypeError
        payload["blocked_hours_jst"] = tuple(payload["blocked_hours_jst"])
        payload["weekend_days_jst"] = tuple(payload["weekend_days_jst"])
        generation = V4GmoFrozenGeneration(**payload)
    except (OSError, json.JSONDecodeError, TypeError) as error:
        raise V4GmoGenerationError(
            "v4 GMO frozen generation artifact invalid"
        ) from error
    if generation.implementation_digest != implementation_digest:
        raise V4GmoGenerationError("v4 GMO implementation digest mismatch")
    return generation
