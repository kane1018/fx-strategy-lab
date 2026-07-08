"""Supervised auto live preview (no-POST, no-credential, no-real-HTTP).

Builds the sanitized package that shows WHAT the automation would propose
and WHICH gates and operator inputs would still be required before any live
POST -- without performing, permitting, or preparing a POST:

- The proposed signal is an ``AUTO_PREVIEW_SIGNAL_*`` label from the paper
  auto cycle runner's enum. It is structurally distinct from the operator
  safe labels (ENTRY_BUY / ENTRY_SELL / HOLD): the package pins
  ``auto_preview_signal_is_operator_signal = False`` and carries the future
  operator inputs as REQUIREMENTS, never as values.
- Inputs are safe labels/booleans only. No credential, ``.env``, runtime
  private GET, sealed value file read, raw market value, or real HTTP
  surface exists in this module.
- ``actual_entry_POST_allowed`` / ``actual_settlement_POST_allowed`` are
  hardcoded false, the package is never truthy, and it answers explicitly
  why a preview is not a permission.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.services.gmo_paper_auto_cycle_runner import AutoPreviewSignal

# The exact operator input NAMES a future live gate still requires. Values
# are never generated, stored, or pre-filled here: confirmation generation by
# the automation is forbidden.
REQUIRED_FUTURE_OPERATOR_INPUT_NAMES: tuple[str, ...] = (
    "operator_signal_type",
    "operator_current_turn_exact_confirmation",
    "operator_readiness",
    "operator_understands_risk",
    "operator_actual_sender_injection_readiness",
    "operator_acknowledges_internal_credential_use_no_exposure",
    "operator_acknowledges_fresh_runtime_read",
)

REQUIRED_FUTURE_GATES: tuple[str, ...] = (
    "FRESH_REPOSITORY_REMOTE_CHECK",
    "FRESH_READ_ONLY_RUNTIME_SAFE_READ",
    "OPERATOR_CURRENT_TURN_EXACT_CONFIRMATION_NOT_BANKED",
    "SEALED_INTERNAL_VALUE_SOURCE_PRESENT_NOT_EXPOSED",
    "FRESH_FINAL_PREFLIGHT",
    "SANITIZED_PREVIEW",
    "REVIEWED_REAL_SENDER_INJECTION_ONE_CALL_SITE",
    "ONE_USE_PERMIT_AND_ACTIVATION",
    "DEFAULT_DENY_HARD_GUARD",
)

WHY_PREVIEW_IS_NOT_PERMISSION = (
    "AUTO_PREVIEW_IS_A_PROPOSAL_ONLY_ACTUAL_POST_REQUIRES_SEPARATE_STEP_WITH_"
    "FRESH_GATES_AND_OPERATOR_CURRENT_TURN_CONFIRMATION"
)


class GmoSupervisedAutoLivePreviewError(RuntimeError):
    """Raised for fail-closed violations. Never carries a raw value."""


class GmoAutoTrendSafeLabel(str, Enum):
    """Synthetic/derived trend safe labels for preview derivation only."""

    UPTREND = "UPTREND"
    DOWNTREND = "DOWNTREND"
    FLAT = "FLAT"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class SupervisedAutoPreviewSafeInput:
    """Safe-label/boolean-only input for THIS preview turn. Default-deny.

    No field can carry a raw price, size, ID, credential, or payload. These
    inputs come from safe labels the caller already holds (e.g. paper
    scenarios); this module never fetches anything itself.
    """

    trend_safe_label: GmoAutoTrendSafeLabel = GmoAutoTrendSafeLabel.UNKNOWN
    position_flat_safe: bool = False
    market_open_safe: bool = False
    ticker_fresh_safe: bool = False
    spread_within_limit_safe: bool = False
    active_pending_clear_safe: bool = False


def derive_auto_preview_signal(
    preview_input: SupervisedAutoPreviewSafeInput,
) -> AutoPreviewSignal:
    """Derive the AUTO preview signal mechanically from safe labels.

    Fail-closed: any unknown/unsafe/degraded input yields
    ``AUTO_PREVIEW_SIGNAL_UNKNOWN_BLOCKED``. A held position or pending
    orders never yield an entry-shaped preview.
    """

    gates_safe = (
        preview_input.position_flat_safe
        and preview_input.market_open_safe
        and preview_input.ticker_fresh_safe
        and preview_input.spread_within_limit_safe
        and preview_input.active_pending_clear_safe
    )
    if not gates_safe:
        return AutoPreviewSignal.AUTO_PREVIEW_SIGNAL_UNKNOWN_BLOCKED
    if preview_input.trend_safe_label is GmoAutoTrendSafeLabel.UPTREND:
        return AutoPreviewSignal.AUTO_PREVIEW_SIGNAL_BUY
    if preview_input.trend_safe_label is GmoAutoTrendSafeLabel.DOWNTREND:
        return AutoPreviewSignal.AUTO_PREVIEW_SIGNAL_SELL
    if preview_input.trend_safe_label is GmoAutoTrendSafeLabel.FLAT:
        return AutoPreviewSignal.AUTO_PREVIEW_SIGNAL_HOLD
    return AutoPreviewSignal.AUTO_PREVIEW_SIGNAL_UNKNOWN_BLOCKED


_SIGNAL_TO_PROPOSAL = {
    AutoPreviewSignal.AUTO_PREVIEW_SIGNAL_BUY: "AUTO_PREVIEW_ENTRY_OPEN_BUY",
    AutoPreviewSignal.AUTO_PREVIEW_SIGNAL_SELL: "AUTO_PREVIEW_ENTRY_OPEN_SELL",
    AutoPreviewSignal.AUTO_PREVIEW_SIGNAL_HOLD: "AUTO_PREVIEW_NO_ORDER",
    AutoPreviewSignal.AUTO_PREVIEW_SIGNAL_UNKNOWN_BLOCKED: (
        "AUTO_PREVIEW_BLOCKED_NO_ORDER"
    ),
}


@dataclass(frozen=True)
class GmoSupervisedAutoLivePreviewPackage:
    """Preview-only package. Never truthy, never a permission.

    Structurally there is no field that can carry an operator confirmation
    VALUE, a credential, a raw size/price/ID, or a request body.
    """

    auto_preview_signal: AutoPreviewSignal
    proposed_action_safe_label: str
    proposal_would_require_live_gate: bool
    required_future_gates: tuple[str, ...]
    required_future_operator_input_names: tuple[str, ...]
    why_not_permission: str
    auto_preview_signal_is_operator_signal: bool = False
    operator_confirmation_generated: bool = False
    operator_confirmation_banked: bool = False
    actual_entry_POST_allowed: bool = False
    actual_settlement_POST_allowed: bool = False
    broker_write_performed: bool = False
    real_http_performed: bool = False
    runtime_private_get_performed: bool = False
    credential_value_read: bool = False
    env_read_performed: bool = False
    raw_id_value_exposure: bool = False
    local_sealed_value_file_read: bool = False
    real_sender_injected: bool = False
    hard_guard_allow_resolved: bool = False

    def __bool__(self) -> bool:
        return False


def build_gmo_supervised_auto_live_preview(
    preview_input: SupervisedAutoPreviewSafeInput,
) -> GmoSupervisedAutoLivePreviewPackage:
    """Build the supervised preview package from safe labels only.

    BUY/SELL previews state that a future live gate with fresh gates and a
    current-turn operator confirmation would still be required; HOLD and
    BLOCKED previews propose no order at all. Nothing here mutates state,
    touches the network, or produces a permission.
    """

    signal = derive_auto_preview_signal(preview_input)
    proposes_order = signal in (
        AutoPreviewSignal.AUTO_PREVIEW_SIGNAL_BUY,
        AutoPreviewSignal.AUTO_PREVIEW_SIGNAL_SELL,
    )
    return GmoSupervisedAutoLivePreviewPackage(
        auto_preview_signal=signal,
        proposed_action_safe_label=_SIGNAL_TO_PROPOSAL[signal],
        proposal_would_require_live_gate=proposes_order,
        required_future_gates=REQUIRED_FUTURE_GATES if proposes_order else (),
        required_future_operator_input_names=(
            REQUIRED_FUTURE_OPERATOR_INPUT_NAMES if proposes_order else ()
        ),
        why_not_permission=WHY_PREVIEW_IS_NOT_PERMISSION,
    )
