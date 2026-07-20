from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from app.services import h11_v4_gmo_signal_preview as preview
from app.shadow.gmo_public import Candle, GmoPublicError


def _generation() -> SimpleNamespace:
    return SimpleNamespace(
        digest="sha256:" + "2" * 64,
        generation_label="H11_AUTO_30M_20260717_G013",
        strategy_version="SHORT_V1",
        signal_config_hash="sha256:test-model",
        selected_horizon="30m",
        symbol="USD_JPY",
        quantity_units=1000,
        actual_post_authorized=False,
        protection_contract_hash="sha256:protection",
        broker_capability_evidence_hash="sha256:capability",
    )


def _prerequisite() -> object:
    return preview._PreviewPrerequisite(
        token=preview._PREREQUISITE_TOKEN,
        reviewed_files_digest="sha256:" + "1" * 64,
        generation=_generation(),
    )


def _frame(end: datetime, count: int = 40) -> pd.DataFrame:
    times = [end - timedelta(minutes=index) for index in reversed(range(count))]
    return pd.DataFrame(
        {
            "time_utc": times,
            "open": [150.0] * count,
            "high": [150.1] * count,
            "low": [149.9] * count,
            "close": [150.0] * count,
        }
    )


class _Client:
    calls: list[tuple[object, ...]] = []
    candles: list[Candle] = []

    def __init__(self) -> None:
        self.client = SimpleNamespace(close=lambda: None)

    def fetch_candles(self, *args: object, **kwargs: object) -> list[Candle]:
        self.calls.append((*args, kwargs))
        return self.candles


def _arrange(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, now: datetime) -> None:
    monkeypatch.setattr(preview, "_load_prerequisite", lambda **_kwargs: _prerequisite())
    monkeypatch.setattr(
        preview,
        "_execution_policy",
        lambda _generation: SimpleNamespace(entry_time_allowed=lambda **_kwargs: True),
    )
    model = tmp_path / preview.G013_PREVIEW_MODEL_RELATIVE
    model.parent.mkdir(parents=True)
    model.write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(
        preview,
        "_artifact_from_captured_bytes",
        lambda _value: SimpleNamespace(config_hash="sha256:test-model"),
    )


@pytest.mark.parametrize(("probability", "expected"), [(0.42, True), (0.50, False), (0.58, True)])
def test_preview_returns_only_non_authorizing_boolean_report(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    probability: float,
    expected: bool,
) -> None:
    now = datetime(2026, 7, 20, 5, 30, 20, tzinfo=UTC)
    slot = now.replace(second=0, microsecond=0) - timedelta(minutes=1)
    _arrange(monkeypatch, tmp_path, now)
    monkeypatch.setattr(preview, "predict_short_model", lambda *_args: probability)
    _Client.calls = []
    _Client.candles = [
        Candle(
            time=row.time_utc.isoformat(),
            open=row.open,
            high=row.high,
            low=row.low,
            close=row.close,
        )
        for row in _frame(slot).itertuples(index=False)
    ]
    report = preview.run_g013_signal_preview(
        repository=tmp_path,
        now_utc=now,
        client_factory=_Client,
    ).to_safe_dict()
    assert report["candidate_actionable"] is expected
    assert len(_Client.calls) == 1
    assert _Client.calls[0][:3] == ("USD_JPY", "M1", 0)
    assert _Client.calls[0][3] == {"price_type": "BID", "date": "20260720"}
    assert set(report) == {
        "status", "candidate_actionable", "signal_fresh", "signal_age_seconds",
        "public_get_count", "direction_exposed", "probability_exposed", "price_exposed",
        "raw_response_retained", "credential_read", "private_api_read", "broker_write",
        "broker_post_count", "authorization_granted", "activation_permit_issued",
        "actual_generation_consumed", "formal_signal_authorized",
    }
    assert all(
        report[key] is False
        for key in (
            "direction_exposed", "probability_exposed", "price_exposed",
            "raw_response_retained", "credential_read", "private_api_read", "broker_write",
            "authorization_granted", "activation_permit_issued",
            "actual_generation_consumed", "formal_signal_authorized",
        )
    )
    assert "BUY" not in json.dumps(report) and "SELL" not in json.dumps(report)


