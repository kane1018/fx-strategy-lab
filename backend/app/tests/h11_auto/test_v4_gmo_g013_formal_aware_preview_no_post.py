from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from app.h11_auto.v4_actual_preparation_guard import (
    V4ActualPreparationGuardError,
)
from app.services import h11_v4_gmo_formal_aware_preview as subject
from app.services.h11_v4_gmo_signal_preview import G013SignalPreviewError
from app.shadow.models import Candle
from scripts import h11_auto_v4_g013_formal_aware_observer as observer


def _h1_frame(*, end: datetime, count: int = 25) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "time_utc": [end - timedelta(hours=index) for index in range(count - 1, -1, -1)],
            "open": [160.0] * count,
            "high": [160.1] * count,
            "low": [159.9] * count,
            "close": [160.0] * count,
        }
    )


def _candles(frame: pd.DataFrame) -> list[Candle]:
    return [
        Candle(
            time=str(row.time_utc),
            open=float(row.open),
            high=float(row.high),
            low=float(row.low),
            close=float(row.close),
        )
        for row in frame.itertuples(index=False)
    ]


def test_non_actionable_m1_does_not_fetch_h1(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        subject,
        "run_g013_signal_preview",
        lambda **_kwargs: SimpleNamespace(candidate_actionable=False),
    )
    monkeypatch.setattr(
        subject,
        "GmoPublicMarketDataClient",
        lambda: pytest.fail("H1 Public client must not be created"),
    )

    result = subject.run_g013_formal_aware_preview(
        repository=tmp_path, now_utc=datetime(2026, 7, 22, 5, 1, tzinfo=UTC)
    )

    assert result.to_safe_dict() == {
        "status": "G013_FORMAL_AWARE_PREVIEW_NON_ACTIONABLE",
        "candidate_actionable": False,
        "formal_candidate_actionable": False,
        "public_get_count": 1,
        "broker_post_count": 0,
        "private_api_read": False,
        "credential_read": False,
        "broker_write": False,
        "permit_issued": False,
        "actual_generation_consumed": False,
        "direction_exposed": False,
        "probability_exposed": False,
        "price_exposed": False,
        "raw_market_data_exposed": False,
        "order_sheet_exposed": False,
        "challenge_exposed": False,
        "notification_attempted": False,
        "local_sound_attempted": False,
        "observer_contract": "ONE_COMPLETED_SLOT_PER_INVOCATION",
        "next_action": "WAIT_NEXT_COMPLETED_SLOT",
    }


def test_candidate_fetches_one_h1_and_keeps_input_in_memory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    now = datetime(2026, 7, 22, 5, 1, tzinfo=UTC)
    h1 = _h1_frame(end=datetime(2026, 7, 22, 4, 0, tzinfo=UTC))
    calls: list[str] = []

    class FakeClient:
        def __init__(self) -> None:
            self.client = SimpleNamespace(close=lambda: calls.append("close"))

        def fetch_candles(self, symbol: str, interval: str, **_kwargs: object) -> list[Candle]:
            assert symbol == "USD_JPY"
            calls.append(interval)
            return _candles(h1)

    monkeypatch.setattr(
        subject,
        "run_g013_signal_preview",
        lambda **_kwargs: SimpleNamespace(candidate_actionable=True),
    )
    monkeypatch.setattr(subject, "GmoPublicMarketDataClient", FakeClient)
    local_paths: list[Path] = []

    def load_local(path: Path) -> pd.DataFrame:
        local_paths.append(path)
        return _h1_frame(end=datetime(2026, 7, 21, 4, 0, tzinfo=UTC))

    monkeypatch.setattr(subject, "load_candle_csv", load_local)
    sleeps: list[float] = []

    result = subject.run_g013_formal_aware_preview(
        repository=tmp_path, now_utc=now, sleeper=sleeps.append
    )

    assert result.status == "G013_FORMAL_AWARE_PREVIEW_FORMAL_ACTIONABLE"
    assert result.candidate_actionable is True
    assert result.formal_candidate_actionable is True
    assert result.public_get_count == 2
    assert calls == ["H1", "close"]
    assert sleeps == [subject.G013_PUBLIC_CANDLE_REQUEST_GAP_SECONDS]
    assert local_paths == [
        tmp_path / "backend/market_data/h11_manual/usdjpy_h1_bid.csv"
    ]


