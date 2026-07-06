from dataclasses import dataclass
from enum import Enum

from app.config import Settings
from app.schemas.trading import OrderRequest, RiskConfig
from app.services.gmo_live_safety_policy import (
    GmoLiveEnablePolicyInput,
    GmoLiveKillSwitchState,
    GmoLiveRiskConfig,
    evaluate_gmo_live_enable_policy,
    evaluate_gmo_live_kill_switch,
)


@dataclass(frozen=True)
class RiskDecision:
    allowed: bool
    reasons: list[str]


def evaluate_order_risk(
    request: OrderRequest,
    risk: RiskConfig,
    settings: Settings,
    *,
    open_positions: int,
    daily_loss: float,
    consecutive_losses: int,
) -> RiskDecision:
    reasons: list[str] = []
    if not request.manual_stop_available:
        reasons.append("手動停止機能が無効")
    if not request.logs_enabled:
        reasons.append("取引ログ保存が無効")
    if request.units > risk.max_units:
        reasons.append("最大取引数量を超過")
    if request.estimated_loss > risk.max_loss_per_trade:
        reasons.append("1回の最大損失額を超過")
    if daily_loss + request.estimated_loss > risk.max_daily_loss:
        reasons.append("1日の最大損失額を超過")
    if open_positions >= risk.max_positions:
        reasons.append("最大ポジション数に到達")
    if consecutive_losses >= risk.max_consecutive_losses:
        reasons.append("連敗停止条件に到達")
    if request.spread_pips > risk.max_spread_pips:
        reasons.append("スプレッド上限を超過")
    if request.high_impact_news_active:
        reasons.append("重要指標の停止時間帯")
    if request.side.value == "buy" and not (
        request.stop_loss < request.current_price < request.take_profit
    ):
        reasons.append("買い注文の損切り・利確価格が不正")
    if request.side.value == "sell" and not (
        request.take_profit < request.current_price < request.stop_loss
    ):
        reasons.append("売り注文の損切り・利確価格が不正")
    if request.mode == "live":
        if not settings.enable_live_trading:
            reasons.append("環境変数 ENABLE_LIVE_TRADING が true ではない")
        if not request.admin_live_enabled:
            reasons.append("管理画面の実資金モードがOFF")
        if request.confirmation_text != settings.live_confirmation_phrase:
            reasons.append("確認文言が一致しない")
        if not request.api_connection_ok:
            reasons.append("直近のAPI接続テストが成功していない")
        if risk.max_units <= 0 or risk.max_daily_loss <= 0:
            reasons.append("最大数量または日次最大損失が未設定")
        # This MVP never routes live funds. The explicit blocker prevents accidental wiring.
        reasons.append("実資金ブローカーアダプターが未実装")
    return RiskDecision(allowed=not reasons, reasons=reasons)


class GmoLiveShadowBlockReason(str, Enum):
    """Structured safe-label categories for GmoLiveReadinessShadowResult.

    A safe result type kept independent of `evaluate_order_risk`'s free-text
    Japanese reasons, so a future real integration Step can match on stable
    enum values instead of parsing strings.
    """

    GMO_LIVE_ENABLED_FALSE = "GMO_LIVE_ENABLED_FALSE"
    LIVE_ENABLE_POLICY_NOT_READY = "LIVE_ENABLE_POLICY_NOT_READY"
    KILL_SWITCH_TRIGGERED = "KILL_SWITCH_TRIGGERED"
    GENERIC_CLOSE_ATTEMPT_DETECTED = "GENERIC_CLOSE_ATTEMPT_DETECTED"
    SETTLEMENT_SIDE_DOCS_NOT_CONFIRMED = "SETTLEMENT_SIDE_DOCS_NOT_CONFIRMED"
    PAPER_EVIDENCE_MISSING = "PAPER_EVIDENCE_MISSING"
    OPERATOR_ENABLE_MISSING = "OPERATOR_ENABLE_MISSING"


@dataclass(frozen=True)
class GmoLiveReadinessShadowInput:
    """Safe-label-only inputs for the GMO live shadow gate.

    Never carries a real position ID, quantity, price, or credential.
    """

    risk_config: GmoLiveRiskConfig = GmoLiveRiskConfig()
    live_enable_policy_input: GmoLiveEnablePolicyInput = GmoLiveEnablePolicyInput()
    kill_switch_state: GmoLiveKillSwitchState = GmoLiveKillSwitchState()
    generic_close_attempt_detected: bool = False
    settlement_side_docs_status_classified: bool = False
    paper_evidence_safe_label_present: bool = False
    operator_live_enable_declared: bool = False


@dataclass(frozen=True)
class GmoLiveReadinessShadowResult:
    entry_shadow_allowed: bool
    settlement_shadow_allowed: bool
    blocked_reasons: tuple[str, ...]
    shadow_only: bool = True


def evaluate_gmo_live_readiness_shadow(
    shadow_input: GmoLiveReadinessShadowInput | None = None,
) -> GmoLiveReadinessShadowResult:
    """Shadow-only GMO live readiness classification.

    This NEVER gates a real order request and is not called by
    `evaluate_order_risk` -- the existing unconditional GMO live rejection
    above is untouched. It exists so callers (tests, future reporting, a
    future real integration Step) can observe what GMO live readiness WOULD
    be, without wiring it into the real decision path. Default-constructed
    input blocks everything, matching the existing default-deny posture.
    """
    snapshot = shadow_input or GmoLiveReadinessShadowInput()
    reasons: list[str] = []

    if not snapshot.risk_config.gmo_live_enabled:
        reasons.append(GmoLiveShadowBlockReason.GMO_LIVE_ENABLED_FALSE.value)

    live_enable_result = evaluate_gmo_live_enable_policy(snapshot.live_enable_policy_input)
    if not live_enable_result.live_enable_ready:
        reasons.append(GmoLiveShadowBlockReason.LIVE_ENABLE_POLICY_NOT_READY.value)

    kill_switch_decision = evaluate_gmo_live_kill_switch(snapshot.kill_switch_state)
    if not kill_switch_decision.entry_allowed:
        reasons.append(GmoLiveShadowBlockReason.KILL_SWITCH_TRIGGERED.value)

    if snapshot.generic_close_attempt_detected:
        reasons.append(GmoLiveShadowBlockReason.GENERIC_CLOSE_ATTEMPT_DETECTED.value)
    if not snapshot.settlement_side_docs_status_classified:
        reasons.append(GmoLiveShadowBlockReason.SETTLEMENT_SIDE_DOCS_NOT_CONFIRMED.value)
    if not snapshot.paper_evidence_safe_label_present:
        reasons.append(GmoLiveShadowBlockReason.PAPER_EVIDENCE_MISSING.value)
    if not snapshot.operator_live_enable_declared:
        reasons.append(GmoLiveShadowBlockReason.OPERATOR_ENABLE_MISSING.value)

    settlement_blocked = bool(reasons) or not kill_switch_decision.settlement_allowed
    return GmoLiveReadinessShadowResult(
        entry_shadow_allowed=not reasons,
        settlement_shadow_allowed=not settlement_blocked,
        blocked_reasons=tuple(reasons),
    )
