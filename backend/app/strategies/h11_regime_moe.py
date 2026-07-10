"""H-11 Regime-Adaptive Mixture-of-Experts directional probability model (no-POST).

Research layer ONLY. Implements the frozen spec
``docs/STRATEGY_H11_SPEC_FREEZE_DRAFT_NO_POST_20260711.md``
(config_hash sha256:7bff1ee4b8427a67111f289211bca5d654f1ae38bc3670bd1592a3ba9790e4a1).

This module outputs directional probabilities and safe status labels only.
It never produces trade-candidate labels or operator-owned entry/hold labels,
and never touches network, broker, credentials, or POST paths.
NaN / Inf / out-of-range / normalization failure => prediction_status=BLOCKED
with a safe block_reason (fail-closed).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

import numpy as np
import pandas as pd

H11_CONFIG_HASH = "sha256:7bff1ee4b8427a67111f289211bca5d654f1ae38bc3670bd1592a3ba9790e4a1"

# Frozen spec constants (spec freeze doc §1-§5). Not runtime-configurable.
PREDICTION_HORIZON_BARS = 24
MAX_FEATURE_LOOKBACK_BARS = 120
ZSCORE_WINDOW_BARS = 500
ZSCORE_CLIP = 4.0
PROBABILITY_NORMALIZATION_TOLERANCE = 1e-6
PURGE_BARS = 24
EMBARGO_BARS = 24
TRAIN_FRACTION = 0.70
L2_LAMBDA = 1.0
TRAIN_ITERATIONS = 500
TRAIN_LEARNING_RATE = 0.1

EXPERT_NAMES = ("TREND_CONTINUATION", "MEAN_REVERSION", "BREAKOUT_CONTINUATION")
N_EXPERTS = 3
N_EXPERT_FEATURES = 3
N_REGIME_AXES = 5


class H11PredictionStatus(str, Enum):
    OK = "OK"
    BLOCKED = "BLOCKED"


class H11BlockReason(str, Enum):
    MODEL_NOT_TRAINED = "MODEL_NOT_TRAINED"
    INSUFFICIENT_LOOKBACK = "INSUFFICIENT_LOOKBACK"
    NON_FINITE_FEATURE = "NON_FINITE_FEATURE"
    OUT_OF_DOMAIN_REGIME_AXIS = "OUT_OF_DOMAIN_REGIME_AXIS"
    PROBABILITY_OUT_OF_RANGE = "PROBABILITY_OUT_OF_RANGE"
    NORMALIZATION_FAILURE = "NORMALIZATION_FAILURE"
    INVALID_INPUT_SHAPE = "INVALID_INPUT_SHAPE"


@dataclass(frozen=True)
class H11Prediction:
    """Safe prediction contract (preregistration §3). No trade labels."""

    p_up: float | None
    p_down: float | None
    expert_probabilities: tuple[float, ...] | None
    expert_weights: tuple[float, ...] | None
    model_uncertainty: float | None
    prediction_status: H11PredictionStatus
    block_reasons: tuple[str, ...] = ()
    config_hash: str = H11_CONFIG_HASH


def _blocked(*reasons: H11BlockReason) -> H11Prediction:
    return H11Prediction(
        p_up=None,
        p_down=None,
        expert_probabilities=None,
        expert_weights=None,
        model_uncertainty=None,
        prediction_status=H11PredictionStatus.BLOCKED,
        block_reasons=tuple(reason.value for reason in reasons),
    )


def _rolling_mean(values: np.ndarray, window: int) -> np.ndarray:
    # NaN-tolerant: a window containing NaN yields NaN, later full windows recover.
    return pd.Series(values).rolling(window, min_periods=window).mean().to_numpy()


def _rolling_std(values: np.ndarray, window: int) -> np.ndarray:
    return pd.Series(values).rolling(window, min_periods=window).std(ddof=0).to_numpy()


def _rolling_zscore(values: np.ndarray, window: int = ZSCORE_WINDOW_BARS) -> np.ndarray:
    mean = _rolling_mean(values, window)
    std = _rolling_std(values, window)
    with np.errstate(divide="ignore", invalid="ignore"):
        z = (values - mean) / std
    z[~np.isfinite(z)] = np.nan
    return np.clip(z, -ZSCORE_CLIP, ZSCORE_CLIP)


def _rolling_max(values: np.ndarray, window: int) -> np.ndarray:
    return pd.Series(values).rolling(window, min_periods=window).max().to_numpy()


def _rolling_min(values: np.ndarray, window: int) -> np.ndarray:
    return pd.Series(values).rolling(window, min_periods=window).min().to_numpy()


def _atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, window: int) -> np.ndarray:
    prev_close = np.roll(close, 1)
    prev_close[0] = np.nan
    tr = np.maximum(high - low, np.maximum(np.abs(high - prev_close), np.abs(low - prev_close)))
    return _rolling_mean(tr, window)


def _rsi(close: np.ndarray, window: int = 14) -> np.ndarray:
    delta = np.diff(close, prepend=np.nan)
    gain = np.where(delta > 0, delta, 0.0)
    loss = np.where(delta < 0, -delta, 0.0)
    avg_gain = _rolling_mean(gain, window)
    avg_loss = _rolling_mean(loss, window)
    with np.errstate(divide="ignore", invalid="ignore"):
        rs = avg_gain / avg_loss
        rsi = 100.0 - 100.0 / (1.0 + rs)
    rsi = np.where(np.isfinite(rsi), rsi, np.where(avg_gain > 0, 100.0, 50.0))
    rsi[: window] = np.nan
    return rsi


@dataclass(frozen=True)
class H11FeatureMatrix:
    """Per-timestamp features. NaN rows are ineligible (fail-closed)."""

    expert_features: np.ndarray  # (n, N_EXPERTS, N_EXPERT_FEATURES)
    regime_axes: np.ndarray  # (n, N_REGIME_AXES)
    eligible: np.ndarray  # (n,) bool — all features finite & lookback satisfied


def compute_features(
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    hour_jst: np.ndarray,
    spread_wide: np.ndarray,
) -> H11FeatureMatrix:
    """Frozen feature set (spec §2). ``hour_jst`` int 0-23; ``spread_wide`` 0/1."""

    n = len(close)
    if not (len(open_) == len(high) == len(low) == len(hour_jst) == len(spread_wide) == n):
        raise ValueError("input arrays must share length")

    log_close = np.log(close)
    ret_24 = log_close - np.roll(log_close, PREDICTION_HORIZON_BARS)
    ret_24[:PREDICTION_HORIZON_BARS] = np.nan
    ret_120 = log_close - np.roll(log_close, MAX_FEATURE_LOOKBACK_BARS)
    ret_120[:MAX_FEATURE_LOOKBACK_BARS] = np.nan
    sma_24 = _rolling_mean(close, 24)
    sma_120 = _rolling_mean(close, 120)
    atr_14 = _atr(high, low, close, 14)
    atr_24 = _atr(high, low, close, 24)
    atr_96 = _atr(high, low, close, 96)

    trend = np.stack(
        [
            _rolling_zscore(ret_24),
            _rolling_zscore(ret_120),
            _rolling_zscore(close - sma_120),
        ],
        axis=1,
    )

    boll_mid = _rolling_mean(close, 20)
    boll_std = _rolling_std(close, 20)
    with np.errstate(divide="ignore", invalid="ignore"):
        boll_pos = (close - boll_mid) / (2.0 * boll_std)
    boll_pos[~np.isfinite(boll_pos)] = np.nan
    mean_rev = np.stack(
        [
            _rolling_zscore(close - sma_24),
            _rolling_zscore(_rsi(close)),
            np.clip(boll_pos, -ZSCORE_CLIP, ZSCORE_CLIP),
        ],
        axis=1,
    )

    with np.errstate(divide="ignore", invalid="ignore"):
        compression = atr_14 / atr_96
    compression[~np.isfinite(compression)] = np.nan
    prior_high = np.roll(_rolling_max(high, 24), 1)
    prior_low = np.roll(_rolling_min(low, 24), 1)
    prior_high[0] = np.nan
    prior_low[0] = np.nan
    with np.errstate(divide="ignore", invalid="ignore"):
        break_up = (close - prior_high) / atr_24
        break_dn = (close - prior_low) / atr_24
    breakout_dist = np.where(break_up > 0, break_up, np.where(break_dn < 0, break_dn, 0.0))
    breakout_dist = np.where(
        np.isfinite(break_up) & np.isfinite(break_dn), breakout_dist, np.nan
    )
    broke = (breakout_dist != 0.0) & np.isfinite(breakout_dist)
    bars_since = np.full(n, np.nan)
    last = -1
    for i in range(n):
        if broke[i]:
            last = i
        if last >= 0:
            bars_since[i] = min(i - last, 96)
    breakout = np.stack(
        [
            _rolling_zscore(compression),
            np.clip(breakout_dist, -ZSCORE_CLIP, ZSCORE_CLIP),
            _rolling_zscore(bars_since),
        ],
        axis=1,
    )

    expert_features = np.stack([trend, mean_rev, breakout], axis=1)

    # Regime axes (spec §2 note): trend z / vol z / compression / session / liquidity.
    session = np.where(hour_jst < 9, 2.0, np.where(hour_jst < 16, 0.0, 1.0)) - 1.0
    regime_axes = np.stack(
        [
            _rolling_zscore(np.abs(close - sma_120)),
            _rolling_zscore(atr_24),
            _rolling_zscore(compression),
            session,
            spread_wide.astype(float),
        ],
        axis=1,
    )

    eligible = np.isfinite(expert_features).all(axis=(1, 2)) & np.isfinite(regime_axes).all(
        axis=1
    )
    return H11FeatureMatrix(
        expert_features=expert_features, regime_axes=regime_axes, eligible=eligible
    )


def directional_labels(close: np.ndarray) -> np.ndarray:
    """label=1 if close(t+24)>close(t), 0 if <, NaN for tie/undefined (spec §1)."""

    future = np.roll(close, -PREDICTION_HORIZON_BARS)
    labels = np.where(future > close, 1.0, np.where(future < close, 0.0, np.nan))
    labels[-PREDICTION_HORIZON_BARS:] = np.nan
    return labels


@dataclass(frozen=True)
class H11ModelParameters:
    """Trained parameters. expert_weights: (N_EXPERTS, N_EXPERT_FEATURES+1);
    router_weights: (N_EXPERTS, N_REGIME_AXES+1). Bias is the last column."""

    expert_weights: tuple[tuple[float, ...], ...]
    router_weights: tuple[tuple[float, ...], ...]
    config_hash: str = H11_CONFIG_HASH


def _sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(x, -30.0, 30.0)))


def _fit_logistic(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Deterministic L2 logistic regression via fixed-iteration gradient descent."""

    xb = np.hstack([x, np.ones((len(x), 1))])
    w = np.zeros(xb.shape[1])
    for _ in range(TRAIN_ITERATIONS):
        p = _sigmoid(xb @ w)
        grad = xb.T @ (p - y) / len(y) + L2_LAMBDA * w / len(y)
        w -= TRAIN_LEARNING_RATE * grad
    return w