def test_same_slot_is_consumed_before_network_and_cannot_retry(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    now = datetime(2026, 7, 20, 5, 31, 20, tzinfo=UTC)
    slot = now.replace(second=0, microsecond=0) - timedelta(minutes=1)
    _arrange(monkeypatch, tmp_path, now)
    monkeypatch.setattr(preview, "predict_short_model", lambda *_args: 0.50)

    class _Failing(_Client):
        def fetch_candles(self, *args: object, **kwargs: object) -> list[Candle]:
            state = preview._safe_state_root(repository=tmp_path, prerequisite=_prerequisite())
            assert list(state.glob("slot-*-attempted.json"))
            self.calls.append((*args, kwargs))
            raise GmoPublicError("unsafe provider detail")

    _Failing.calls = []
    with pytest.raises(preview.G013SignalPreviewError, match="PUBLIC_GET_FAILED_NO_RETRY"):
        preview.run_g013_signal_preview(repository=tmp_path, now_utc=now, client_factory=_Failing)
    with pytest.raises(preview.G013SignalPreviewError, match="SLOT_ALREADY_ATTEMPTED"):
        preview.run_g013_signal_preview(repository=tmp_path, now_utc=now, client_factory=_Failing)
    assert len(_Failing.calls) == 1
    assert slot.isoformat() in next(
        (tmp_path / preview.G013_PREVIEW_STATE_RELATIVE).rglob("slot-*-attempted.json")
    ).read_text(encoding="utf-8")


def test_provider_detail_is_not_retained_in_exception_context(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    now = datetime(2026, 7, 20, 5, 31, 20, tzinfo=UTC)
    _arrange(monkeypatch, tmp_path, now)

    class _RawFailing(_Client):
        def fetch_candles(self, *args: object, **kwargs: object) -> list[Candle]:
            raise GmoPublicError("RAW_PRICE_150.123")

    with pytest.raises(preview.G013SignalPreviewError) as captured:
        preview.run_g013_signal_preview(
            repository=tmp_path,
            now_utc=now,
            client_factory=_RawFailing,
        )
    assert str(captured.value) == "G013_PREVIEW_PUBLIC_GET_FAILED_NO_RETRY"
    assert captured.value.__context__ is None


def test_later_slot_is_a_distinct_observation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    first = datetime(2026, 7, 20, 5, 32, 20, tzinfo=UTC)
    _arrange(monkeypatch, tmp_path, first)
    monkeypatch.setattr(preview, "predict_short_model", lambda *_args: 0.50)
    _Client.calls = []
    for now in (first, first + timedelta(minutes=1)):
        slot = now.replace(second=0, microsecond=0) - timedelta(minutes=1)
        _Client.candles = [
            Candle(
                time=row.time_utc.isoformat(),
                open=row.open,
                high=row.high,
                low=row.low,
                close=row.close,
            )
            for row in _frame(slot).itertuples(index=False)
        ]
        preview.run_g013_signal_preview(repository=tmp_path, now_utc=now, client_factory=_Client)
    assert len(_Client.calls) == 2


def test_active_public_bar_is_filtered_and_utc_date_is_used(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    now = datetime(2026, 7, 19, 15, 30, 20, tzinfo=UTC)
    slot = now.replace(second=0, microsecond=0) - timedelta(minutes=1)
    _arrange(monkeypatch, tmp_path, now)
    monkeypatch.setattr(preview, "predict_short_model", lambda *_args: 0.50)
    rows = _frame(slot)
    rows = pd.concat((rows, _frame(slot + timedelta(minutes=1), count=1)), ignore_index=True)
    _Client.calls = []
    _Client.candles = [
        Candle(
            time=row.time_utc.isoformat(),
            open=row.open,
            high=row.high,
            low=row.low,
            close=row.close,
        )
        for row in rows.itertuples(index=False)
    ]
    report = preview.run_g013_signal_preview(
        repository=tmp_path, now_utc=now, client_factory=_Client
    )
    assert report.to_safe_dict()["candidate_actionable"] is False
    assert _Client.calls[0][3]["date"] == "20260719"


def test_model_input_change_after_slot_claim_fails_closed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    now = datetime(2026, 7, 20, 5, 33, 20, tzinfo=UTC)
    slot = now.replace(second=0, microsecond=0) - timedelta(minutes=1)
    _arrange(monkeypatch, tmp_path, now)
    model_path = tmp_path / preview.G013_PREVIEW_MODEL_RELATIVE

    class _Mutating(_Client):
        def fetch_candles(self, *args: object, **kwargs: object) -> list[Candle]:
            model_path.write_text("changed\n", encoding="utf-8")
            return self.candles

    _Mutating.candles = [
        Candle(
            time=row.time_utc.isoformat(),
            open=row.open,
            high=row.high,
            low=row.low,
            close=row.close,
        )
        for row in _frame(slot).itertuples(index=False)
    ]
    with pytest.raises(preview.G013SignalPreviewError, match="MODEL_INPUT_CHANGED"):
        preview.run_g013_signal_preview(repository=tmp_path, now_utc=now, client_factory=_Mutating)


def test_model_artifact_is_built_from_the_exact_captured_bytes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    now = datetime(2026, 7, 20, 5, 34, 20, tzinfo=UTC)
    _arrange(monkeypatch, tmp_path, now)
    model_path = tmp_path / preview.G013_PREVIEW_MODEL_RELATIVE
    model_path.write_bytes(b"captured-model-bytes")
    captured: list[bytes] = []
    monkeypatch.setattr(
        preview,
        "_artifact_from_captured_bytes",
        lambda value: captured.append(value) or SimpleNamespace(config_hash="sha256:test-model"),
    )
    preview._read_model_input(
        repository=tmp_path,
        expected_model_config_hash="sha256:test-model",
    )
    assert captured == [b"captured-model-bytes"]


def test_remote_window_requires_exact_contiguous_31_bars() -> None:
    slot = datetime(2026, 7, 20, 5, 34, tzinfo=UTC)
    valid = _frame(slot, count=31)
    result = preview._exact_remote_m1_window(remote=valid, slot=slot)
    assert len(result) == 31
    gap = _frame(slot, count=32).drop(index=15).reset_index(drop=True)
    with pytest.raises(preview.G013SignalPreviewError, match="REMOTE_WINDOW_INVALID"):
        preview._exact_remote_m1_window(remote=gap, slot=slot)


@pytest.mark.parametrize("probability", [float("nan"), float("inf")])
def test_invalid_model_output_fails_not_false(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, probability: float
) -> None:
    now = datetime(2026, 7, 20, 5, 34, 20, tzinfo=UTC)
    slot = now.replace(second=0, microsecond=0) - timedelta(minutes=1)
    _arrange(monkeypatch, tmp_path, now)
    monkeypatch.setattr(preview, "predict_short_model", lambda *_args: probability)
    _Client.candles = [
        Candle(
            time=row.time_utc.isoformat(),
            open=row.open,
            high=row.high,
            low=row.low,
            close=row.close,
        )
        for row in _frame(slot).itertuples(index=False)
    ]
    with pytest.raises(preview.G013SignalPreviewError, match="MODEL_INVALID"):
        preview.run_g013_signal_preview(repository=tmp_path, now_utc=now, client_factory=_Client)


def test_publication_delay_and_entry_window_block_before_state_and_network(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(preview, "_load_prerequisite", lambda **_kwargs: _prerequisite())
    monkeypatch.setattr(
        preview,
        "_execution_policy",
        lambda _generation: SimpleNamespace(entry_time_allowed=lambda **_kwargs: False),
    )
    _Client.calls = []
    with pytest.raises(preview.G013SignalPreviewError, match="ENTRY_WINDOW_BLOCKED"):
        preview.run_g013_signal_preview(
            repository=tmp_path,
            now_utc=datetime(2026, 7, 20, 5, 35, 5, tzinfo=UTC),
            client_factory=_Client,
        )
    assert not (tmp_path / preview.G013_PREVIEW_STATE_RELATIVE).exists()
    assert _Client.calls == []


def test_preview_source_has_no_actual_authorization_or_private_dependencies() -> None:
    source = Path(preview.__file__).read_text(encoding="utf-8")
    forbidden = (
        "load_completed_preparation_evidence", "refresh_g013_formal_canary_input",
        "ActivationPermit", "GmoFxActual", "cancelOrders", "closeOrder", "latestExecutions",
        "openPositions", "activeOrders", "Keychain", "Pushover", "SMTP", "while ", "sleep(",
    )
    assert all(token not in source for token in forbidden)


def test_preview_reviewed_digest_closes_local_imports_without_duplicates() -> None:
    from h11_v4_reviewed_digest import REVIEWED_FILES

    assert len(REVIEWED_FILES) == len(set(REVIEWED_FILES))
    assert {
        "backend/app/services/__init__.py",
        "backend/app/services/h11_v4_gmo_signal_preview.py",
        "backend/app/shadow/__init__.py",
        "backend/app/shadow/gmo_public.py",
        "backend/app/shadow/models.py",
        "backend/app/h11_manual/__init__.py",
        "backend/app/h11_manual/contracts.py",
        "backend/app/h11_manual/short_model.py",
    }.issubset(REVIEWED_FILES)
