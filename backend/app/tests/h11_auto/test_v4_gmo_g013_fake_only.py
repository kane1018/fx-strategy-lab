from __future__ import annotations

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

from app.h11_auto import v4_actual_preparation_guard as guard_module
from app.h11_auto.contracts import FormalHorizon, FormalSignal, SignalDecision
from app.h11_auto.v4_activation_preparation import V4ApprovedOperatorSelections
from app.h11_auto.v4_gmo_canary_activation import V4GmoCanaryIntent
from app.h11_manual.short_model import ShortModelArtifact
from app.services import h11_v4_gmo_formal_canary_source as source_module
from app.services import h11_v4_gmo_g013_canary as canary_module
from app.services.h11_v4_gmo_actual_adapter import V4GmoPrivateOutcome
from app.services.h11_v4_gmo_formal_canary_source import (
    G013_ATR_TIMEFRAME,
    V4GmoFormalCanarySourceError,
    build_g013_formal_canary_input,
    refresh_g013_formal_canary_input,
)
from app.services.h11_v4_gmo_public_preflight import (
    G013_MAXIMUM_ENTRY_SPREAD_PIPS,
    V4GmoG013PublicOperation,
    V4GmoG013PublicOperationLedger,
    V4GmoPublicPreflightError,
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
            m1=_frame(end_utc=now - timedelta(minutes=3), count=40, minutes=1),
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
            frame = m1_frame if interval == "M1" else h1_frame
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
    monkeypatch.setattr(
        source_module,
        "CandleRepository",
        lambda root: repository_type(root, supplemental_h1_paths=()),
    )
    monkeypatch.setattr(
        source_module.ShortModelArtifact,
        "load",
        staticmethod(lambda path: _artifact_stub()),
    )
    monkeypatch.setattr(source_module, "predict_short_model", lambda *args: 0.61)
    ledger = _public_ledger(tmp_path / "ledger")
    result = refresh_g013_formal_canary_input(
        operation_ledger=ledger,
        data_root=tmp_path / "data",
        now_utc=now,
    )
    assert _FakePublicClient.calls == ["M1", "H1"]
    assert result.signal.observed_at_utc == datetime(2026, 7, 17, 3, 0, tzinfo=UTC)
    assert result.frozen_atr_24 == Decimal("0.04")
    with pytest.raises(V4GmoPublicPreflightError, match="ALREADY_ATTEMPTED"):
        refresh_g013_formal_canary_input(
            operation_ledger=ledger,
            data_root=tmp_path / "data",
            now_utc=now,
        )
    assert _FakePublicClient.calls == ["M1", "H1"]


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
    assert "backend/app/h11_auto/signal_adapter.py" in guard_module._REVIEWED_FILES


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


def test_g013_orchestrator_rechecks_120_second_signal_age_before_any_post() -> None:
    path = _FakePath(["FILLED_UNPROTECTED", "FILLED_PROTECTED"])
    binding = SimpleNamespace(coordinated_path=path)
    with pytest.raises(canary_module.V4GmoG013CanaryError, match="SIGNAL_EXPIRED"):
        canary_module._run_bound_g013_canary(
            session=_fake_session(),
            binding=binding,
            on_protected=None,
            wall_clock=lambda: datetime(2099, 1, 1, 0, 2, 1, tzinfo=UTC),
        )
    assert "market" not in path.calls
    assert "cancel" not in path.calls
    assert "oco" not in path.calls


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
