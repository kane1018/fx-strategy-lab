from __future__ import annotations

import ast
import inspect
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import httpx
import pandas as pd
import pytest

from app.h11_auto import v4_unattended_shadow_controller as controller
from app.h11_auto.contracts import FormalHorizon, SignalDecision
from app.h11_auto.v4_gmo_contracts import V4GmoExecutionPolicy
from app.h11_auto.v4_gmo_protection import H11_V4_GMO_PROTECTION_CONTRACT_HASH
from app.h11_manual.short_model import ShortModelArtifact
from app.services import h11_v4_gmo_formal_canary_source as canary_source
from app.services import h11_v4_unattended_shadow_public_adapter as subject
from app.shadow.gmo_public import PUBLIC_BASE_URL, GmoPublicMarketDataClient
from scripts import h11_auto_v4_unattended_shadow_run as runner

_NOW = datetime(2026, 7, 20, 3, 1, 30, tzinfo=UTC)
_EXPECTED_SLOT = datetime(2026, 7, 20, 3, 0, 0, tzinfo=UTC)
_TICKER_TIMESTAMP = "2026-07-20T03:01:28.000Z"


@pytest.fixture(autouse=True)
def _isolated_shadow_export_root(
    tmp_path: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = Path(str(tmp_path)) / "backend" / "shadow_exports"
    monkeypatch.setattr(subject, "_SHADOW_EXPORT_ROOT", root)
    monkeypatch.setattr(controller, "_SHADOW_EXPORT_ROOT", root)


def _artifact_stub() -> ShortModelArtifact:
    return cast(
        ShortModelArtifact,
        SimpleNamespace(config_hash=subject.V4_UNATTENDED_SHADOW_SIGNAL_CONFIG_HASH),
    )


def _ohlc(index: int) -> tuple[float, float, float, float]:
    base = 160.0 + index * 0.001
    return base, base + 0.02, base - 0.02, base + 0.005


def _frame(*, end_utc: datetime, count: int, minutes: int) -> pd.DataFrame:
    times = [end_utc - timedelta(minutes=minutes * offset) for offset in range(count)]
    times.reverse()
    rows = [_ohlc(index) for index in range(count)]
    return pd.DataFrame(
        {
            "time_utc": [value.isoformat() for value in times],
            "open": [row[0] for row in rows],
            "high": [row[1] for row in rows],
            "low": [row[2] for row in rows],
            "close": [row[3] for row in rows],
        }
    )


def _kline_rows(*, end_utc: datetime, count: int, minutes: int) -> list[dict[str, str]]:
    times = [end_utc - timedelta(minutes=minutes * offset) for offset in range(count)]
    times.reverse()
    rows = []
    for index, value in enumerate(times):
        open_, high, low, close = _ohlc(index)
        rows.append(
            {
                "openTime": str(int(value.timestamp() * 1000)),
                "open": f"{open_:.3f}",
                "high": f"{high:.3f}",
                "low": f"{low:.3f}",
                "close": f"{close:.3f}",
            }
        )
    return rows


def _envelope(data: object) -> dict[str, object]:
    return {"status": 0, "data": data, "responsetime": "2026-07-20T03:01:30.000Z"}


def _default_handler(
    *,
    status_value: str = "OPEN",
    bid: str = "157.000",
    ask: str = "157.004",
    ticker_timestamp: str = _TICKER_TIMESTAMP,
) -> httpx.MockTransport:
    m1_rows = _kline_rows(end_utc=_EXPECTED_SLOT, count=40, minutes=1)
    h1_prev = _kline_rows(
        end_utc=datetime(2026, 7, 19, 23, 0, tzinfo=UTC), count=24, minutes=60
    )
    h1_today = _kline_rows(
        end_utc=datetime(2026, 7, 20, 3, 0, tzinfo=UTC), count=4, minutes=60
    )

    def handle(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/v1/status"):
            return httpx.Response(200, json=_envelope({"status": status_value}))
        if path.endswith("/v1/ticker"):
            return httpx.Response(
                200,
                json=_envelope(
                    [
                        {
                            "symbol": "USD_JPY",
                            "bid": bid,
                            "ask": ask,
                            "timestamp": ticker_timestamp,
                            "status": status_value,
                        }
                    ]
                ),
            )
        if path.endswith("/v1/klines"):
            interval = request.url.params.get("interval")
            date = request.url.params.get("date")
            if interval == "1min":
                return httpx.Response(200, json=_envelope(m1_rows))
            if interval == "1hour" and date == "20260719":
                return httpx.Response(200, json=_envelope(h1_prev))
            if interval == "1hour" and date == "20260720":
                return httpx.Response(200, json=_envelope(h1_today))
        return httpx.Response(404, json=_envelope(None))

    return httpx.MockTransport(handle)


def _client_factory(transport: httpx.MockTransport):
    def factory() -> GmoPublicMarketDataClient:
        return GmoPublicMarketDataClient(
            client=httpx.Client(base_url=PUBLIC_BASE_URL, transport=transport)
        )

    return factory


def _observe(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    transport: httpx.MockTransport | None = None,
    now_utc: datetime = _NOW,
    p_up: float = 0.61,
) -> subject.V4UnattendedShadowObservation:
    monkeypatch.setattr(subject, "predict_short_model", lambda *args: p_up)
    return subject.observe_public_shadow_cycle(
        slot_state_root=subject._SHADOW_EXPORT_ROOT / "slots",
        artifact=_artifact_stub(),
        now_utc=now_utc,
        client_factory=_client_factory(transport or _default_handler()),
        sleeper=lambda _seconds: None,
    )


def _policy() -> V4GmoExecutionPolicy:
    return V4GmoExecutionPolicy(
        strategy_version=subject.V4_UNATTENDED_SHADOW_STRATEGY_VERSION,
        signal_config_hash=subject.V4_UNATTENDED_SHADOW_SIGNAL_CONFIG_HASH,
        selected_horizon=FormalHorizon.MINUTES_30,
        protection_contract_hash=H11_V4_GMO_PROTECTION_CONTRACT_HASH,
    )


def test_clear_public_cycle_blocks_only_on_unobservable_broker_dimensions(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    observation = _observe(monkeypatch, tmp_path)
    assert observation.signal.decision is SignalDecision.BUY
    assert observation.snapshot.market_open is True
    assert observation.snapshot.frozen_atr_24 > Decimal("0")
    assert observation.completed_slot_utc == _EXPECTED_SLOT
    assert observation.public_get_count == 5

    store = controller.V4UnattendedShadowStore(
        subject._SHADOW_EXPORT_ROOT / "shadow.sqlite3"
    )
    report = controller.run_v4_unattended_shadow_cycle_once(
        signal=observation.signal,
        policy=_policy(),
        snapshot=observation.snapshot,
        store=store,
        lock_path=subject._SHADOW_EXPORT_ROOT / "shadow.lock",
        now_utc=_NOW,
    )
    assert report.status is controller.V4ShadowDecisionStatus.SHADOW_BLOCKED_SAFE
    # Every unobservable broker dimension is named fail-closed; nothing from the
    # signal / market / quote / spread gates appears (those all passed).
    assert set(report.blocked_reasons) == {
        "BOOT_RECONCILIATION_REQUIRED",
        "NOTIFICATION_PATH_NOT_READY",
        "BROKER_SNAPSHOT_STALE",
        "POSITION_NOT_FLAT",
        "ACTIVE_ORDER_EXISTS",
        "DAILY_ENTRY_LIMIT_REACHED",
    }
    assert report.shadow_intent is None
    assert report.to_safe_dict()["broker_post_authorized"] is False


def test_signal_and_atr_match_the_frozen_actual_canary_builder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    m1 = _frame(end_utc=_NOW - timedelta(seconds=90), count=40, minutes=1)
    h1 = _frame(end_utc=_NOW - timedelta(hours=1), count=25, minutes=60)
    monkeypatch.setattr(subject, "predict_short_model", lambda *args: 0.61)
    monkeypatch.setattr(canary_source, "predict_short_model", lambda *args: 0.61)

    shadow_signal, shadow_atr = subject._build_signal_and_atr(
        m1_window=m1, h1_completed=h1, artifact=_artifact_stub(), now_utc=_NOW
    )
    canary = canary_source.build_g013_formal_canary_input(
        m1=m1,
        h1=h1,
        artifact=_artifact_stub(),
        now_utc=_NOW,
        public_candle_refresh_performed=False,
    )
    assert shadow_signal.decision is SignalDecision.BUY
    assert shadow_signal.fingerprint == canary.signal.fingerprint
    assert shadow_atr == canary.frozen_atr_24
    # Pin the replicated ATR arithmetic directly against the canonical helper so
    # any future drift in either implementation fails here, not silently in prod.
    assert subject._completed_h1_atr_24(h1) == canary_source._completed_h1_atr_24(h1)


def test_stay_signal_is_accepted_and_still_blocks_safely(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    observation = _observe(monkeypatch, tmp_path, p_up=0.50)
    assert observation.signal.decision is SignalDecision.STAY
    store = controller.V4UnattendedShadowStore(
        subject._SHADOW_EXPORT_ROOT / "shadow.sqlite3"
    )
    report = controller.run_v4_unattended_shadow_cycle_once(
        signal=observation.signal,
        policy=_policy(),
        snapshot=observation.snapshot,
        store=store,
        lock_path=subject._SHADOW_EXPORT_ROOT / "shadow.lock",
        now_utc=_NOW,
    )
    assert report.status is controller.V4ShadowDecisionStatus.SHADOW_BLOCKED_SAFE
    assert report.shadow_intent is None


def test_market_closed_status_makes_cycle_report_market_not_open(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    observation = _observe(
        monkeypatch, tmp_path, transport=_default_handler(status_value="CLOSE")
    )
    assert observation.snapshot.market_open is False


def test_spread_and_quote_age_are_parsed_from_public_ticker(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    observation = _observe(
        monkeypatch,
        tmp_path,
        transport=_default_handler(bid="157.000", ask="157.030"),
    )
    assert observation.snapshot.spread_pips == Decimal("3.0")
    assert observation.snapshot.quote_age_seconds == Decimal("2.0")
    assert observation.snapshot.reference_deviation_pips == Decimal("0")


def test_same_completed_slot_is_claimed_once_and_never_retried(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _observe(monkeypatch, tmp_path)
    with pytest.raises(
        subject.V4UnattendedShadowPublicError, match="SHADOW_PUBLIC_SLOT_ALREADY_OBSERVED"
    ):
        _observe(monkeypatch, tmp_path)


def test_slot_root_outside_shadow_exports_is_refused(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(subject, "predict_short_model", lambda *args: 0.61)
    with pytest.raises(
        subject.V4UnattendedShadowPublicError, match="SHADOW_PUBLIC_SLOT_ROOT_OUTSIDE_EXPORTS"
    ):
        subject.observe_public_shadow_cycle(
            slot_state_root=Path(str(tmp_path)) / "outside",
            artifact=_artifact_stub(),
            now_utc=_NOW,
            client_factory=_client_factory(_default_handler()),
            sleeper=lambda _seconds: None,
        )


def test_forged_artifact_config_hash_is_refused(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    forged = cast(ShortModelArtifact, SimpleNamespace(config_hash="sha256:" + "0" * 64))
    monkeypatch.setattr(subject, "predict_short_model", lambda *args: 0.61)
    with pytest.raises(
        subject.V4UnattendedShadowPublicError, match="SHADOW_PUBLIC_ARTIFACT_MISMATCH"
    ):
        subject.observe_public_shadow_cycle(
            slot_state_root=subject._SHADOW_EXPORT_ROOT / "slots",
            artifact=forged,
            now_utc=_NOW,
            client_factory=_client_factory(_default_handler()),
            sleeper=lambda _seconds: None,
        )


def test_stale_completed_bar_is_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    # The observe path structurally pins origin to now-floor minus one minute, so
    # staleness is exercised directly on the defensive builder guard.
    monkeypatch.setattr(subject, "predict_short_model", lambda *args: 0.61)
    stale_m1 = _frame(end_utc=_NOW - timedelta(minutes=6), count=40, minutes=1)
    h1 = _frame(end_utc=_NOW - timedelta(hours=1), count=25, minutes=60)
    with pytest.raises(
        subject.V4UnattendedShadowPublicError, match="SHADOW_PUBLIC_SIGNAL_STALE"
    ):
        subject._build_signal_and_atr(
            m1_window=stale_m1, h1_completed=h1, artifact=_artifact_stub(), now_utc=_NOW
        )


def test_public_get_failure_is_fail_closed_no_retry(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def handle(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json=_envelope(None))

    with pytest.raises(
        subject.V4UnattendedShadowPublicError, match="SHADOW_PUBLIC_GET_FAILED_NO_RETRY"
    ):
        _observe(monkeypatch, tmp_path, transport=httpx.MockTransport(handle))


def test_insufficient_h1_history_is_fail_closed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/v1/status"):
            return httpx.Response(200, json=_envelope({"status": "OPEN"}))
        if path.endswith("/v1/ticker"):
            return httpx.Response(
                200,
                json=_envelope(
                    [
                        {
                            "symbol": "USD_JPY",
                            "bid": "157.000",
                            "ask": "157.004",
                            "timestamp": _TICKER_TIMESTAMP,
                            "status": "OPEN",
                        }
                    ]
                ),
            )
        if path.endswith("/v1/klines"):
            if request.url.params.get("interval") == "1min":
                return httpx.Response(
                    200,
                    json=_envelope(_kline_rows(end_utc=_EXPECTED_SLOT, count=40, minutes=1)),
                )
            return httpx.Response(
                200,
                json=_envelope(
                    _kline_rows(
                        end_utc=datetime(2026, 7, 20, 2, 0, tzinfo=UTC),
                        count=3,
                        minutes=60,
                    )
                ),
            )
        return httpx.Response(404, json=_envelope(None))

    with pytest.raises(
        subject.V4UnattendedShadowPublicError, match="SHADOW_PUBLIC_H1_HISTORY_INSUFFICIENT"
    ):
        _observe(monkeypatch, tmp_path, transport=httpx.MockTransport(handle))


def test_planned_loss_uses_frozen_multiplier_and_size() -> None:
    assert subject._planned_loss_bound_jpy(frozen_atr_24=Decimal("0.04")) == 60
    assert subject._planned_loss_bound_jpy(frozen_atr_24=Decimal("0.09")) == 135


def test_observation_object_is_falsey_and_sanitized(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    observation = _observe(monkeypatch, tmp_path)
    assert bool(observation) is False
    assert "sanitized" in repr(observation)
    assert observation.private_api_read is False
    assert observation.broker_write_performed is False


def test_adapter_has_no_private_or_write_code_tokens() -> None:
    # Code-identifier tokens only: the exclusion docstring legitimately names the
    # capabilities the adapter avoids, so the import-graph test below is the
    # authoritative module-isolation guard.
    source = inspect.getsource(subject)
    for forbidden in (
        "app.private_api",
        "app.services.h11_v4_gmo_actual",
        "real_broker_post_hard_guard",
        "smtplib",
        "cancelOrders",
        "closeOrder",
        "/private/v1",
        "launchd",
        "launchctl",
    ):
        assert forbidden not in source, forbidden


def test_adapter_reachable_app_modules_are_public_only() -> None:
    reachable = _reachable_app_modules(
        root_module="app.services.h11_v4_unattended_shadow_public_adapter",
        app_root=Path(subject.__file__).parents[1],
    )
    forbidden_fragments = (
        "actual",
        "coordinator",
        "private",
        "hard_guard",
        "canary",
        "launchd",
        "permit",
        "notification",
        "settlement",
        "broker",
    )
    for module_name in reachable:
        for fragment in forbidden_fragments:
            assert fragment not in module_name, module_name


def _reachable_app_modules(*, root_module: str, app_root: Path) -> set[str]:
    pending = [root_module]
    visited: set[str] = set()
    while pending:
        module_name = pending.pop()
        if module_name in visited:
            continue
        module_path = _app_module_path(module_name=module_name, app_root=app_root)
        if module_path is None:
            continue
        visited.add(module_name)
        # Also walk ancestor package __init__.py modules, whose eager imports run
        # at import time and would otherwise escape a purely explicit-import walk.
        parts = module_name.split(".")
        pending.extend(".".join(parts[:length]) for length in range(1, len(parts)))
        tree = ast.parse(module_path.read_text(encoding="utf-8"), filename=str(module_path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("app."):
                pending.append(node.module)
            elif isinstance(node, ast.Import):
                pending.extend(
                    alias.name
                    for alias in node.names
                    if alias.name == "app" or alias.name.startswith("app.")
                )
    return visited


def _app_module_path(*, module_name: str, app_root: Path) -> Path | None:
    relative = module_name.split(".")[1:]
    if not relative:
        return None
    base = app_root.joinpath(*relative)
    for candidate in (base.with_suffix(".py"), base / "__init__.py"):
        if candidate.is_file():
            return candidate
    return None


def _safe_report() -> object:
    return SimpleNamespace(
        to_safe_dict=lambda: {
            "status": "SHADOW_BLOCKED_SAFE",
            "blocked_reasons": ["BROKER_SNAPSHOT_STALE"],
            "recorded": True,
            "shadow_intent_created": False,
            "broker_post_authorized": False,
            "actual_post_count": 0,
            "broker_read_performed": False,
            "broker_write_performed": False,
            "credential_read_performed": False,
            "network_access_performed": False,
            "live_ready": False,
            "unattended_live_supported": False,
        }
    )


def test_bounded_runner_loops_records_and_prints_sanitized(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        runner.ShortModelArtifact, "load", staticmethod(lambda _path: _artifact_stub())
    )
    calls = {"observe": 0, "run": 0}

    def fake_observe(*, slot_state_root: Path, artifact: object, now_utc: datetime):
        calls["observe"] += 1
        return SimpleNamespace(signal=object(), snapshot=object())

    def fake_run(*, signal, policy, snapshot, store, lock_path, now_utc):
        calls["run"] += 1
        return _safe_report()

    monkeypatch.setattr(runner, "observe_public_shadow_cycle", fake_observe)
    monkeypatch.setattr(runner, "run_v4_unattended_shadow_cycle_once", fake_run)

    exit_code = runner.main(
        [
            "--max-cycles",
            "3",
            "--interval-seconds",
            "0",
            "--shadow-root",
            str(subject._SHADOW_EXPORT_ROOT / "run"),
        ]
    )
    assert exit_code == 0
    assert calls == {"observe": 3, "run": 3}
    lines = [line for line in capsys.readouterr().out.splitlines() if line.strip()]
    assert len(lines) == 3
    for index, line in enumerate(lines):
        payload = json.loads(line)
        assert payload["cycle"] == index
        assert payload["status"] == "SHADOW_BLOCKED_SAFE"
        assert payload["broker_post_authorized"] is False
        assert payload["actual_post_count"] == 0
        assert payload["live_ready"] is False
        assert payload["unattended_live_supported"] is False
    assert (subject._SHADOW_EXPORT_ROOT / "run" / "shadow.sqlite3").is_file()


def test_bounded_runner_reports_adapter_failure_without_crashing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        runner.ShortModelArtifact, "load", staticmethod(lambda _path: _artifact_stub())
    )

    def failing_observe(*, slot_state_root: Path, artifact: object, now_utc: datetime):
        raise subject.V4UnattendedShadowPublicError("SHADOW_PUBLIC_GET_FAILED_NO_RETRY")

    monkeypatch.setattr(runner, "observe_public_shadow_cycle", failing_observe)

    exit_code = runner.main(
        [
            "--max-cycles",
            "2",
            "--interval-seconds",
            "0",
            "--shadow-root",
            str(subject._SHADOW_EXPORT_ROOT / "run"),
        ]
    )
    assert exit_code == 0
    lines = [line for line in capsys.readouterr().out.splitlines() if line.strip()]
    assert len(lines) == 2
    for line in lines:
        payload = json.loads(line)
        assert payload["status"] == "SHADOW_PUBLIC_GET_FAILED_NO_RETRY"
        assert payload["recorded"] is False
        assert payload["broker_post_authorized"] is False


def test_bounded_runner_rejects_out_of_range_cycles(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        runner.ShortModelArtifact, "load", staticmethod(lambda _path: _artifact_stub())
    )
    with pytest.raises(SystemExit):
        runner.main(["--max-cycles", "0"])
    with pytest.raises(SystemExit):
        runner.main(["--max-cycles", "100000"])


def test_bounded_runner_reports_malformed_model_file_as_safe_label(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # A structurally invalid but syntactically valid model file must fail closed
    # with a fixed safe label and exit 2, never a stack trace or leaked path/key.
    bad_model = Path(str(tmp_path)) / "bad_model.json"
    bad_model.write_text("{}", encoding="utf-8")
    exit_code = runner.main(
        [
            "--max-cycles",
            "1",
            "--interval-seconds",
            "0",
            "--shadow-root",
            str(subject._SHADOW_EXPORT_ROOT / "run"),
            "--model-path",
            str(bad_model),
        ]
    )
    assert exit_code == 2
    lines = [line for line in capsys.readouterr().out.splitlines() if line.strip()]
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["status"] == "SHADOW_PUBLIC_MODEL_INPUT_INVALID"
    assert payload["broker_post_authorized"] is False
    assert payload["recorded"] is False
