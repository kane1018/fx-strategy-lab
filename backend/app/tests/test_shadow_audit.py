"""Adversarial tests for Phase 2E local audit writer hardening."""

from __future__ import annotations

import json
from dataclasses import dataclass, fields
from datetime import UTC, datetime, timedelta

import pytest

from app.shadow.audit import AuditLogWriteError, write_audit_event
from app.shadow.audit_schema import KillSwitchAuditRecord
from app.shadow.risk import (
    SCHEMA_VERSION,
    KillSwitchReason,
    OrderCandidate,
    RiskContext,
    SignalLabel,
    SpreadProvenance,
    create_order_candidate,
    evaluate,
)

NOW = datetime(2026, 6, 22, 3, 0, tzinfo=UTC)
MARKET_TIME = NOW - timedelta(seconds=30)


@dataclass(frozen=True)
class CommonAuditPayload:
    run_id: str
    timestamp: str
    real_order: bool = False
    private_api_used: bool = False
    api_key_used: bool = False
    no_order_execution: bool = True
    live_trading_environment_enabled: bool = False
    gmo_order_enabled: bool = False


@dataclass(frozen=True)
class UnknownAuditPayload(CommonAuditPayload):
    unexpected: bool = True


@dataclass(frozen=True)
class CredentialAuditPayload(CommonAuditPayload):
    api_key: str = "dummy"


@dataclass(frozen=True)
class RawResponseAuditPayload(CommonAuditPayload):
    raw_response: dict[str, str] | None = None


def _candidate(**overrides) -> OrderCandidate:
    values = {
        "signal_label": SignalLabel.BUY,
        "run_id": "r-safe",
        "step_index": 0,
        "timestamp": NOW,
        "market_data_timestamp": MARKET_TIME,
        "source": "mock",
        "symbol": "USD_JPY",
        "interval": "M1",
        "quantity": 100,
        "bid": 154.100,
        "ask": 154.104,
        "spread_provenance": SpreadProvenance.REAL_PUBLIC_BID_ASK,
        "signal_name": "audit_test",
        "signal_reason": "fixture",
        "confidence": 0.8,
    }
    values.update(overrides)
    candidate = create_order_candidate(**values)
    assert candidate is not None
    return candidate


def _context() -> RiskContext:
    return RiskContext(
        evaluation_time=NOW,
        spread_provenance=SpreadProvenance.REAL_PUBLIC_BID_ASK,
    )


def _malformed_dataclass(instance, **overrides):
    clone = object.__new__(type(instance))
    for item in fields(instance):
        object.__setattr__(clone, item.name, getattr(instance, item.name))
    for key, value in overrides.items():
        object.__setattr__(clone, key, value)
    return clone


def test_audit_writer_saves_valid_typed_candidate(tmp_path) -> None:
    path = write_audit_event(
        tmp_path,
        run_id="r-safe",
        event_type="candidate_log",
        payload=_candidate(),
    )
    row = json.loads(path.read_text())
    assert path == tmp_path / "r-safe" / "candidate_log.jsonl"
    assert row["schema_version"] == SCHEMA_VERSION
    assert row["event_type"] == "candidate_log"
    assert row["real_order"] is False
    assert row["no_order_execution"] is True


def test_audit_writer_rejects_arbitrary_dict(tmp_path) -> None:
    with pytest.raises(AuditLogWriteError, match="typed dataclass"):
        write_audit_event(
            tmp_path,
            run_id="r-safe",
            event_type="candidate_log",
            payload={"run_id": "r-safe", "timestamp": NOW.isoformat()},
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("real_order", True),
        ("private_api_used", True),
        ("api_key_used", True),
        ("no_order_execution", False),
        ("live_trading_environment_enabled", True),
        ("gmo_order_enabled", True),
    ],
)
def test_audit_writer_rejects_unsafe_safety_flags(tmp_path, field, value) -> None:
    payload = _malformed_dataclass(_candidate(), **{field: value})
    with pytest.raises(AuditLogWriteError, match="safety"):
        write_audit_event(
            tmp_path,
            run_id="r-safe",
            event_type="candidate_log",
            payload=payload,
        )


