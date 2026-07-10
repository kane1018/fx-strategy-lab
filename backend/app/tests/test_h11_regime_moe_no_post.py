"""H-11 MoE research layer tests (no-POST, synthetic data only)."""

from __future__ import annotations

import numpy as np
import pytest

from app.strategies.h11_regime_moe import (
    N_EXPERT_FEATURES,
    N_EXPERTS,
    N_REGIME_AXES,
    PREDICTION_HORIZON_BARS,
    H11BlockReason,
    H11PredictionStatus,
    chronological_split,
    compute_features,
    directional_labels,
    predict_h11,
    train_h11_model,
)


def _synthetic_market(n: int = 2000, seed: int = 7):
    rng = np.random.default_rng(seed)
    drift = np.where(np.arange(n) % 400 < 200, 0.0002, -0.0002)
    log_close = np.cumsum(rng.normal(drift, 0.001))
    close = 150.0 * np.exp(log_close)
    spread_noise = np.abs(rng.normal(0.0, 0.02, n))
    high = close + spread_noise
    low = close - spread_noise
    open_ = np.roll(close, 1)
    open_[0] = close[0]
    hour = np.arange(n) % 24
    wide = (rng.random(n) < 0.05).astype(int)
    return open_, high, low, close, hour, wide


def _trained_parameters():
    open_, high, low, close, hour, wide = _synthetic_market()
    features = compute_features(open_, high, low, close, hour, wide)
    labels = directional_labels(close)
    return train_h11_model(features, labels), features


def test_labels_horizon_and_ties():
    close = np.array([1.0] * 30 + [2.0] * 30)
    labels = directional_labels(close)
    assert labels[10] == 1.0  # close(10+24)=2.0 > 1.0 => up label
    assert np.isnan(labels[0])  # close(24)=1.0 tie => excluded
    assert np.isnan(labels[-PREDICTION_HORIZON_BARS:]).all()
    flat = directional_labels(np.ones(60))
    assert np.isnan(flat[: 60 - PREDICTION_HORIZON_BARS]).all()  # ties excluded


def test_features_shapes_and_eligibility():
    open_, high, low, close, hour, wide = _synthetic_market(1200)
    features = compute_features(open_, high, low, close, hour, wide)
    assert features.expert_features.shape == (1200, N_EXPERTS, N_EXPERT_FEATURES)
    assert features.regime_axes.shape == (1200, N_REGIME_AXES)
    assert not features.eligible[:100].any()  # lookback not yet satisfied
    assert features.eligible.sum() > 500


def test_chronological_split_has_purge_gap():
    train_idx, valid_idx = chronological_split(1000)
    assert train_idx.max() < 700 - 1  # purge removed tail
    assert valid_idx.min() >= 700 + 24  # embargo respected
    assert valid_idx.min() - train_idx.max() >= 48


def test_training_is_deterministic():
    params_a, _ = _trained_parameters()
    params_b, _ = _trained_parameters()
    assert params_a.expert_weights == params_b.expert_weights
    assert params_a.router_weights == params_b.router_weights


def test_prediction_contract_coherence():
    params, features = _trained_parameters()
    rows = np.flatnonzero(features.eligible)[-50:]
    for row in rows:
        pred = predict_h11(params, features.expert_features[row], features.regime_axes[row])
        assert pred.prediction_status is H11PredictionStatus.OK
        assert 0.0 <= pred.p_up <= 1.0
        assert abs(pred.p_up + pred.p_down - 1.0) <= 1e-6
        assert len(pred.expert_probabilities) == N_EXPERTS
        assert len(pred.expert_weights) == N_EXPERTS
        assert abs(sum(pred.expert_weights) - 1.0) <= 1e-6
        assert all(w >= 0.0 for w in pred.expert_weights)
        assert pred.model_uncertainty >= 0.0


def test_untrained_model_is_blocked():
    pred = predict_h11(None, np.zeros((N_EXPERTS, N_EXPERT_FEATURES)), np.zeros(N_REGIME_AXES))
    assert pred.prediction_status is H11PredictionStatus.BLOCKED
    assert H11BlockReason.MODEL_NOT_TRAINED.value in pred.block_reasons
    assert pred.p_up is None


def test_fail_closed_on_bad_inputs():
    params, features = _trained_parameters()
    row = int(np.flatnonzero(features.eligible)[-1])
    good_x = features.expert_features[row]
    good_a = features.regime_axes[row]

    nan_x = good_x.copy()
    nan_x[0, 0] = np.nan
    assert predict_h11(params, nan_x, good_a).prediction_status is H11PredictionStatus.BLOCKED

    out_a = good_a.copy()
    out_a[0] = 9.0  # beyond z-score clip => out-of-domain regime
    pred = predict_h11(params, good_x, out_a)
    assert pred.prediction_status is H11PredictionStatus.BLOCKED
    assert H11BlockReason.OUT_OF_DOMAIN_REGIME_AXIS.value in pred.block_reasons

    bad_shape = predict_h11(params, good_x[:, :2], good_a)
    assert bad_shape.prediction_status is H11PredictionStatus.BLOCKED


def test_no_trade_labels_in_module():
    import app.strategies.h11_regime_moe as module

    source = open(module.__file__, encoding="utf-8").read()
    for forbidden in ("ENTRY_BUY", "ENTRY_SELL", "BUY_CANDIDATE", "SELL_CANDIDATE"):
        assert forbidden not in source


def test_insufficient_training_rows_raises():
    open_, high, low, close, hour, wide = _synthetic_market(600)
    features = compute_features(open_, high, low, close, hour, wide)
    labels = directional_labels(close)
    with pytest.raises(ValueError):
        train_h11_model(features, labels)


def test_mixture_beats_coin_flip_on_synthetic_validation():
    """Sanity only (synthetic regime-switching data): Brier <= 0.26. Not edge evidence."""

    params, features = _trained_parameters()
    open_, high, low, close, hour, wide = _synthetic_market()
    labels = directional_labels(close)
    _, valid_idx = chronological_split(len(labels))
    rows = valid_idx[features.eligible[valid_idx] & np.isfinite(labels[valid_idx])]
    errors = []
    for row in rows:
        pred = predict_h11(params, features.expert_features[row], features.regime_axes[row])
        if pred.prediction_status is H11PredictionStatus.OK:
            errors.append((pred.p_up - labels[row]) ** 2)
    assert len(errors) > 100
    assert float(np.mean(errors)) <= 0.26