def chronological_split(n: int) -> tuple[np.ndarray, np.ndarray]:
    """70/30 chronological split with purge+embargo gap (spec §3). Returns index arrays."""

    split = int(n * TRAIN_FRACTION)
    train_end = max(split - PURGE_BARS, 0)
    valid_start = min(split + EMBARGO_BARS, n)
    return np.arange(0, train_end), np.arange(valid_start, n)


def train_h11_model(features: H11FeatureMatrix, labels: np.ndarray) -> H11ModelParameters:
    """Fit 3 expert logistics then the softmax router on training rows only."""

    usable = features.eligible & np.isfinite(labels)
    idx_train, _ = chronological_split(len(labels))
    rows = idx_train[usable[idx_train]]
    if len(rows) < ZSCORE_WINDOW_BARS:
        raise ValueError("insufficient eligible training rows")
    y = labels[rows]

    expert_w = []
    expert_p = np.zeros((len(rows), N_EXPERTS))
    for e in range(N_EXPERTS):
        w = _fit_logistic(features.expert_features[rows, e, :], y)
        expert_w.append(w)
        xb = np.hstack([features.expert_features[rows, e, :], np.ones((len(rows), 1))])
        expert_p[:, e] = _sigmoid(xb @ w)

    # Router: gradient descent on mixture log loss w.r.t. softmax weights.
    axes = np.hstack([features.regime_axes[rows], np.ones((len(rows), 1))])
    router = np.zeros((N_EXPERTS, axes.shape[1]))
    for _ in range(TRAIN_ITERATIONS):
        logits = axes @ router.T
        logits -= logits.max(axis=1, keepdims=True)
        weights = np.exp(logits)
        weights /= weights.sum(axis=1, keepdims=True)
        mix = (weights * expert_p).sum(axis=1)
        mix = np.clip(mix, 1e-9, 1.0 - 1e-9)
        residual = (mix - y) / (mix * (1.0 - mix))
        grad_w = weights * (expert_p - mix[:, None]) * residual[:, None]
        grad = grad_w.T @ axes / len(rows) + L2_LAMBDA * router / len(rows)
        router -= TRAIN_LEARNING_RATE * grad

    return H11ModelParameters(
        expert_weights=tuple(tuple(map(float, w)) for w in expert_w),
        router_weights=tuple(tuple(map(float, w)) for w in router),
    )


