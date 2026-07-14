"""Deterministic low-capacity M1 direction model for 10m and 30m research signals.

The artifact is trained once from a chronological development slice and then
frozen. Training and inference are local numerical operations only. This module
does not fetch data or expose any order/execution concept.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from app.h11_manual.contracts import Horizon

MODEL_VERSION = "H11_MANUAL_SHORT_LOGISTIC_V1"
FEATURE_NAMES = (
    "ret_1_norm",
    "ret_5_norm",
    "ret_10_norm",
    "ret_30_norm",
    "sma_10_distance_norm",
    "sma_30_distance_norm",
    "volatility_ratio",
    "session_sin",
    "session_cos",
)
MIN_TRAINING_ROWS = 2_000
PURGE_BARS = 30
TRAIN_FRACTION = 0.70
L2_LAMBDA = 1.0
ITERATIONS = 500
LEARNING_RATE = 0.08


@dataclass(frozen=True)
class ShortModelArtifact:
    version: str
    trained_at_utc: str
    development_cutoff_utc: str
    formal_start_utc: str
    data_hash: str
    feature_names: tuple[str, ...]
    feature_mean: tuple[float, ...]
    feature_scale: tuple[float, ...]
    weights_10m: tuple[float, ...]
    weights_30m: tuple[float, ...]
    config_hash: str

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + ".tmp")
        temp.write_text(json.dumps(asdict(self), indent=2, sort_keys=True))
        temp.replace(path)

    @classmethod
    def load(cls, path: Path) -> ShortModelArtifact:
        raw = json.loads(path.read_text())
        for key in (
            "feature_names",
            "feature_mean",
            "feature_scale",
            "weights_10m",
            "weights_30m",
        ):
            raw[key] = tuple(raw[key])
        artifact = cls(**raw)
        if artifact.version != MODEL_VERSION or artifact.feature_names != FEATURE_NAMES:
            raise ValueError("unsupported short-model artifact")
        if artifact.config_hash != _artifact_hash(asdict(artifact), omit_hash=True):
            raise ValueError("short-model artifact hash mismatch")
        return artifact


def _artifact_hash(payload: dict[str, object], *, omit_hash: bool = False) -> str:
    canonical = dict(payload)
    if omit_hash:
        canonical.pop("config_hash", None)
    encoded = json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _sigmoid(values: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(values, -30.0, 30.0)))


def _fit_logistic(features: np.ndarray, labels: np.ndarray) -> np.ndarray:
    design = np.hstack([features, np.ones((len(features), 1))])
    weights = np.zeros(design.shape[1])
    for _ in range(ITERATIONS):
        probability = _sigmoid(design @ weights)
        gradient = design.T @ (probability - labels) / len(labels)
        gradient[:-1] += L2_LAMBDA * weights[:-1] / len(labels)
        weights -= LEARNING_RATE * gradient
    return weights


def compute_short_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Return causal features indexed exactly like the input M1 frame."""

    close = pd.to_numeric(frame["close"], errors="coerce").astype(float)
    log_close = np.log(close)
    ret_1 = log_close.diff(1)
    vol_30 = ret_1.rolling(30, min_periods=30).std(ddof=0).replace(0.0, np.nan)
    vol_10 = ret_1.rolling(10, min_periods=10).std(ddof=0)
    sma_10 = close.rolling(10, min_periods=10).mean()
    sma_30 = close.rolling(30, min_periods=30).mean()
    timestamp = pd.to_datetime(frame["time_utc"], utc=True, errors="coerce")
    minute_jst = ((timestamp.dt.hour + 9) % 24) * 60 + timestamp.dt.minute
    angle = 2.0 * math.pi * minute_jst / 1_440.0
    features = pd.DataFrame(
        {
            "ret_1_norm": ret_1 / vol_30,
            "ret_5_norm": log_close.diff(5) / (vol_30 * math.sqrt(5)),
            "ret_10_norm": log_close.diff(10) / (vol_30 * math.sqrt(10)),
            "ret_30_norm": log_close.diff(30) / (vol_30 * math.sqrt(30)),
            "sma_10_distance_norm": (close / sma_10 - 1.0) / vol_30,
            "sma_30_distance_norm": (close / sma_30 - 1.0) / vol_30,
            "volatility_ratio": vol_10 / vol_30 - 1.0,
            "session_sin": np.sin(angle),
            "session_cos": np.cos(angle),
        },
        index=frame.index,
    )
    return features.replace([np.inf, -np.inf], np.nan).clip(-8.0, 8.0)


