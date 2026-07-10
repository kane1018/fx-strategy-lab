"""H-11 preview adapter tests (no-POST). Frozen mapping priority verification."""

from __future__ import annotations

from app.services.gmo_paper_auto_cycle_runner import AutoPreviewSignal
from app.services.h11_preview_adapter import (
    H11AdapterReason,
    map_h11_prediction_to_preview,
)
from app.strategies.h11_regime_moe import H11Prediction, H11PredictionStatus


def _prediction(p_up: float, probs=None, uncertainty: float = 0.01, **overrides):
    probs = probs or (p_up, p_up, p_up)
    values = dict(
        p_up=p_up,
        p_down=1.0 - p_up,
        expert_probabilities=probs,
        expert_weights=(1 / 3, 1 / 3, 1 / 3),
        model_uncertainty=uncertainty,
        prediction_status=H11PredictionStatus.OK,
    )
    values.update(overrides)
    return H11Prediction(**values)


def test_blocked_prediction_maps_to_unknown_blocked():
    blocked = H11Prediction(
        p_up=None,
        p_down=None,
        expert_probabilities=None,
        expert_weights=None,
        model_uncertainty=None,
        prediction_status=H11PredictionStatus.BLOCKED,
        block_reasons=("MODEL_NOT_TRAINED",),
    )
    decision = map_h11_prediction_to_preview(blocked)
    assert decision.signal is AutoPreviewSignal.AUTO_PREVIEW_SIGNAL_UNKNOWN_BLOCKED
    assert decision.reason is H11AdapterReason.PREDICTION_BLOCKED


def test_config_hash_mismatch_blocks():
    decision = map_h11_prediction_to_preview(_prediction(0.9, config_hash="sha256:other"))
    assert decision.signal is AutoPreviewSignal.AUTO_PREVIEW_SIGNAL_UNKNOWN_BLOCKED
    assert decision.reason is H11AdapterReason.CONFIG_HASH_MISMATCH


def test_disagreement_abstains_before_threshold():
    decision = map_h11_prediction_to_preview(_prediction(0.9, probs=(0.95, 0.50, 0.90)))
    assert decision.signal is AutoPreviewSignal.AUTO_PREVIEW_SIGNAL_HOLD
    assert decision.reason is H11AdapterReason.EXPERT_DISAGREEMENT_ABSTAIN


def test_uncertainty_abstains_before_threshold():
    decision = map_h11_prediction_to_preview(_prediction(0.9, uncertainty=0.20))
    assert decision.signal is AutoPreviewSignal.AUTO_PREVIEW_SIGNAL_HOLD
    assert decision.reason is H11AdapterReason.MODEL_UNCERTAINTY_ABSTAIN


def test_buy_sell_hold_thresholds():
    buy = map_h11_prediction_to_preview(_prediction(0.58))
    assert buy.signal is AutoPreviewSignal.AUTO_PREVIEW_SIGNAL_BUY
    sell = map_h11_prediction_to_preview(_prediction(0.42))
    assert sell.signal is AutoPreviewSignal.AUTO_PREVIEW_SIGNAL_SELL
    hold = map_h11_prediction_to_preview(_prediction(0.50))
    assert hold.signal is AutoPreviewSignal.AUTO_PREVIEW_SIGNAL_HOLD
    assert hold.reason is H11AdapterReason.INSIDE_NO_TRADE_BAND


def test_adapter_never_emits_operator_labels():
    import app.services.h11_preview_adapter as module

    source = open(module.__file__, encoding="utf-8").read()
    for forbidden in ('"ENTRY_BUY"', '"ENTRY_SELL"'):
        assert forbidden not in source


def test_adapter_version_pinning():
    from app.strategies.h11_regime_moe import H11_V2_CONFIG_HASH

    v2_pred = _prediction(0.60, probs=(0.60,), config_hash=H11_V2_CONFIG_HASH)
    v2_pred = H11Prediction(**{**v2_pred.__dict__, "expert_weights": (1.0,)})

    pinned_v2 = map_h11_prediction_to_preview(v2_pred, expected_config_hash=H11_V2_CONFIG_HASH)
    assert pinned_v2.signal is AutoPreviewSignal.AUTO_PREVIEW_SIGNAL_BUY

    default_pin_v1 = map_h11_prediction_to_preview(v2_pred)
    assert default_pin_v1.signal is AutoPreviewSignal.AUTO_PREVIEW_SIGNAL_UNKNOWN_BLOCKED
    assert default_pin_v1.reason is H11AdapterReason.CONFIG_HASH_MISMATCH