def test_h1_failure_is_terminal_without_broker_surface(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    class FailingClient:
        def __init__(self) -> None:
            self.client = SimpleNamespace(close=lambda: None)

        def fetch_candles(self, *_args: object, **_kwargs: object) -> list[Candle]:
            raise subject.GmoPublicError("sanitized")

    monkeypatch.setattr(
        subject,
        "run_g013_signal_preview",
        lambda **_kwargs: SimpleNamespace(candidate_actionable=True),
    )
    monkeypatch.setattr(subject, "GmoPublicMarketDataClient", FailingClient)

    with pytest.raises(subject.G013FormalAwarePreviewError, match="H1_REFRESH_FAILED_NO_RETRY"):
        subject.run_g013_formal_aware_preview(
            repository=tmp_path, now_utc=datetime(2026, 7, 22, 5, 1, tzinfo=UTC)
        )


def test_stale_completed_h1_is_not_formal_actionable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    now = datetime(2026, 7, 22, 5, 1, tzinfo=UTC)
    stale = _h1_frame(end=datetime(2026, 7, 22, 3, 0, tzinfo=UTC))

    class FakeClient:
        def __init__(self) -> None:
            self.client = SimpleNamespace(close=lambda: None)

        def fetch_candles(self, *_args: object, **_kwargs: object) -> list[Candle]:
            return _candles(stale)

    monkeypatch.setattr(
        subject,
        "run_g013_signal_preview",
        lambda **_kwargs: SimpleNamespace(candidate_actionable=True),
    )
    monkeypatch.setattr(subject, "GmoPublicMarketDataClient", FakeClient)
    monkeypatch.setattr(subject, "load_candle_csv", lambda _path: stale)

    with pytest.raises(
        subject.G013FormalAwarePreviewError,
        match="G013_FORMAL_AWARE_H1_INPUT_INVALID",
    ):
        subject.run_g013_formal_aware_preview(
            repository=tmp_path,
            now_utc=now,
            sleeper=lambda _seconds: None,
        )


def test_h1_failure_then_same_slot_does_not_start_second_h1(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    m1_calls = 0
    h1_clients = 0

    def preview(**_kwargs: object) -> SimpleNamespace:
        nonlocal m1_calls
        m1_calls += 1
        if m1_calls == 1:
            return SimpleNamespace(candidate_actionable=True)
        raise G013SignalPreviewError(
            "G013_PREVIEW_SLOT_ALREADY_ATTEMPTED"
        )

    class FailingClient:
        def __init__(self) -> None:
            nonlocal h1_clients
            h1_clients += 1
            self.client = SimpleNamespace(close=lambda: None)

        def fetch_candles(self, *_args: object, **_kwargs: object) -> list[Candle]:
            raise subject.GmoPublicError("sanitized")

    monkeypatch.setattr(subject, "run_g013_signal_preview", preview)
    monkeypatch.setattr(subject, "GmoPublicMarketDataClient", FailingClient)

    with pytest.raises(subject.G013FormalAwarePreviewError):
        subject.run_g013_formal_aware_preview(
            repository=tmp_path,
            now_utc=datetime(2026, 7, 22, 5, 1, tzinfo=UTC),
        )
    with pytest.raises(
        G013SignalPreviewError,
        match="G013_PREVIEW_SLOT_ALREADY_ATTEMPTED",
    ):
        subject.run_g013_formal_aware_preview(
            repository=tmp_path,
            now_utc=datetime(2026, 7, 22, 5, 1, tzinfo=UTC),
        )

    assert m1_calls == 2
    assert h1_clients == 1


def test_source_does_not_depend_on_actual_canary_or_private_surfaces() -> None:
    source = Path(subject.__file__).read_text()
    forbidden = (
        "h11_auto_v4_g013_actual_canary",
        "h11_v4_gmo_g013_canary",
        "GmoFxBroker",
        "Keychain",
        "getpass",
    )
    assert all(token not in source for token in forbidden)


def test_current_generation_binding_is_inherited_before_conditional_h1(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[Path] = []

    def bound_preview(**kwargs: object) -> SimpleNamespace:
        calls.append(Path(kwargs["repository"]))
        return SimpleNamespace(candidate_actionable=False)

    monkeypatch.setattr(subject, "run_g013_signal_preview", bound_preview)
    monkeypatch.setattr(
        subject,
        "GmoPublicMarketDataClient",
        lambda: pytest.fail("H1 Public client must not be created"),
    )

    result = subject.run_g013_formal_aware_preview(
        repository=tmp_path,
        now_utc=datetime(2026, 7, 29, 7, 30, tzinfo=UTC),
    )

    assert calls == [tmp_path]
    assert result.formal_candidate_actionable is False


@pytest.mark.parametrize(
    "status",
    [
        "G013_PREVIEW_GENERATION_INVALID",
        "G013_PREVIEW_REVIEW_BOUNDARY_INVALID",
        "G013_PREVIEW_SLOT_ALREADY_ATTEMPTED",
    ],
)
def test_prerequisite_or_same_slot_failure_never_starts_h1(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    status: str,
) -> None:
    monkeypatch.setattr(
        subject,
        "run_g013_signal_preview",
        lambda **_kwargs: (_ for _ in ()).throw(
                G013SignalPreviewError(status)
        ),
    )
    monkeypatch.setattr(
        subject,
        "GmoPublicMarketDataClient",
        lambda: pytest.fail("H1 Public client must not be created"),
    )

    with pytest.raises(G013SignalPreviewError, match=status):
        subject.run_g013_formal_aware_preview(
            repository=tmp_path,
            now_utc=datetime(2026, 7, 29, 7, 30, tzinfo=UTC),
        )


def test_observer_has_no_notification_or_local_sound_surface() -> None:
    source = Path(observer.__file__).read_text(encoding="utf-8")

    assert "subprocess" not in source
    assert "afplay" not in source
    assert "Pushover" not in source
    assert "SMTP" not in source


def test_observer_returns_fixed_safe_error_without_retry(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        observer,
        "run_g013_formal_aware_preview",
        lambda **_kwargs: (_ for _ in ()).throw(
            subject.G013FormalAwarePreviewError(
                "G013_FORMAL_AWARE_H1_REFRESH_FAILED_NO_RETRY",
                public_get_count=2,
                candidate_actionable=True,
            )
        ),
    )
    monkeypatch.setattr(
        "sys.argv",
        ["formal-aware-preview", "--repository", str(tmp_path)],
    )

    assert observer.main() == observer.FAILURE_EXIT_CODE
    report = json.loads(capsys.readouterr().err)
    assert report["status"] == "G013_FORMAL_AWARE_H1_REFRESH_FAILED_NO_RETRY"
    assert report["candidate_actionable"] is True
    assert report["candidate_actionable_known"] is True
    assert report["public_get_count"] == 2
    assert report["public_get_count_known"] is True
    assert report["broker_post_count"] == 0
    assert report["broker_write"] is False
    assert report["notification_attempted"] is False
    assert report["local_sound_attempted"] is False
    assert report["next_action"] == "STOP_NO_RETRY"


def test_observer_distinguishes_wait_and_actionable_exit_codes(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        "sys.argv",
        ["formal-aware-preview", "--repository", str(tmp_path)],
    )
    monkeypatch.setattr(
        observer,
        "run_g013_formal_aware_preview",
        lambda **_kwargs: (_ for _ in ()).throw(
            G013SignalPreviewError("G013_PREVIEW_PUBLICATION_PENDING")
        ),
    )
    assert observer.main() == observer.WAIT_EXIT_CODE
    waiting = json.loads(capsys.readouterr().err)
    assert waiting["next_action"] == "WAIT_NEXT_WAKE"
    assert waiting["public_get_count"] == 0

    monkeypatch.setattr(
        observer,
        "run_g013_formal_aware_preview",
        lambda **_kwargs: (_ for _ in ()).throw(
            G013SignalPreviewError("G013_PREVIEW_SLOT_ALREADY_ATTEMPTED")
        ),
    )
    assert observer.main() == observer.WAIT_EXIT_CODE
    already_observed = json.loads(capsys.readouterr().err)
    assert already_observed["next_action"] == "WAIT_NEXT_WAKE"
    assert already_observed["public_get_count"] == 0

    monkeypatch.setattr(
        observer,
        "run_g013_formal_aware_preview",
        lambda **_kwargs: subject.G013FormalAwarePreviewReport(
            status="G013_FORMAL_AWARE_PREVIEW_FORMAL_ACTIONABLE",
            candidate_actionable=True,
            formal_candidate_actionable=True,
            public_get_count=2,
        ),
    )
    assert observer.main() == observer.ACTIONABLE_EXIT_CODE
    actionable = json.loads(capsys.readouterr().out)
    assert actionable["next_action"] == "STOP_FORMAL_ACTIONABLE"


def test_observer_classifies_clean_main_terminal_and_unknown_failures(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        "sys.argv",
        ["formal-aware-preview", "--repository", str(tmp_path)],
    )
    monkeypatch.setattr(
        observer,
        "run_g013_formal_aware_preview",
        lambda **_kwargs: (_ for _ in ()).throw(
            V4ActualPreparationGuardError("V4_PREPARATION_GIT_GATE_FAILED")
        ),
    )
    assert observer.main() == observer.FAILURE_EXIT_CODE
    clean_main = json.loads(capsys.readouterr().err)
    assert clean_main["next_action"] == "STOP_REQUIRES_CLEAN_MAIN"
    assert clean_main["public_get_count"] == 0

    monkeypatch.setattr(
        observer,
        "run_g013_formal_aware_preview",
        lambda **_kwargs: (_ for _ in ()).throw(
            G013SignalPreviewError("G013_PREVIEW_GENERATION_INVALID")
        ),
    )
    assert observer.main() == observer.FAILURE_EXIT_CODE
    terminal = json.loads(capsys.readouterr().err)
    assert terminal["next_action"] == "STOP_NO_RETRY"
    assert terminal["public_get_count"] is None
    assert terminal["public_get_count_known"] is False

    monkeypatch.setattr(
        observer,
        "run_g013_formal_aware_preview",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("provider details")),
    )
    assert observer.main() == observer.FAILURE_EXIT_CODE
    unknown = json.loads(capsys.readouterr().err)
    assert unknown["status"] == "G013_FORMAL_AWARE_PREVIEW_FAILED_SAFE"
    assert unknown["next_action"] == "STOP_UNKNOWN"
