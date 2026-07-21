from __future__ import annotations

import json
import signal
import time
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from unittest.mock import MagicMock

import httpx
import pandas as pd
import pytest

from app.h11_auto.contracts import FormalHorizon, FormalSignal, SignalDecision
from app.h11_auto.v4_activation_preparation import V4ApprovedOperatorSelections
from app.h11_auto.v4_gmo_canary_activation import V4GmoCanaryIntent
from app.h11_manual.short_model import ShortModelArtifact
from app.services import h11_v4_gmo_formal_canary_source as source_module
from app.services import h11_v4_gmo_g013_canary as canary_module
from app.services.h11_v4_gmo_actual_adapter import V4GmoPrivateOutcome
from app.services.h11_v4_gmo_formal_canary_source import (
    G013_ATR_TIMEFRAME,
    G013_PUBLIC_CANDLE_REQUEST_GAP_SECONDS,
    V4GmoFormalCanarySourceError,
    build_g013_formal_canary_input,
    refresh_g013_formal_canary_input,
)
from app.services.h11_v4_gmo_public_preflight import (
    G013_MAXIMUM_ENTRY_SPREAD_PIPS,
    V4GmoG013PublicOperation,
    V4GmoG013PublicOperationLedger,
    V4GmoPublicPreflightError,
    g013_public_cycle_key,
    read_g013_final_quote_once,
)
from app.shadow.models import Candle


def _frame(*, end_utc: datetime, count: int, minutes: int) -> pd.DataFrame:
    times = [end_utc - timedelta(minutes=minutes * offset) for offset in range(count)]
    times.reverse()
    base = 160.0
    return pd.DataFrame(
        {
            "time_utc": [value.isoformat() for value in times],
            "open": [base + index * 0.001 for index in range(count)],
            "high": [base + index * 0.001 + 0.02 for index in range(count)],
            "low": [base + index * 0.001 - 0.02 for index in range(count)],
            "close": [base + index * 0.001 + 0.005 for index in range(count)],
        }
    )


def _artifact_stub() -> ShortModelArtifact:
    return cast(
        ShortModelArtifact,
        SimpleNamespace(
            config_hash=V4ApprovedOperatorSelections().signal_config_hash,
        ),
    )


