"""H-11 prediction -> AUTO_PREVIEW_SIGNAL_* deterministic adapter (no-POST).

Implements the frozen mapping of the staged live policy §2 and spec freeze doc §4:
safety block -> abstention -> direction threshold, in that priority. The output is a
non-prescriptive preview label only. It is not a permission, not an order intent,
and never produces operator-owned ENTRY_BUY / ENTRY_SELL / HOLD labels.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.services.gmo_paper_auto_cycle_runner import AutoPreviewSignal
from app.strategies.h11_regime_moe import (
    H11_CONFIG_HASH,
    H11Prediction,
    H11PredictionStatus,
)

# Frozen thresholds (spec freeze doc §4). Not runtime-configurable.
BUY_PROBABILITY_THRESHOLD = 0.58
SELL_PROBABILITY_THRESHOLD = 0.42
MAX_EXPERT_DISAGREEMENT = 0.40
MAX_MODEL_UNCERTAINTY = 0.15


class H11AdapterReason(str, Enum):
    PREDICTION_BLOCKED = "PREDICTION_BLOCKED"
    CONFIG_HASH_MISMATCH = "CONFIG_HASH_MISMATCH"
    EXPERT_DISAGREEMENT_ABSTAIN = "EXPERT_DISAGREEMENT_ABSTAIN"
    MODEL_UNCERTAINTY_ABSTAIN = "MODEL_UNCERTAINTY_ABSTAIN"
    BUY_THRESHOLD_MET = "BUY_THRESHOLD_MET"
    SELL_THRESHOLD_MET = "SELL_THRESHOLD_MET"
    INSIDE_NO_TRADE_BAND = "INSIDE_NO_TRADE_BAND"


@dataclass(frozen=True)
class H11PreviewDecision:
    signal: AutoPreviewSignal
    reason: H11AdapterReason


def map_h11_prediction_to_preview(
    prediction: H11Prediction, expected_config_hash: str = H11_CONFIG_HASH
) -> H11PreviewDecision:
    """Priority order is frozen: safety block -> abstention -> threshold.

    ``expected_config_hash`` pins the adapter to one frozen spec version; a
    prediction from any other version is blocked, never silently accepted.
    """

    if (
        prediction.prediction_status is not H11PredictionStatus.OK
        or prediction.p_up is None
        or prediction.expert_probabilities is None
        or prediction.model_uncertainty is None
    ):
        return H11PreviewDecision(
            AutoPreviewSignal.AUTO_PREVIEW_SIGNAL_UNKNOWN_BLOCKED,
            H11AdapterReason.PREDICTION_BLOCKED,
        )
    if prediction.config_hash != expected_config_hash:
        return H11PreviewDecision(
            AutoPreviewSignal.AUTO_PREVIEW_SIGNAL_UNKNOWN_BLOCKED,
            H11AdapterReason.CONFIG_HASH_MISMATCH,
        )

    probs = prediction.expert_probabilities
    disagreement = max(abs(a - b) for a in probs for b in probs)
    if disagreement > MAX_EXPERT_DISAGREEMENT:
        return H11PreviewDecision(
            AutoPreviewSignal.AUTO_PREVIEW_SIGNAL_HOLD,
            H11AdapterReason.EXPERT_DISAGREEMENT_ABSTAIN,
        )
    if prediction.model_uncertainty > MAX_MODEL_UNCERTAINTY:
        return H11PreviewDecision(
            AutoPreviewSignal.AUTO_PREVIEW_SIGNAL_HOLD,
            H11AdapterReason.MODEL_UNCERTAINTY_ABSTAIN,
        )

    if prediction.p_up >= BUY_PROBABILITY_THRESHOLD:
        return H11PreviewDecision(
            AutoPreviewSignal.AUTO_PREVIEW_SIGNAL_BUY, H11AdapterReason.BUY_THRESHOLD_MET
        )
    if prediction.p_up <= SELL_PROBABILITY_THRESHOLD:
        return H11PreviewDecision(
            AutoPreviewSignal.AUTO_PREVIEW_SIGNAL_SELL, H11AdapterReason.SELL_THRESHOLD_MET
        )
    return H11PreviewDecision(
        AutoPreviewSignal.AUTO_PREVIEW_SIGNAL_HOLD, H11AdapterReason.INSIDE_NO_TRADE_BAND
    )
