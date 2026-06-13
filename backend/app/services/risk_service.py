from dataclasses import dataclass

from app.config import Settings
from app.schemas.trading import OrderRequest, RiskConfig


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