def test_formal_canary_source_uses_frozen_30m_signal_and_completed_h1_atr(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime(2026, 7, 17, 3, 1, 30, tzinfo=UTC)
    monkeypatch.setattr(source_module, "predict_short_model", lambda *args: 0.61)
    result = build_g013_formal_canary_input(
        m1=_frame(end_utc=now - timedelta(seconds=90), count=40, minutes=1),
        h1=_frame(end_utc=now - timedelta(hours=1), count=25, minutes=60),
        artifact=_artifact_stub(),
        now_utc=now,
        public_candle_refresh_performed=True,
    )
    assert result.signal.decision is SignalDecision.BUY
    assert result.signal.probability_up.is_finite()
    assert result.signal.horizon.value == "30m"
    assert result.atr_timeframe == G013_ATR_TIMEFRAME
    assert result.frozen_atr_24 == Decimal("0.04")
    assert result.private_api_read is False
    assert result.credential_read is False
    assert result.broker_write is False


def test_formal_canary_source_blocks_stay_and_stale(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime(2026, 7, 17, 3, 1, 30, tzinfo=UTC)
    m1 = _frame(end_utc=now - timedelta(seconds=90), count=40, minutes=1)
    h1 = _frame(end_utc=now - timedelta(hours=1), count=25, minutes=60)
    monkeypatch.setattr(source_module, "predict_short_model", lambda *args: 0.50)
    with pytest.raises(V4GmoFormalCanarySourceError, match="SIGNAL_STAY"):
        build_g013_formal_canary_input(
            m1=m1,
            h1=h1,
            artifact=_artifact_stub(),
            now_utc=now,
            public_candle_refresh_performed=True,
        )
    monkeypatch.setattr(source_module, "predict_short_model", lambda *args: 0.61)
    with pytest.raises(V4GmoFormalCanarySourceError, match="SIGNAL_STALE"):
        build_g013_formal_canary_input(
            # 最新確定M1が6分(360s)前 = MAXIMUM_FORMAL_SIGNAL_AGE_SECONDS(300s)超でstale。
            m1=_frame(end_utc=now - timedelta(minutes=6), count=40, minutes=1),
            h1=h1,
            artifact=_artifact_stub(),
            now_utc=now,
            public_candle_refresh_performed=True,
        )


def test_formal_canary_source_rejects_active_m1_and_h1_bars(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime(2026, 7, 17, 3, 1, 30, tzinfo=UTC)
    monkeypatch.setattr(source_module, "predict_short_model", lambda *args: 0.61)
    with pytest.raises(V4GmoFormalCanarySourceError, match="M1_NOT_COMPLETED"):
        build_g013_formal_canary_input(
            m1=_frame(end_utc=now - timedelta(seconds=30), count=40, minutes=1),
            h1=_frame(end_utc=now - timedelta(hours=1), count=25, minutes=60),
            artifact=_artifact_stub(),
            now_utc=now,
            public_candle_refresh_performed=True,
        )
    with pytest.raises(V4GmoFormalCanarySourceError, match="H1_NOT_COMPLETED"):
        build_g013_formal_canary_input(
            m1=_frame(end_utc=now - timedelta(seconds=90), count=40, minutes=1),
            h1=_frame(end_utc=now - timedelta(minutes=30), count=25, minutes=60),
            artifact=_artifact_stub(),
            now_utc=now,
            public_candle_refresh_performed=True,
        )


def test_formal_refresh_claims_once_and_uses_completed_public_bars(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    now = datetime(2026, 7, 17, 3, 1, 30, tzinfo=UTC)
    m1_frame = _frame(
        end_utc=datetime(2026, 7, 17, 3, 0, tzinfo=UTC),
        count=40,
        minutes=1,
    )
    active_m1 = _frame(
        end_utc=datetime(2026, 7, 17, 3, 1, tzinfo=UTC),
        count=1,
        minutes=1,
    )
    m1_response = pd.concat((m1_frame, active_m1), ignore_index=True)
    h1_frame = _frame(
        end_utc=datetime(2026, 7, 17, 2, 0, tzinfo=UTC),
        count=25,
        minutes=60,
    )

    class _FakePublicClient:
        calls: list[str] = []

        def __init__(self) -> None:
            self.client = SimpleNamespace(close=lambda: None)

        def fetch_candles(
            self,
            symbol: str,
            interval: str,
            limit: int,
            *,
            price_type: str,
            date: str,
        ) -> list[Candle]:
            assert symbol == "USD_JPY"
            assert limit == 0
            assert price_type == "BID"
            assert date == "20260717"
            self.calls.append(interval)
            frame = m1_response if interval == "M1" else h1_frame
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

    repository_type = source_module.CandleRepository
    monkeypatch.setattr(source_module, "GmoPublicMarketDataClient", _FakePublicClient)
    captured_supplemental_h1_paths: list[tuple[Path, ...]] = []

    def _capturing_repository(
        root: Path, supplemental_h1_paths: tuple[Path, ...]
    ) -> object:
        # No default: if production regresses to CandleRepository(data_root)
        # (re-including the DEV/STAGE supplemental caches), the omitted keyword
        # raises TypeError here instead of a false-passing capture of ().
        captured_supplemental_h1_paths.append(supplemental_h1_paths)
        return repository_type(root, supplemental_h1_paths=supplemental_h1_paths)

    monkeypatch.setattr(source_module, "CandleRepository", _capturing_repository)
    monkeypatch.setattr(
        source_module.ShortModelArtifact,
        "load",
        staticmethod(lambda path: _artifact_stub()),
    )
    monkeypatch.setattr(source_module, "predict_short_model", lambda *args: 0.61)
    ledger = _public_ledger(tmp_path / "ledger")
    sleeps: list[float] = []
    result = refresh_g013_formal_canary_input(
        operation_ledger=ledger,
        data_root=tmp_path / "data",
        now_utc=now,
        sleeper=sleeps.append,
    )
    assert _FakePublicClient.calls == ["M1", "H1"]
    assert sleeps == [G013_PUBLIC_CANDLE_REQUEST_GAP_SECONDS]
    assert result.signal.observed_at_utc == datetime(2026, 7, 17, 3, 0, tzinfo=UTC)
    assert result.frozen_atr_24 == Decimal("0.04")
    # R2: the formal ATR basis excludes the development/stage supplemental H1
    # caches; only the official h1_bid.csv history participates.
    assert captured_supplemental_h1_paths == [()]
    persisted_m1 = pd.read_csv(tmp_path / "data" / "usdjpy_m1_bid.csv")
    assert pd.to_datetime(persisted_m1["time_utc"], utc=True).max() == pd.Timestamp(
        "2026-07-17T03:00:00Z"
    )
    with pytest.raises(V4GmoPublicPreflightError, match="ALREADY_ATTEMPTED"):
        refresh_g013_formal_canary_input(
            operation_ledger=ledger,
            data_root=tmp_path / "data",
            now_utc=now,
        )
    assert _FakePublicClient.calls == ["M1", "H1"]


def test_formal_m1_window_rejects_gap_duplicate_and_wrong_end_slot() -> None:
    now = datetime(2026, 7, 17, 3, 1, 30, tzinfo=UTC)
    slot = datetime(2026, 7, 17, 3, 0, tzinfo=UTC)

    def candles(frame: pd.DataFrame) -> list[Candle]:
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

    valid = _frame(end_utc=slot, count=31, minutes=1)
    _, window = source_module._fresh_exact_m1_window(
        candles=candles(valid), now_utc=now
    )
    assert len(window) == 31

    gap = _frame(end_utc=slot, count=32, minutes=1).drop(index=15).reset_index(drop=True)
    duplicate = pd.concat((valid, valid.tail(1)), ignore_index=True)
    wrong_end = _frame(end_utc=slot - timedelta(minutes=1), count=31, minutes=1)
    for invalid in (gap, duplicate, wrong_end):
        with pytest.raises(
            V4GmoFormalCanarySourceError, match="G013_FORMAL_M1_WINDOW_INVALID"
        ):
            source_module._fresh_exact_m1_window(
                candles=candles(invalid), now_utc=now
            )


@pytest.mark.parametrize(
    ("failed_interval", "expected_code", "expected_calls", "expected_sleeps"),
    [
        (
            "M1",
            "G013_PUBLIC_M1_CANDLE_REFRESH_FAILED_NO_RETRY",
            ["M1"],
            [],
        ),
        (
            "H1",
            "G013_PUBLIC_H1_CANDLE_REFRESH_FAILED_NO_RETRY",
            ["M1", "H1"],
            [G013_PUBLIC_CANDLE_REQUEST_GAP_SECONDS],
        ),
    ],
)
def test_formal_refresh_classifies_failed_interval_without_retry(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    failed_interval: str,
    expected_code: str,
    expected_calls: list[str],
    expected_sleeps: list[float],
) -> None:
    class _FailingPublicClient:
        calls: list[str] = []

        def __init__(self) -> None:
            self.client = SimpleNamespace(close=lambda: None)

        def fetch_candles(self, _symbol: str, interval: str, **_kwargs: object) -> list[Candle]:
            self.calls.append(interval)
            if interval == failed_interval:
                raise source_module.GmoPublicError("sanitized fake failure")
            return []

    monkeypatch.setattr(source_module, "GmoPublicMarketDataClient", _FailingPublicClient)
    sleeps: list[float] = []
    with pytest.raises(V4GmoFormalCanarySourceError, match=expected_code):
        refresh_g013_formal_canary_input(
            operation_ledger=_public_ledger(tmp_path / "ledger"),
            data_root=tmp_path / "data",
            now_utc=datetime(2026, 7, 20, 5, 0, tzinfo=UTC),
            sleeper=sleeps.append,
        )
    assert _FailingPublicClient.calls == expected_calls
    assert sleeps == expected_sleeps


def _quote_client(*, spread_pips: str) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.query == b""
        if request.url.path == "/public/v1/status":
            return httpx.Response(200, json={"status": 0, "data": {"status": "OPEN"}})
        assert request.url.path == "/public/v1/ticker"
        ask = 160 + float(spread_pips) * 0.01
        return httpx.Response(
            200,
            json={
                "status": 0,
                "data": [
                    {
                        "symbol": "USD_JPY",
                        "ask": f"{ask:.3f}",
                        "bid": "160.000",
                        "timestamp": "2026-07-17T03:00:00Z",
                        "status": "OPEN",
                    }
                ],
            },
        )

    return httpx.Client(transport=httpx.MockTransport(handler))


def _public_ledger(tmp_path: Path) -> V4GmoG013PublicOperationLedger:
    return V4GmoG013PublicOperationLedger(
        state_root=tmp_path,
        generation_digest="sha256:" + "a" * 64,
    )


def test_g013_final_quote_is_two_gets_and_accepts_exact_spread_limit(
    tmp_path: Path,
) -> None:
    client = _quote_client(spread_pips="0.5")
    quote = read_g013_final_quote_once(
        operation_ledger=_public_ledger(tmp_path),
        operation=V4GmoG013PublicOperation.REFERENCE_QUOTE,
        client=client,
        wall_clock=lambda: datetime(2026, 7, 17, 3, 0, 1, tzinfo=UTC),
    )
    assert quote.public_get_count == 2
    assert quote.spread_pips == G013_MAXIMUM_ENTRY_SPREAD_PIPS
    assert quote.market_open is True
    assert quote.quote_fresh is True
    assert quote.broker_post_count == 0
    client.close()


def test_g013_final_quote_blocks_spread_above_limit(tmp_path: Path) -> None:
    client = _quote_client(spread_pips="0.6")
    with pytest.raises(V4GmoPublicPreflightError, match="GATE_BLOCKED"):
        read_g013_final_quote_once(
            operation_ledger=_public_ledger(tmp_path),
            operation=V4GmoG013PublicOperation.REFERENCE_QUOTE,
            client=client,
            wall_clock=lambda: datetime(2026, 7, 17, 3, 0, 1, tzinfo=UTC),
        )
    client.close()


def test_g013_final_quote_must_remain_near_confirmed_reference() -> None:
    reference = SimpleNamespace(bid=Decimal("160.000"), ask=Decimal("160.005"))
    within = SimpleNamespace(bid=Decimal("160.045"), ask=Decimal("160.050"))
    canary_module._require_final_quote_near_reference(
        reference=reference,
        final=within,
        maximum_deviation_pips=Decimal("5.0"),
    )
    moved = SimpleNamespace(bid=Decimal("160.060"), ask=Decimal("160.065"))
    with pytest.raises(canary_module.V4GmoG013CanaryError, match="MOVED"):
        canary_module._require_final_quote_near_reference(
            reference=reference,
            final=moved,
            maximum_deviation_pips=Decimal("5.0"),
        )


def _exact_binding_session() -> SimpleNamespace:
    base = _fake_session()
    signal = base.formal_input.signal
    generation = SimpleNamespace(
        digest="sha256:" + "d" * 64,
        implementation_digest="sha256:" + "c" * 64,
        generation_label="H11_AUTO_30M_20260717_G013",
        strategy_version=signal.strategy_version,
        quantity_units=1_000,
        symbol="USD_JPY",
        adverse_slippage_allowance_pips="5.0",
        per_trade_loss_bound_jpy=5_000,
        maximum_unprotected_seconds=15,
    )
    reference = SimpleNamespace(
        bid=Decimal("160.000"),
        ask=Decimal("160.005"),
        observed_at_utc=datetime(2099, 1, 1, 0, 0, 59, tzinfo=UTC),
    )
    risk = SimpleNamespace(planned_loss_bound_jpy=4_500)
    sheet = canary_module.V4GmoG013OrderSheet(
        generation_label=generation.generation_label,
        strategy_version=generation.strategy_version,
        horizon=signal.horizon.value,
        symbol="USD_JPY",
        side=signal.decision.value,
        size=1_000,
        execution_type="MARKET",
        probability_up=format(signal.probability_up, "f"),
        formal_origin_utc=signal.observed_at_utc.isoformat(),
        formal_valid_until_utc=signal.valid_until_utc.isoformat(),
        frozen_atr_24="0.04",
        formal_input_provenance_digest="sha256:" + "e" * 64,
        atr_timeframe=G013_ATR_TIMEFRAME,
        stop_distance_rule="1.50 * frozen ATR(24) from actual average fill",
        take_profit_rule="1.50R from actual average fill",
        maximum_spread_pips="0.5",
        reference_bid="160",
        reference_ask="160.005",
        reference_quote_observed_at_utc=reference.observed_at_utc.isoformat(),
        maximum_reference_deviation_pips="5.0",
        planned_loss_bound_jpy=4_500,
        maximum_loss_per_trade_jpy=5_000,
        maximum_unprotected_seconds=15,
    )
    intent = V4GmoCanaryIntent(
        generation_digest=generation.digest,
        cycle_ref="b" * 64,
        side=signal.decision.value,
        exact_order_sheet_digest=sheet.digest,
    )
    return SimpleNamespace(
        generation=generation,
        formal_input=SimpleNamespace(
            signal=signal,
            frozen_atr_24=Decimal("0.04"),
            input_provenance_digest="sha256:" + "e" * 64,
            atr_timeframe=G013_ATR_TIMEFRAME,
        ),
        reference_quote=reference,
        risk=risk,
        order_sheet=sheet,
        intent=intent,
        challenge=SimpleNamespace(intent_digest=intent.digest),
    )


def test_g013_exact_order_sheet_is_rehashed_before_execution() -> None:
    session = _exact_binding_session()
    canary_module._require_exact_session_binding(session)
    session.order_sheet = replace(session.order_sheet, reference_bid="159.999")
    with pytest.raises(canary_module.V4GmoG013CanaryError, match="BINDING_MISMATCH"):
        canary_module._require_exact_session_binding(session)
    session = _exact_binding_session()
    session.formal_input.input_provenance_digest = "sha256:" + "0" * 64
    with pytest.raises(canary_module.V4GmoG013CanaryError, match="BINDING_MISMATCH"):
        canary_module._require_exact_session_binding(session)


def test_g013_review_digest_includes_formal_direction_adapter() -> None:
    from h11_v4_reviewed_digest import REVIEWED_FILES

    assert "backend/app/h11_auto/signal_adapter.py" in REVIEWED_FILES


def test_g013_prepermit_refresh_rechecks_implementation_digest(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    base = _exact_binding_session()
    session = canary_module.V4GmoG013PreparedSession(
        repository=tmp_path,
        generation=base.generation,
        formal_input=base.formal_input,
        store=object(),
        risk=base.risk,
        intent=base.intent,
        challenge=base.challenge,
        preparation_evidence=object(),
        public_operation_ledger=object(),
        reference_quote=base.reference_quote,
        order_sheet=base.order_sheet,
    )
    monkeypatch.setattr(canary_module, "require_clean_main", lambda **_kwargs: object())
    monkeypatch.setattr(
        canary_module,
        "reviewed_files_digest",
        lambda **_kwargs: "sha256:" + "f" * 64,
    )
    with pytest.raises(
        canary_module.V4GmoG013CanaryError,
        match="IMPLEMENTATION_CHANGED_BEFORE_PERMIT",
    ):
        canary_module._refresh_session_evidence_before_permit(session)


def test_g013_runtime_has_one_distinct_partial_remainder_cancel_path() -> None:
    source = Path(source_module.__file__).with_name("h11_v4_gmo_g013_canary.py")
    text = source.read_text(encoding="utf-8")
    assert "prepare_cancel_entry_remainder_plan" in text
    assert "perform_risk_reducing_once" in text
    assert "cancelOrders" not in text
    assert "retry" not in text.lower().replace("same_action_retry", "")


class _FakePath:
    def __init__(
        self,
        recoveries: list[str],
        *,
        market_outcome: V4GmoPrivateOutcome = V4GmoPrivateOutcome.ACCEPTED_SANITIZED,
        cancel_outcome: V4GmoPrivateOutcome = V4GmoPrivateOutcome.ACCEPTED_SANITIZED,
        protection_outcome: V4GmoPrivateOutcome = V4GmoPrivateOutcome.ACCEPTED_SANITIZED,
    ) -> None:
        self.recoveries = recoveries
        self.market_outcome = market_outcome
        self.cancel_outcome = cancel_outcome
        self.protection_outcome = protection_outcome
        self.calls: list[str] = []
        self.dead_man_store = SimpleNamespace(heartbeat=lambda **kwargs: None)
        self.store = SimpleNamespace(unknown_halt_latched=lambda: True)

    def reconcile_once_fixed(self, **kwargs: object) -> object:
        del kwargs
        self.calls.append("reconcile")
        return object()

    def record_canary_entry_preflight(self, **kwargs: object) -> None:
        del kwargs
        self.calls.append("preflight")

    def perform_market_once(self, **kwargs: object) -> V4GmoPrivateOutcome:
        del kwargs
        self.calls.append("market")
        return self.market_outcome

    def recover_pending_transport_and_carry_once(
        self, **kwargs: object
    ) -> tuple[SimpleNamespace, object]:
        del kwargs
        self.calls.append("recover")
        return SimpleNamespace(classification=self.recoveries.pop(0)), object()

    def prepare_cancel_entry_remainder_plan(self, **kwargs: object) -> tuple[object, object]:
        del kwargs
        self.calls.append("prepare_cancel")
        return object(), object()

    def perform_risk_reducing_once(self, **kwargs: object) -> V4GmoPrivateOutcome:
        del kwargs
        self.calls.append("cancel")
        return self.cancel_outcome

    def prepare_exact_protection_plan(self, **kwargs: object) -> tuple[SimpleNamespace, object]:
        del kwargs
        self.calls.append("prepare_oco")
        return SimpleNamespace(exact_filled_size=1_000), object()

    def perform_exact_protection_once(self, **kwargs: object) -> V4GmoPrivateOutcome:
        del kwargs
        self.calls.append("oco")
        return self.protection_outcome

    def confirm_exact_protection_once(self, **kwargs: object) -> None:
        del kwargs
        self.calls.append("confirm_oco")


def _fake_session() -> SimpleNamespace:
    selected = V4ApprovedOperatorSelections()
    signal = FormalSignal(
        strategy_version=selected.strategy_version,
        signal_config_hash=selected.signal_config_hash,
        horizon=FormalHorizon.MINUTES_30,
        observed_at_utc=datetime(2099, 1, 1, tzinfo=UTC),
        valid_until_utc=datetime(2099, 1, 1, 0, 30, tzinfo=UTC),
        decision=SignalDecision.BUY,
        probability_up=Decimal("0.61"),
    )
    return SimpleNamespace(
        formal_input=SimpleNamespace(signal=signal),
        intent=SimpleNamespace(cycle_ref="b" * 64, size=1_000),
        generation=object(),
        preparation_evidence=object(),
        public_operation_ledger=object(),
        reference_quote=SimpleNamespace(bid=Decimal("160.000"), ask=Decimal("160.005")),
        order_sheet=SimpleNamespace(maximum_reference_deviation_pips="5.0"),
    )


@pytest.mark.parametrize(
    ("recoveries", "expected_cancel_attempts"),
    (
        (["FILLED_UNPROTECTED", "FILLED_PROTECTED"], 0),
        (["MARKET_PARTIAL_PENDING", "FILLED_UNPROTECTED", "FILLED_PROTECTED"], 1),
    ),
)
def test_g013_orchestrator_uses_one_entry_optional_cancel_and_one_oco(
    monkeypatch: pytest.MonkeyPatch,
    recoveries: list[str],
    expected_cancel_attempts: int,
) -> None:
    path = _FakePath(recoveries.copy())
    binding = SimpleNamespace(
        coordinated_path=path,
        build_foreground_lifecycle_driver=lambda: SimpleNamespace(
            run_until_flat=lambda: SimpleNamespace(flat_reconciled=True)
        ),
    )
    monkeypatch.setattr(
        canary_module,
        "_execution_policy",
        lambda generation: SimpleNamespace(entry_time_allowed=lambda **kwargs: True),
    )
    monkeypatch.setattr(canary_module, "_require_exact_session_binding", lambda session: None)
    monkeypatch.setattr(
        canary_module,
        "read_g013_final_quote_once",
        lambda **kwargs: SimpleNamespace(bid=Decimal("160.000"), ask=Decimal("160.005")),
    )
    result = canary_module._run_bound_g013_canary(
        session=_fake_session(),
        binding=binding,
        on_protected=None,
        wall_clock=lambda: datetime(2099, 1, 1, 0, 1, tzinfo=UTC),
    )
    assert result.entry_post_attempt_count == 1
    assert result.cancel_post_attempt_count == expected_cancel_attempts
    assert result.protection_post_attempt_count == 1
    assert path.calls.count("market") == 1
    assert path.calls.count("cancel") == expected_cancel_attempts
    assert path.calls.count("oco") == 1
    assert path.calls.count("reconcile") == 3 + expected_cancel_attempts
    assert path.calls[path.calls.index("oco") + 1 :] == [
        "reconcile",
        "recover",
        "confirm_oco",
    ]


def test_g013_orchestrator_rechecks_300_second_signal_age_before_any_post() -> None:
    # 観測(00:00:00)から301秒後はMAXIMUM_FORMAL_SIGNAL_AGE_SECONDS(300s)を超え、
    # POST直前の再検査で期限切れ扱いになり一切のPOSTを行わない。
    path = _FakePath(["FILLED_UNPROTECTED", "FILLED_PROTECTED"])
    binding = SimpleNamespace(coordinated_path=path)
    with pytest.raises(canary_module.V4GmoG013CanaryError, match="SIGNAL_EXPIRED"):
        canary_module._run_bound_g013_canary(
            session=_fake_session(),
            binding=binding,
            on_protected=None,
            wall_clock=lambda: datetime(2099, 1, 1, 0, 5, 1, tzinfo=UTC),
        )
    assert "market" not in path.calls
    assert "cancel" not in path.calls
    assert "oco" not in path.calls


def test_g013_orchestrator_admits_signal_within_widened_300_second_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # 観測から240秒後は旧窓(120s)では期限切れだったが、新窓(300s)では十分freshとして
    # 通過し、signal-age gateがmarket entryを妨げないことを実証する回帰。
    path = _FakePath(["FILLED_UNPROTECTED", "FILLED_PROTECTED"])
    binding = SimpleNamespace(
        coordinated_path=path,
        build_foreground_lifecycle_driver=lambda: SimpleNamespace(
            run_until_flat=lambda: SimpleNamespace(flat_reconciled=True)
        ),
    )
    monkeypatch.setattr(
        canary_module,
        "_execution_policy",
        lambda generation: SimpleNamespace(entry_time_allowed=lambda **kwargs: True),
    )
    monkeypatch.setattr(canary_module, "_require_exact_session_binding", lambda session: None)
    monkeypatch.setattr(
        canary_module,
        "read_g013_final_quote_once",
        lambda **kwargs: SimpleNamespace(bid=Decimal("160.000"), ask=Decimal("160.005")),
    )
    result = canary_module._run_bound_g013_canary(
        session=_fake_session(),
        binding=binding,
        on_protected=None,
        wall_clock=lambda: datetime(2099, 1, 1, 0, 4, 0, tzinfo=UTC),
    )
    assert result.entry_post_attempt_count == 1
    assert path.calls.count("market") == 1


def test_g013_orchestrator_rechecks_entry_window_before_public_or_private_io(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = _FakePath(["FILLED_UNPROTECTED", "FILLED_PROTECTED"])
    binding = SimpleNamespace(coordinated_path=path)
    quote_called = False

    def _quote(**kwargs: object) -> object:
        nonlocal quote_called
        del kwargs
        quote_called = True
        return object()

    monkeypatch.setattr(
        canary_module,
        "_execution_policy",
        lambda generation: SimpleNamespace(entry_time_allowed=lambda **kwargs: False),
    )
    monkeypatch.setattr(canary_module, "read_g013_final_quote_once", _quote)
    with pytest.raises(canary_module.V4GmoG013CanaryError, match="SIGNAL_EXPIRED"):
        canary_module._run_bound_g013_canary(
            session=_fake_session(),
            binding=binding,
            on_protected=None,
            wall_clock=lambda: datetime(2099, 1, 1, 0, 1, tzinfo=UTC),
        )
    assert quote_called is False
    assert path.calls == []


@pytest.mark.parametrize(
    ("path", "expected_status"),
    (
        (
            _FakePath(
                [], market_outcome=V4GmoPrivateOutcome.UNKNOWN_SANITIZED
            ),
            "ENTRY_NOT_ACCEPTED_HALT",
        ),
        (
            _FakePath(
                ["MARKET_PARTIAL_PENDING"],
                cancel_outcome=V4GmoPrivateOutcome.UNKNOWN_SANITIZED,
            ),
            "ENTRY_REMAINDER_CANCEL_NOT_ACCEPTED_HALT",
        ),
        (
            _FakePath(
                ["FILLED_UNPROTECTED"],
                protection_outcome=V4GmoPrivateOutcome.UNKNOWN_SANITIZED,
            ),
            "PROTECTION_NOT_ACCEPTED_HALT",
        ),
    ),
)
def test_g013_unknown_write_outcome_never_reaches_a_later_write(
    monkeypatch: pytest.MonkeyPatch,
    path: _FakePath,
    expected_status: str,
) -> None:
    binding = SimpleNamespace(coordinated_path=path)
    monkeypatch.setattr(canary_module, "_require_exact_session_binding", lambda _session: None)
    monkeypatch.setattr(
        canary_module,
        "_execution_policy",
        lambda _generation: SimpleNamespace(entry_time_allowed=lambda **_kwargs: True),
    )
    monkeypatch.setattr(
        canary_module,
        "read_g013_final_quote_once",
        lambda **_kwargs: SimpleNamespace(
            bid=Decimal("160.000"), ask=Decimal("160.005")
        ),
    )
    result = canary_module._run_bound_g013_canary(
        session=_fake_session(),
        binding=binding,
        on_protected=None,
        wall_clock=lambda: datetime(2099, 1, 1, 0, 1, tzinfo=UTC),
    )
    assert result.status == expected_status
    if "market" in path.calls and path.market_outcome is V4GmoPrivateOutcome.UNKNOWN_SANITIZED:
        assert "cancel" not in path.calls and "oco" not in path.calls
    if "cancel" in path.calls and path.cancel_outcome is V4GmoPrivateOutcome.UNKNOWN_SANITIZED:
        assert "oco" not in path.calls
    if "oco" in path.calls and path.protection_outcome is V4GmoPrivateOutcome.UNKNOWN_SANITIZED:
        assert "confirm_oco" not in path.calls


def test_g013_entry_halt_surfaces_fixed_failure_class_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The halt result carries the adapter's FIXED diagnostic label so an operator can
    # attribute a failed entry (timeout / connection / non-JSON / rejected) without any
    # broker content; non-conforming labels are dropped.
    monkeypatch.setattr(canary_module, "_require_exact_session_binding", lambda _s: None)
    monkeypatch.setattr(
        canary_module,
        "_execution_policy",
        lambda _g: SimpleNamespace(entry_time_allowed=lambda **_k: True),
    )
    monkeypatch.setattr(
        canary_module,
        "read_g013_final_quote_once",
        lambda **_k: SimpleNamespace(bid=Decimal("160.000"), ask=Decimal("160.005")),
    )

    def _run(adapter_label: object) -> canary_module.V4GmoG013CanaryResult:
        path = _FakePath([], market_outcome=V4GmoPrivateOutcome.UNKNOWN_SANITIZED)
        path.adapter = SimpleNamespace(last_failure_class=adapter_label)
        return canary_module._run_bound_g013_canary(
            session=_fake_session(),
            binding=SimpleNamespace(coordinated_path=path),
            on_protected=None,
            wall_clock=lambda: datetime(2099, 1, 1, 0, 1, tzinfo=UTC),
        )

    surfaced = _run("V4_GMO_PRIVATE_RESULT_UNKNOWN_TIMEOUT")
    assert surfaced.status == "ENTRY_NOT_ACCEPTED_HALT"
    assert surfaced.failure_class == "V4_GMO_PRIVATE_RESULT_UNKNOWN_TIMEOUT"
    assert "failure_class" in surfaced.to_safe_dict()
    dropped = _run("broker said: <html>")
    assert dropped.failure_class is None


def test_g013_prepermit_refresh_failure_prevents_confirmation_and_permit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = SimpleNamespace(
        _use=SimpleNamespace(consume_once=lambda: None),
    )
    confirm_resume = MagicMock()
    confirm_current = MagicMock()
    issue_permit = MagicMock()
    monkeypatch.setattr(canary_module, "_require_exact_session_binding", lambda _session: None)
    monkeypatch.setattr(
        canary_module,
        "_refresh_session_evidence_before_permit",
        lambda _session: (_ for _ in ()).throw(
            canary_module.V4GmoG013CanaryError("G013_REVALIDATION_BLOCKED")
        ),
    )
    monkeypatch.setattr(canary_module, "confirm_v4_major_incident_resume_exact", confirm_resume)
    monkeypatch.setattr(canary_module, "confirm_v4_current_turn_exact", confirm_current)
    monkeypatch.setattr(canary_module, "issue_v4_gmo_actual_activation_permit", issue_permit)
    with pytest.raises(canary_module.V4GmoG013CanaryError, match="REVALIDATION_BLOCKED"):
        canary_module.run_g013_actual_canary_after_exact_confirmation(
            session=cast(canary_module.V4GmoG013PreparedSession, session),
            major_incident_resume_phrase="not-used",
            current_turn_phrase="not-used",
        )
    confirm_resume.assert_not_called()
    confirm_current.assert_not_called()
    issue_permit.assert_not_called()


def test_g013_run_reserves_no_cycle_when_resume_confirmation_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A mistyped resume phrase raises before the cycle is reserved, so no cycle is written
    # and the generation stays reusable for the next actionable signal.
    reserve = MagicMock()
    issue_permit = MagicMock()
    session = SimpleNamespace(
        _use=SimpleNamespace(consume_once=lambda: None),
        store=SimpleNamespace(reserve_entry_cycle=reserve),
        generation=SimpleNamespace(digest="sha256:" + "a" * 64),
        formal_input=SimpleNamespace(signal=object(), frozen_atr_24=Decimal("0.1")),
        intent=object(),
        repository=Path("/nonexistent"),
    )
    monkeypatch.setattr(canary_module, "_require_exact_session_binding", lambda _session: None)
    monkeypatch.setattr(canary_module, "_refresh_session_evidence_before_permit", lambda s: s)
    monkeypatch.setattr(
        canary_module,
        "confirm_v4_major_incident_resume_exact",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("resume-mismatch")),
    )
    monkeypatch.setattr(canary_module, "issue_v4_gmo_actual_activation_permit", issue_permit)
    with pytest.raises(RuntimeError, match="resume-mismatch"):
        canary_module.run_g013_actual_canary_after_exact_confirmation(
            session=cast(canary_module.V4GmoG013PreparedSession, session),
            major_incident_resume_phrase="wrong",
            current_turn_phrase="unused",
        )
    reserve.assert_not_called()
    issue_permit.assert_not_called()


def test_g013_run_reserves_cycle_after_confirmations_before_permit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # After both exact confirmations succeed, the run re-checks the signal is postable and
    # THEN reserves the single cycle, before issuing the permit / any POST.
    order: list[str] = []
    session = SimpleNamespace(
        _use=SimpleNamespace(consume_once=lambda: None),
        store=SimpleNamespace(reserve_entry_cycle=lambda **_kwargs: order.append("reserve")),
        generation=SimpleNamespace(digest="sha256:" + "a" * 64),
        formal_input=SimpleNamespace(signal=object(), frozen_atr_24=Decimal("0.1")),
        intent=object(),
        challenge=object(),
        repository=Path("/nonexistent"),
    )
    monkeypatch.setattr(canary_module, "_require_exact_session_binding", lambda _session: None)
    monkeypatch.setattr(canary_module, "_refresh_session_evidence_before_permit", lambda s: s)
    monkeypatch.setattr(
        canary_module, "confirm_v4_major_incident_resume_exact", lambda **_kwargs: object()
    )
    monkeypatch.setattr(
        canary_module, "confirm_v4_current_turn_exact", lambda **_kwargs: object()
    )
    monkeypatch.setattr(
        canary_module, "_ensure_signal_postable", lambda **_kwargs: order.append("postable")
    )
    monkeypatch.setattr(canary_module, "_execution_policy", lambda _generation: SimpleNamespace())
    monkeypatch.setattr(
        canary_module,
        "_require_fresh_monitor_heartbeat",
        lambda **_kwargs: order.append("heartbeat"),
    )
    monkeypatch.setattr(
        canary_module,
        "issue_v4_gmo_actual_activation_permit",
        lambda **_kwargs: (_ for _ in ()).throw(
            canary_module.V4GmoG013CanaryError("STOP_AFTER_RESERVE")
        ),
    )
    with pytest.raises(canary_module.V4GmoG013CanaryError, match="STOP_AFTER_RESERVE"):
        canary_module.run_g013_actual_canary_after_exact_confirmation(
            session=cast(canary_module.V4GmoG013PreparedSession, session),
            major_incident_resume_phrase="ok",
            current_turn_phrase="ok",
        )
    # postable re-check, pre-reserve supervisor liveness, cycle reservation, then the
    # post-reserve supervisor gate — all before the permit / any POST.
    assert order == ["postable", "heartbeat", "reserve", "heartbeat"]


def test_require_fresh_monitor_heartbeat_matches_cycle_present_requirement(
    tmp_path: Path,
) -> None:
    # The prepare-phase gate (no cycle yet) requires cycle_present is False; the
    # post-reserve gate requires the supervisor to have observed the cycle (True).
    state_root = tmp_path / "state"
    state_root.mkdir()
    heartbeat_path = state_root / "supervisor-heartbeat.json"

    def _write(*, cycle_present: bool) -> None:
        heartbeat_path.write_text(
            json.dumps(
                {
                    "observed_at_utc": datetime.now(UTC).isoformat(),
                    "generation_bound": True,
                    "cycle_present": cycle_present,
                    "broker_read": False,
                    "broker_write": False,
                    "actual_post_count": 0,
                }
            ),
            encoding="utf-8",
        )

    _write(cycle_present=False)
    canary_module._require_fresh_monitor_heartbeat(
        state_root=state_root, require_cycle_present=False, timeout_seconds=1.0
    )
    with pytest.raises(canary_module.V4GmoG013CanaryError, match="MONITOR_HEARTBEAT_NOT_CLEAR"):
        canary_module._require_fresh_monitor_heartbeat(
            state_root=state_root, require_cycle_present=True, timeout_seconds=1.0
        )
    _write(cycle_present=True)
    canary_module._require_fresh_monitor_heartbeat(
        state_root=state_root, require_cycle_present=True, timeout_seconds=1.0
    )
    with pytest.raises(canary_module.V4GmoG013CanaryError, match="MONITOR_HEARTBEAT_NOT_CLEAR"):
        canary_module._require_fresh_monitor_heartbeat(
            state_root=state_root, require_cycle_present=False, timeout_seconds=1.0
        )


def test_g013_run_reserves_no_cycle_when_signal_ages_out_before_reserve(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Real _ensure_signal_postable: if the signal ages past the postable window during
    # operator input, the run raises before reserving — generation stays reusable.
    reserve = MagicMock()
    issue_permit = MagicMock()
    selected = V4ApprovedOperatorSelections()
    aged_signal = FormalSignal(
        strategy_version=selected.strategy_version,
        signal_config_hash=selected.signal_config_hash,
        horizon=FormalHorizon.MINUTES_30,
        observed_at_utc=datetime(2000, 1, 1, tzinfo=UTC),
        valid_until_utc=datetime(2000, 1, 1, 0, 30, tzinfo=UTC),
        decision=SignalDecision.BUY,
        probability_up=Decimal("0.61"),
    )
    session = SimpleNamespace(
        _use=SimpleNamespace(consume_once=lambda: None),
        store=SimpleNamespace(reserve_entry_cycle=reserve),
        generation=SimpleNamespace(digest="sha256:" + "a" * 64),
        formal_input=SimpleNamespace(signal=aged_signal, frozen_atr_24=Decimal("0.1")),
        intent=object(),
        challenge=object(),
        repository=Path("/nonexistent"),
    )
    monkeypatch.setattr(canary_module, "_require_exact_session_binding", lambda _session: None)
    monkeypatch.setattr(canary_module, "_refresh_session_evidence_before_permit", lambda s: s)
    monkeypatch.setattr(
        canary_module, "confirm_v4_major_incident_resume_exact", lambda **_kwargs: object()
    )
    monkeypatch.setattr(
        canary_module, "confirm_v4_current_turn_exact", lambda **_kwargs: object()
    )
    monkeypatch.setattr(canary_module, "issue_v4_gmo_actual_activation_permit", issue_permit)
    with pytest.raises(canary_module.V4GmoG013CanaryError, match="SIGNAL_EXPIRED_BEFORE_POST"):
        canary_module.run_g013_actual_canary_after_exact_confirmation(
            session=cast(canary_module.V4GmoG013PreparedSession, session),
            major_incident_resume_phrase="ok",
            current_turn_phrase="ok",
        )
    reserve.assert_not_called()
    issue_permit.assert_not_called()


def test_canary_script_reads_hidden_input_without_discarding_typed_bytes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # getpass must own the terminal BEFORE the operator types: it takes the tty with
    # TCSAFLUSH, which discards whatever is already buffered. Waiting for input first
    # (the previous select-on-stdin) threw away exactly the phrase the operator typed,
    # so every confirmation silently mismatched.
    import scripts.h11_auto_v4_g013_actual_canary as canary_script

    prompts: list[str] = []

    def _fake_getpass(prompt: str = "") -> str:
        prompts.append(prompt)
        return "operator-typed-value"

    monkeypatch.setattr(canary_script.getpass, "getpass", _fake_getpass)
    assert (
        canary_script._hidden_input("major_incident_resume_exact_required")
        == "operator-typed-value"
    )
    # The label rides in the getpass prompt (controlling tty), so it survives
    # stdout redirection and appears exactly when echo-off input begins.
    assert prompts == ["major_incident_resume_exact_required\n"]
    # The one-shot timer is disarmed after a successful read, so SIGALRM can
    # never fire later during the permit/POST sequence.
    assert signal.getitimer(signal.ITIMER_REAL) == (0.0, 0.0)
    prompts.clear()
    assert (
        canary_script._hidden_current_turn_input("H11 V4 G013 CANARY abc def")
        == "operator-typed-value"
    )
    # The challenge rides in the getpass prompt, so it is shown the moment getpass takes
    # the terminal — the operator never has to type blind just to reveal it.
    assert prompts == [
        "current_turn_challenge_exact_required [H11 V4 G013 CANARY abc def]\n> "
    ]


def test_canary_script_hidden_input_still_times_out_and_disarms_timer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import scripts.h11_auto_v4_g013_actual_canary as canary_script

    monkeypatch.setattr(canary_script, "INPUT_TIMEOUT_SECONDS", 0.05)
    monkeypatch.setattr(
        canary_script.getpass, "getpass", lambda prompt="": time.sleep(5.0)
    )
    with pytest.raises(
        canary_module.V4GmoG013CanaryError, match="OPERATOR_CONFIRMATION_TIMEOUT"
    ):
        canary_script._hidden_input("major_incident_resume_exact_required")
    # The real-time timer is always disarmed, so it can never fire during a broker write.
    assert signal.getitimer(signal.ITIMER_REAL) == (0.0, 0.0)


def test_canary_script_timeout_survives_inherited_sigalrm_block(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A launcher that blocks SIGALRM must not silently defeat the 300s bound: the
    # reader unblocks SIGALRM before arming, so the timeout still fires.
    import scripts.h11_auto_v4_g013_actual_canary as canary_script

    monkeypatch.setattr(canary_script, "INPUT_TIMEOUT_SECONDS", 0.05)
    monkeypatch.setattr(
        canary_script.getpass, "getpass", lambda prompt="": time.sleep(5.0)
    )
    original_mask = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGALRM})
    try:
        with pytest.raises(
            canary_module.V4GmoG013CanaryError, match="OPERATOR_CONFIRMATION_TIMEOUT"
        ):
            canary_script._hidden_input("major_incident_resume_exact_required")
    finally:
        signal.pthread_sigmask(signal.SIG_SETMASK, original_mask)
    assert signal.getitimer(signal.ITIMER_REAL) == (0.0, 0.0)


def test_public_operation_ledger_cycle_key_retries_next_slot_only(
    tmp_path: Path,
) -> None:
    ledger = V4GmoG013PublicOperationLedger(
        state_root=tmp_path / "runtime",
        generation_digest="sha256:" + "a" * 64,
    )
    formal = V4GmoG013PublicOperation.FORMAL_CANDLES
    slot_a = g013_public_cycle_key(datetime(2026, 7, 20, 17, 30, tzinfo=UTC))
    slot_b = g013_public_cycle_key(datetime(2026, 7, 20, 17, 31, tzinfo=UTC))
    assert slot_a != slot_b

    # Same minute-slot is still strictly one-use (no double public GET/minute).
    ledger.claim_once(formal, cycle_key=slot_a)
    with pytest.raises(V4GmoPublicPreflightError, match="ALREADY_ATTEMPTED"):
        ledger.claim_once(formal, cycle_key=slot_a)

    # The next minute-slot is a fresh claim: a STAY run retries next minute
    # within the same generation without re-running external preparation.
    ledger.claim_once(formal, cycle_key=slot_b)

    # A cycle_key-less claim (FINAL_QUOTE / POST-phase) stays one-use per
    # generation and is independent of the per-slot signal markers.
    final = V4GmoG013PublicOperation.FINAL_QUOTE
    ledger.claim_once(final)
    with pytest.raises(V4GmoPublicPreflightError, match="ALREADY_ATTEMPTED"):
        ledger.claim_once(final)

    # An unsafe cycle_key is rejected before any marker is written.
    with pytest.raises(V4GmoPublicPreflightError, match="CYCLE_KEY_INVALID"):
        ledger.claim_once(formal, cycle_key="../escape")


def test_g013_final_quote_tolerates_behind_clock_within_skew(
    tmp_path: Path,
) -> None:
    ledger = V4GmoG013PublicOperationLedger(
        state_root=tmp_path / "runtime",
        generation_digest="sha256:" + "a" * 64,
    )

    def _handler(timestamp: str):
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/public/v1/status":
                return httpx.Response(
                    200, json={"status": 0, "data": {"status": "OPEN"}}
                )
            return httpx.Response(
                200,
                json={
                    "status": 0,
                    "data": [
                        {
                            "symbol": "USD_JPY",
                            "ask": "160.005",
                            "bid": "160.000",
                            "timestamp": timestamp,
                            "status": "OPEN",
                        }
                    ],
                },
            )

        return handler

    # age = -2s (local clock behind) is within the +/-5s window -> fresh.
    fresh_client = httpx.Client(
        transport=httpx.MockTransport(_handler("2026-07-17T00:00:02Z"))
    )
    quote = read_g013_final_quote_once(
        operation_ledger=ledger,
        operation=V4GmoG013PublicOperation.REFERENCE_QUOTE,
        client=fresh_client,
        wall_clock=lambda: datetime(2026, 7, 17, 0, 0, 0, tzinfo=UTC),
    )
    assert quote.quote_fresh is True
    fresh_client.close()

    # age = -7s exceeds +/-5s -> the POST-phase gate still blocks (staleness cap
    # unchanged; a genuinely-wrong clock is rejected here and by op30).
    stale_client = httpx.Client(
        transport=httpx.MockTransport(_handler("2026-07-17T00:00:07Z"))
    )
    with pytest.raises(V4GmoPublicPreflightError, match="FINAL_QUOTE_GATE_BLOCKED"):
        read_g013_final_quote_once(
            operation_ledger=ledger,
            operation=V4GmoG013PublicOperation.FINAL_QUOTE,
            client=stale_client,
            wall_clock=lambda: datetime(2026, 7, 17, 0, 0, 0, tzinfo=UTC),
        )
    stale_client.close()
