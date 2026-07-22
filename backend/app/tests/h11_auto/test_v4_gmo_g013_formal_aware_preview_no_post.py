from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from app.services import h11_v4_gmo_formal_aware_preview as subject
from app.shadow.models import Candle


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


def test_non_actionable_m1_does_not_fetch_h1(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
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
    monkeypatch.setattr(subject, "load_candle_csv", lambda _path: _h1_frame(end=datetime(2026, 7, 21, 4, 0, tzinfo=UTC)))
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