def predict_h11(
    parameters: H11ModelParameters | None,
    expert_features_row: np.ndarray,
    regime_axes_row: np.ndarray,
) -> H11Prediction:
    """One-timestamp inference under the frozen contract. Fail-closed on any anomaly."""

    if parameters is None:
        return _blocked(H11BlockReason.MODEL_NOT_TRAINED)
    if expert_features_row.shape != (N_EXPERTS, N_EXPERT_FEATURES) or regime_axes_row.shape != (
        N_REGIME_AXES,
    ):
        return _blocked(H11BlockReason.INVALID_INPUT_SHAPE)
    if not np.isfinite(expert_features_row).all():
        return _blocked(H11BlockReason.NON_FINITE_FEATURE)
    if not np.isfinite(regime_axes_row).all() or np.abs(regime_axes_row).max() > ZSCORE_CLIP:
        return _blocked(H11BlockReason.OUT_OF_DOMAIN_REGIME_AXIS)

    expert_p = []
    for e in range(N_EXPERTS):
        w = np.asarray(parameters.expert_weights[e])
        xb = np.append(expert_features_row[e], 1.0)
        expert_p.append(float(_sigmoid(np.array([xb @ w]))[0]))
    router = np.asarray(parameters.router_weights)
    logits = router @ np.append(regime_axes_row, 1.0)
    logits -= logits.max()
    weights = np.exp(logits)
    total = weights.sum()
    if not math.isfinite(total) or total <= 0.0:
        return _blocked(H11BlockReason.NORMALIZATION_FAILURE)
    weights = weights / total

    p_up = float(np.dot(weights, expert_p))
    p_down = 1.0 - p_up
    if not all(math.isfinite(p) and 0.0 <= p <= 1.0 for p in [p_up, p_down, *expert_p]):
        return _blocked(H11BlockReason.PROBABILITY_OUT_OF_RANGE)
    if abs(p_up + p_down - 1.0) > PROBABILITY_NORMALIZATION_TOLERANCE:
        return _blocked(H11BlockReason.NORMALIZATION_FAILURE)
    if abs(float(weights.sum()) - 1.0) > PROBABILITY_NORMALIZATION_TOLERANCE or (
        weights < 0.0
    ).any():
        return _blocked(H11BlockReason.NORMALIZATION_FAILURE)

    uncertainty = float(np.dot(weights, (np.asarray(expert_p) - p_up) ** 2))
    return H11Prediction(
        p_up=p_up,
        p_down=p_down,
        expert_probabilities=tuple(expert_p),
        expert_weights=tuple(float(w) for w in weights),
        model_uncertainty=uncertainty,
        prediction_status=H11PredictionStatus.OK,
    )