def test_audit_writer_rejects_unknown_and_nested_unknown_fields(tmp_path) -> None:
    with pytest.raises(AuditLogWriteError, match="unknown audit field"):
        write_audit_event(
            tmp_path,
            run_id="r-safe",
            event_type="candidate_log",
            payload=UnknownAuditPayload(run_id="r-safe", timestamp=NOW.isoformat()),
        )

    kill = KillSwitchAuditRecord(
        run_id="r-safe",
        timestamp=NOW.isoformat(),
        active=True,
        reasons=(KillSwitchReason.MANUAL_STOP_FILE_EXISTS,),
        activated_at=NOW.isoformat(),
        trigger="manual",
        safety_snapshot={
            "real_order": False,
            "private_api_used": False,
            "api_key_used": False,
            "no_order_execution": True,
            "live_trading_environment_enabled": False,
            "gmo_order_enabled": False,
            "extra": False,
        },
    )
    with pytest.raises(AuditLogWriteError, match="unknown nested safety field"):
        write_audit_event(tmp_path, run_id="r-safe", event_type="kill_switch_log", payload=kill)


def test_audit_writer_rejects_credentials_and_raw_response_fields(tmp_path) -> None:
    with pytest.raises(AuditLogWriteError, match="forbidden"):
        write_audit_event(
            tmp_path,
            run_id="r-safe",
            event_type="candidate_log",
            payload=CredentialAuditPayload(run_id="r-safe", timestamp=NOW.isoformat()),
        )
    with pytest.raises(AuditLogWriteError, match="forbidden"):
        write_audit_event(
            tmp_path,
            run_id="r-safe",
            event_type="candidate_log",
            payload=RawResponseAuditPayload(
                run_id="r-safe",
                timestamp=NOW.isoformat(),
                raw_response={"status": "dummy"},
            ),
        )


@pytest.mark.parametrize("run_id", ["../escape", "/absolute", "bad/run", "bad..run", ""])
def test_audit_writer_rejects_invalid_run_id_and_path_injection(tmp_path, run_id) -> None:
    with pytest.raises(AuditLogWriteError, match="run_id"):
        write_audit_event(
            tmp_path,
            run_id=run_id,
            event_type="candidate_log",
            payload=_candidate(),
        )


def test_audit_writer_rejects_invalid_event_schema_and_reason_code(tmp_path) -> None:
    with pytest.raises(AuditLogWriteError, match="event_type"):
        write_audit_event(
            tmp_path,
            run_id="r-safe",
            event_type="not_allowed",
            payload=_candidate(),
        )

    bad_schema = _malformed_dataclass(_candidate(), schema_version="bad")
    with pytest.raises(AuditLogWriteError, match="schema_version"):
        write_audit_event(tmp_path, run_id="r-safe", event_type="candidate_log", payload=bad_schema)

    missing_required = CommonAuditPayload(run_id="r-safe", timestamp=NOW.isoformat())
    with pytest.raises(AuditLogWriteError, match="missing required"):
        write_audit_event(
            tmp_path,
            run_id="r-safe",
            event_type="candidate_log",
            payload=missing_required,
        )

    decision = evaluate(_candidate(), _context())
    bad_reason = _malformed_dataclass(decision, status=decision.status, reasons=("bad_reason",))
    with pytest.raises(AuditLogWriteError, match="invalid reason code"):
        write_audit_event(
            tmp_path,
            run_id="r-safe",
            event_type="risk_decision_log",
            payload=bad_reason,
        )


def test_audit_writer_rejects_symlink_escape(tmp_path) -> None:
    root = tmp_path / "root"
    outside = tmp_path / "outside"
    outside.mkdir()
    root.mkdir()
    (root / "r-safe").symlink_to(outside, target_is_directory=True)

    with pytest.raises(AuditLogWriteError, match="symlink"):
        write_audit_event(root, run_id="r-safe", event_type="candidate_log", payload=_candidate())


def test_audit_writer_rejects_event_file_symlink(tmp_path) -> None:
    root = tmp_path / "root"
    run_dir = root / "r-safe"
    outside = tmp_path / "outside.jsonl"
    run_dir.mkdir(parents=True)
    outside.write_text("")
    (run_dir / "candidate_log.jsonl").symlink_to(outside)

    with pytest.raises(AuditLogWriteError, match="symlink"):
        write_audit_event(root, run_id="r-safe", event_type="candidate_log", payload=_candidate())


def test_audit_writer_write_and_fsync_failures_are_fail_closed(tmp_path, monkeypatch) -> None:
    not_a_directory = tmp_path / "blocked"
    not_a_directory.write_text("file")
    with pytest.raises(AuditLogWriteError, match="write failed"):
        write_audit_event(
            not_a_directory,
            run_id="r-safe",
            event_type="candidate_log",
            payload=_candidate(),
        )

    def fail_fsync(_fd):
        raise OSError("fsync failed")

    monkeypatch.setattr("app.shadow.audit.os.fsync", fail_fsync)
    with pytest.raises(AuditLogWriteError, match="fsync failed"):
        write_audit_event(
            tmp_path,
            run_id="r-safe",
            event_type="candidate_log",
            payload=_candidate(),
        )