def _labels(close: pd.Series, bars: int) -> pd.Series:
    future = close.shift(-bars)
    label = pd.Series(np.nan, index=close.index, dtype=float)
    label[future > close] = 1.0
    label[future < close] = 0.0
    return label


def _data_hash(frame: pd.DataFrame) -> str:
    columns = frame[["time_utc", "open", "high", "low", "close"]].copy()
    encoded = columns.to_csv(index=False, float_format="%.8f").encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def train_short_model(frame: pd.DataFrame, *, now: datetime | None = None) -> ShortModelArtifact:
    required = {"time_utc", "open", "high", "low", "close"}
    if not required.issubset(frame.columns):
        raise ValueError("M1 frame is missing required columns")
    ordered = frame.sort_values("time_utc").drop_duplicates("time_utc").reset_index(drop=True)
    features = compute_short_features(ordered)
    close = pd.to_numeric(ordered["close"], errors="coerce").astype(float)
    labels = {10: _labels(close, 10), 30: _labels(close, 30)}
    split = int(len(ordered) * TRAIN_FRACTION)
    training_end = split - PURGE_BARS
    common = features.notna().all(axis=1)
    common &= labels[10].notna() & labels[30].notna()
    rows = np.flatnonzero(common.to_numpy() & (np.arange(len(ordered)) < training_end))
    if len(rows) < MIN_TRAINING_ROWS:
        raise ValueError("insufficient M1 rows to train short model")
    raw = features.iloc[rows].to_numpy(dtype=float)
    mean = raw.mean(axis=0)
    scale = raw.std(axis=0)
    scale[scale < 1e-9] = 1.0
    normalized = (raw - mean) / scale
    weights: dict[int, np.ndarray] = {}
    for bars in (10, 30):
        weights[bars] = _fit_logistic(normalized, labels[bars].iloc[rows].to_numpy())

    cutoff = pd.to_datetime(ordered.loc[split - 1, "time_utc"], utc=True).isoformat()
    formal_start = pd.to_datetime(ordered.loc[split, "time_utc"], utc=True).isoformat()
    payload: dict[str, object] = {
        "version": MODEL_VERSION,
        "trained_at_utc": (now or datetime.now(UTC)).astimezone(UTC).isoformat(timespec="seconds"),
        "development_cutoff_utc": cutoff,
        "formal_start_utc": formal_start,
        "data_hash": _data_hash(ordered.iloc[:split]),
        "feature_names": FEATURE_NAMES,
        "feature_mean": tuple(map(float, mean)),
        "feature_scale": tuple(map(float, scale)),
        "weights_10m": tuple(map(float, weights[10])),
        "weights_30m": tuple(map(float, weights[30])),
    }
    payload["config_hash"] = _artifact_hash(payload)
    return ShortModelArtifact(**payload)


def predict_short_model(
    artifact: ShortModelArtifact,
    frame: pd.DataFrame,
    row: int,
    horizon: Horizon,
) -> float:
    if horizon not in (Horizon.MINUTES_10, Horizon.MINUTES_30):
        raise ValueError("short model only supports 10m and 30m")
    features = compute_short_features(frame).iloc[row].to_numpy(dtype=float)
    if not np.isfinite(features).all():
        raise ValueError("short-model features are not eligible")
    mean = np.asarray(artifact.feature_mean)
    scale = np.asarray(artifact.feature_scale)
    normalized = (features - mean) / scale
    weights = np.asarray(
        artifact.weights_10m if horizon is Horizon.MINUTES_10 else artifact.weights_30m
    )
    probability = float(_sigmoid(np.array([np.append(normalized, 1.0) @ weights]))[0])
    if not math.isfinite(probability) or not 0.0 <= probability <= 1.0:
        raise ValueError("short-model probability is invalid")
    return probability
