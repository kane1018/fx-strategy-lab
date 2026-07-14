"""Synthetic-only tests for the local manual-signal model and labels."""

from __future__ import annotations

from datetime import UTC, datetime

import numpy as np
import pandas as pd

from app.h11_manual.contracts import Direction, Horizon, map_probability
from app.h11_manual.short_model import (
    FEATURE_NAMES,
    ShortModelArtifact,
    predict_short_model,
    train_short_model,
)


def synthetic_m1(rows: int = 4_000, seed: int = 17) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    returns = rng.normal(0.000001, 0.00012, rows)
    close = 155.0 * np.exp(np.cumsum(returns))
    open_ = np.roll(close, 1)
    open_[0] = close[0]
    width = np.abs(rng.normal(0.006, 0.002, rows))
    return pd.DataFrame(
        {
            "time_utc": pd.date_range("2026-01-01", periods=rows, freq="min", tz="UTC").astype(str),
            "open": open_,
            "high": np.maximum(open_, close) + width,
            "low": np.minimum(open_, close) - width,
            "close": close,
        }
    )


def test_probability_labels_are_direct_and_fail_closed() -> None:
    assert map_probability(0.58) is Direction.BUY
    assert map_probability(0.42) is Direction.SELL
    assert map_probability(0.50) is Direction.NO_TRADE
    assert map_probability(None) is Direction.UNKNOWN
    assert map_probability(0.80, blocked=True) is Direction.UNKNOWN


def test_short_model_is_deterministic_and_serializable(tmp_path) -> None:
    frame = synthetic_m1()
    now = datetime(2026, 2, 1, tzinfo=UTC)
    first = train_short_model(frame, now=now)
    second = train_short_model(frame, now=now)
    assert first == second
    assert first.feature_names == FEATURE_NAMES
    assert first.config_hash.startswith("sha256:")

    path = tmp_path / "artifact.json"
    first.save(path)
    loaded = ShortModelArtifact.load(path)
    assert loaded == first
    for horizon in (Horizon.MINUTES_10, Horizon.MINUTES_30):
        probability = predict_short_model(loaded, frame, len(frame) - 1, horizon)
        assert 0.0 <= probability <= 1.0


def test_short_model_rejects_wrong_horizon() -> None:
    frame = synthetic_m1()
    artifact = train_short_model(frame)
    try:
        predict_short_model(artifact, frame, len(frame) - 1, Horizon.HOURS_24)
    except ValueError as error:
        assert "only supports" in str(error)
    else:
        raise AssertionError("24h must not use the short model")
